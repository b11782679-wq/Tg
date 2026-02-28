from __future__ import annotations

import os
import secrets
import time
import hmac
import hashlib
import datetime
from zoneinfo import ZoneInfo
from pathlib import Path

from aiogram import Router, F
try:
    from aiogram.exceptions import SkipHandler
except Exception:
    try:
        from aiogram.dispatcher.event.bases import SkipHandler
    except Exception:
        SkipHandler = None  # type: ignore
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.db.repo import Repo
from bot.keyboards.youtube_auto import (
    yt_auto_menu_kb, yt_visibility_kb, yt_schedule_choice_kb, yt_timezone_kb,
    yt_metadata_menu_kb, yt_yes_no_kb, yt_category_kb, yt_licence_kb, yt_comments_kb
)
from bot.services.youtube_uploader import to_utc_sqlite_datetime

from google_auth_oauthlib.flow import Flow


router = Router()
_repo: Repo | None = None
_cfg: Config | None = None
_deny_bot_notice_ts: dict[int, float] = {}


class YTAutoStates(StatesGroup):
    waiting_video = State()
    waiting_title = State()
    waiting_description = State()
    waiting_timezone = State()
    waiting_schedule_time = State()
    # Metadata states
    waiting_tags = State()
    waiting_language = State()
    waiting_recording_date = State()
    waiting_video_location = State()


def setup(repo: Repo, cfg: Config):
    global _repo, _cfg
    _repo = repo
    _cfg = cfg


async def _deny_bot_user(obj: Message | CallbackQuery) -> bool:
    u = getattr(obj, "from_user", None)
    if not u or not getattr(u, "is_bot", False):
        return False
    uid = int(getattr(u, "id", 0) or 0)
    # Silent deny - no messages to avoid spam
    try:
        if isinstance(obj, CallbackQuery):
            await obj.answer()  # silent - no text, no alert
    except Exception:
        pass
    # Log once per user per 60 seconds to log channel only
    now = float(time.time())
    last = float(_deny_bot_notice_ts.get(uid, 0.0))
    if now - last >= 60.0:
        _deny_bot_notice_ts[uid] = now
        try:
            if _cfg and (_cfg.log_channel or "").strip():
                await (obj.bot.send_message(
                    _cfg.log_channel,
                    "<b>YT BLOCKED BOT USER</b>\n" + f"User: <code>{uid}</code>",
                ))
        except Exception:
            pass
    return True


@router.callback_query(F.data == "yt:auto:noop")
async def yt_noop(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data == "yt:auto:menu")
async def yt_auto_menu(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await state.clear()
    await _repo.yt_draft_clear(call.from_user.id)
    token = await _repo.yt_get_token(call.from_user.id)
    is_connected = bool(token)
    txt = "🤖 <b>Avtomatlashtirilgan YouTube</b>\n\nQuyidagilardan birini tanlang 👇"
    await call.message.edit_text(txt, reply_markup=yt_auto_menu_kb(is_connected=is_connected))
    await call.answer()


@router.callback_query(F.data == "yt:auto:connect")
async def yt_auto_connect(call: CallbackQuery):
    if await _deny_bot_user(call):
        return
    await call.answer()

    if not (_cfg.youtube_oauth_client_id and _cfg.youtube_oauth_client_secret and _cfg.youtube_oauth_redirect_url):
        await call.message.answer("❌ YouTube OAuth sozlanmagan.")
        return

    # PKCE: embed code_verifier into signed state so callback can redeem code.
    nonce = secrets.token_urlsafe(8).replace("-", "").replace("_", "")
    ts = int(time.time())
    verifier = secrets.token_urlsafe(48).replace("-", "").replace("_", "")
    payload = f"{int(call.from_user.id)}:{ts}:{nonce}:{verifier}"
    key = (_cfg.youtube_oauth_client_secret or _cfg.bot_token or "").encode("utf-8")
    sig = hmac.new(key, payload.encode("utf-8"), hashlib.sha256).hexdigest()[:20]
    state = f"{payload}:{sig}"

    # Keep DB state for backward compat/observability (but flow can work without it).
    await _repo.yt_oauth_create_state(call.from_user.id, state)

    base = (_cfg.admin_public_url or "").strip().rstrip("/")
    if not base:
        base = str(_cfg.youtube_oauth_redirect_url).split("/oauth/youtube/")[0].rstrip("/")
    url = f"{base}/oauth/youtube/start?state={state}"

    await call.message.answer(
        "🔗 Kanalni ulash uchun quyidagi linkni bosing:\n"
        f"{url}\n\n"
        "Google ruxsat bergandan keyin botga qayting.",
        disable_web_page_preview=True,
    )


@router.callback_query(F.data == "yt:auto:disconnect")
async def yt_auto_disconnect(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await _repo.yt_disconnect(call.from_user.id)
    await state.clear()
    await call.message.answer("✅ Ulanish uzildi.")


@router.callback_query(F.data == "yt:auto:upload")
async def yt_auto_upload_start(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    token = await _repo.yt_get_token(call.from_user.id)
    if not token:
        await call.message.answer("❗️ Avval kanalni ulang (Kanalni ulash).")
        return

    await state.clear()
    await _repo.yt_draft_clear(call.from_user.id)
    await _repo.yt_draft_upsert(call.from_user.id, step="video")
    await state.set_state(YTAutoStates.waiting_video)
    await call.message.answer("📤 Videoni yuboring (Telegram video yoki document).")


@router.message(YTAutoStates.waiting_video)
async def yt_auto_got_video(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    doc = message.document
    vid = message.video
    if not doc and not vid:
        await message.answer("❗️ Video yuboring.")
        return

    file_id = (vid.file_id if vid else doc.file_id)
    fname = (vid.file_name if vid and getattr(vid, "file_name", None) else (doc.file_name if doc else None))
    if not fname:
        fname = "video.mp4"

    tmp_dir = Path("tmp") / "yt"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    safe_name = secrets.token_hex(12) + "_" + (Path(fname).name or "video.mp4")
    dest = tmp_dir / safe_name

    try:
        tg_file = await message.bot.get_file(file_id)
        # aiogram v3 supports download_file
        await message.bot.download_file(tg_file.file_path, destination=dest)
    except Exception as e:
        await message.answer(f"❌ Videoni yuklab bo‘lmadi: <code>{str(e)[:200]}</code>")
        return

    await state.update_data(file_path=str(dest))
    await _repo.yt_draft_upsert(message.from_user.id, step="title", file_path=str(dest))
    await state.set_state(YTAutoStates.waiting_title)
    await message.answer("✍️ Video sarlavhasini (Title) yozing:")


@router.message(YTAutoStates.waiting_title)
async def yt_auto_got_title(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    title = (message.text or "").strip()
    if not title:
        await message.answer("❗️ Title bo‘sh bo‘lmasin.")
        return
    await state.update_data(title=title)
    await _repo.yt_draft_upsert(message.from_user.id, step="description", title=title)
    await state.set_state(YTAutoStates.waiting_description)
    await message.answer("📝 Description (ixtiyoriy). Bo‘sh qoldirish uchun <code>-</code> yuboring:")


@router.message(F.text, F.reply_to_message)
async def yt_auto_reply_without_state(message: Message, state: FSMContext):
    cur = await state.get_state()
    if cur:
        if SkipHandler:
            raise SkipHandler()
        return
    rt = getattr(message.reply_to_message, "text", None) or ""
    rt = str(rt)
    if (
        "Video sarlavhasini" in rt
        or "Videoni yuboring" in rt
        or "Description" in rt
        or "Timezone" in rt
        or "Vaqt kiriting" in rt
    ):
        await message.answer(
            "❗️ Jarayon uzilib qoldi (bot yangilangan yoki qayta ishga tushgan bo‘lishi mumkin).\n\n"
            "Iltimos, yana: <b>🤖 Avtomatlashtirilgan YouTube</b> → <b>📤 Video yuklash</b> ni bosib qaytadan boshlang.",
        )
    if SkipHandler:
        raise SkipHandler()
    return


@router.message(YTAutoStates.waiting_description)
async def yt_auto_got_description(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""
    await state.update_data(description=desc)
    await _repo.yt_draft_upsert(message.from_user.id, step="visibility", description=desc)
    await message.answer("🔒 Visibility tanlang:", reply_markup=yt_visibility_kb())


@router.callback_query(F.data == "yt:auto:vis:back")
async def yt_auto_back_to_visibility(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await _repo.yt_draft_upsert(call.from_user.id, step="visibility")
    await call.message.edit_text("🔒 Visibility tanlang:", reply_markup=yt_visibility_kb())


@router.callback_query(F.data.startswith("yt:auto:vis:"))
async def yt_auto_set_visibility(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    vis = (call.data or "").split(":")[-1]
    if vis not in ("public", "unlisted", "private"):
        vis = "private"
    await state.update_data(visibility=vis)
    await _repo.yt_draft_upsert(call.from_user.id, step="timezone", visibility=vis)
    await state.set_state(YTAutoStates.waiting_timezone)
    await call.message.answer("🌍 Timezone tanlang:", reply_markup=yt_timezone_kb())


@router.callback_query(F.data.startswith("yt:auto:tz:"))
async def yt_auto_set_timezone(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    raw = (call.data or "").split(":", maxsplit=3)[-1]
    tz = str(raw or "").strip()
    if tz == "manual":
        await state.set_state(YTAutoStates.waiting_timezone)
        await call.message.edit_text(
            "🌍 Timezone yozing (masalan: <code>Asia/Tashkent</code>).\n"
            "Ro‘yxat: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
            disable_web_page_preview=True,
        )
        return

    try:
        z = ZoneInfo(tz)
    except Exception:
        await call.message.answer("❌ Timezone noto‘g‘ri. Masalan: <code>Asia/Tashkent</code>")
        return

    await state.update_data(timezone=tz)
    await _repo.yt_draft_upsert(call.from_user.id, step="schedule_time", timezone=tz)
    await state.set_state(YTAutoStates.waiting_schedule_time)
    
    # Get current time in selected timezone
    now_local = datetime.datetime.now(tz=z)
    current_time_str = now_local.strftime("%Y-%m-%d %H:%M")
    
    # Create inline keyboard with options
    from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚙️ Qo‘shimcha sozlamalar", callback_data="yt:auto:metadata:menu"),
            ],
            [
                InlineKeyboardButton(text="⚡ Hozir", callback_data="yt:auto:sched:now"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:tz:back"),
            ],
        ]
    )
    
    await call.message.edit_text(
        f"📅 <b>Vaqt kiriting:</b> <code>YYYY-MM-DD HH:MM</code>\n\n"
        f"🌍 Sizning vaqtingiz ({tz}):\n"
        f"<code>{current_time_str}</code>\n\n"
        f"✍️ Yuqoridagi formatda yozing:\n"
        f"Masalan: <code>{current_time_str}</code>\n\n"
        f"ℹ️ Hozir yuklash uchun: <code>-</code> yuboring",
        reply_markup=kb
    )


@router.callback_query(F.data == "yt:auto:tz:back")
async def yt_auto_back_to_timezone(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await state.set_state(YTAutoStates.waiting_timezone)
    await _repo.yt_draft_upsert(call.from_user.id, step="timezone")
    await call.message.edit_text("🌍 Timezone tanlang:", reply_markup=yt_timezone_kb())


@router.message(YTAutoStates.waiting_timezone)
async def yt_auto_got_timezone(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    tz = (message.text or "").strip()
    if not tz:
        await message.answer("❗️ Timezone bo‘sh bo‘lmasin.")
        return
    await state.update_data(timezone=tz)
    await _repo.yt_draft_upsert(message.from_user.id, step="schedule", timezone=tz)
    await message.answer("⏰ Qachon yuklaymiz?", reply_markup=yt_schedule_choice_kb())


@router.callback_query(F.data == "yt:auto:sched:now")
async def yt_auto_schedule_now(call: CallbackQuery, state: FSMContext):
    uid = int(call.from_user.id) if call.from_user else 0
    is_bot = bool(getattr(call.from_user, "is_bot", False))
    
    # Debug
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            await call.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG schedule_now START</b>\nUser: <code>{uid}</code>\nis_bot: {is_bot}",
            )
    except Exception:
        pass
    
    if await _deny_bot_user(call):
        try:
            if _cfg and (_cfg.log_channel or "").strip():
                await call.bot.send_message(
                    _cfg.log_channel,
                    f"<b>YT DEBUG schedule_now DENIED</b>\nUser: <code>{uid}</code>",
                )
        except Exception:
            pass
        return
    
    # Debug passed deny
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            await call.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG schedule_now PASSED deny</b>\nUser: <code>{uid}</code>",
            )
    except Exception:
        pass
    
    await call.answer()
    await _finalize_upload(call.message, state, scheduled_at=None, user_id=call.from_user.id)


@router.callback_query(F.data == "yt:auto:sched:set")
async def yt_auto_schedule_set(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await _repo.yt_draft_upsert(call.from_user.id, step="schedule_time")
    await state.set_state(YTAutoStates.waiting_schedule_time)
    await call.message.answer("📅 Vaqt kiriting: <code>YYYY-MM-DD HH:MM</code> (timezone bo‘yicha)")


@router.callback_query(F.data.startswith("yt:auto:sched:preset:"))
async def yt_auto_schedule_preset(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    preset = (call.data or "").split(":")[-1]

    draft = await _repo.yt_draft_get(call.from_user.id)
    tz = str((draft["timezone"] if draft else "") or "").strip()
    if not tz:
        data = await state.get_data()
        tz = str(data.get("timezone") or "").strip()
    if not tz:
        await call.message.answer("❗️ Avval timezone tanlang.")
        return

    try:
        z = ZoneInfo(tz)
    except Exception:
        await call.message.answer("❌ Timezone noto‘g‘ri. Qaytadan tanlang.")
        return

    now_local = datetime.datetime.now(tz=z)
    if preset == "10m":
        target = now_local + datetime.timedelta(minutes=10)
    elif preset == "1h":
        target = now_local + datetime.timedelta(hours=1)
    elif preset == "tom10":
        tomorrow = (now_local + datetime.timedelta(days=1)).date()
        target = datetime.datetime(
            year=tomorrow.year,
            month=tomorrow.month,
            day=tomorrow.day,
            hour=10,
            minute=0,
            tzinfo=z,
        )
    else:
        await call.message.answer("❌ Noma'lum preset.")
        return

    local_str = target.strftime("%Y-%m-%d %H:%M")
    try:
        utc_dt = to_utc_sqlite_datetime(local_str, tz)
    except Exception as e:
        await call.message.answer(f"❌ Vaqt xato: <code>{str(e)[:200]}</code>")
        return

    await _finalize_upload(call.message, state, scheduled_at=utc_dt, user_id=call.from_user.id)


@router.message(YTAutoStates.waiting_schedule_time)
async def yt_auto_got_schedule_time(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    data = await state.get_data()
    tz = str(data.get("timezone") or "").strip()
    raw = (message.text or "").strip()
    try:
        utc_dt = to_utc_sqlite_datetime(raw, tz)
    except Exception as e:
        await message.answer(f"❌ Vaqt xato: <code>{str(e)[:200]}</code>")
        return

    await _finalize_upload(message, state, scheduled_at=utc_dt)


async def _finalize_upload(message: Message, state: FSMContext, scheduled_at: str | None, user_id: int | None = None):
    uid = int(user_id) if user_id else (int(message.from_user.id) if message.from_user else 0)
    
    # Debug: log entry
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            await message.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG _finalize_upload ENTRY</b>\nUser: <code>{uid}</code>",
            )
    except Exception:
        pass
    
    # Final safety check - prevent bot users from creating uploads
    user = getattr(message, "from_user", None)
    # For callbacks, use provided user_id to check; for messages, use message.from_user
    check_user_id = user_id if user_id else (getattr(user, 'id', None) if user else None)
    check_is_bot = False
    if check_user_id:
        # If we have the user_id, we need to check if it's a bot
        # For callback queries, we trust the call.from_user.is_bot check done earlier
        # For direct messages, check the message sender
        if not user_id and user and getattr(user, "is_bot", False):
            check_is_bot = True
    if check_is_bot:
        try:
            if _cfg and (_cfg.log_channel or "").strip():
                await message.bot.send_message(
                    _cfg.log_channel,
                    f"<b>YT BLOCKED BOT in _finalize_upload</b>\nUser: <code>{int(user.id)}</code>",
                )
        except Exception:
            pass
        await state.clear()
        return
    
    data = await state.get_data()
    draft = await _repo.yt_draft_get(uid if uid else (message.from_user.id if message.from_user else 0))
    
    # Debug: log state and draft
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            has_file = bool(data.get("file_path"))
            has_draft = bool(draft)
            await message.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG state/draft</b>\nUser: <code>{uid}</code>\nState file_path: {has_file}\nDraft exists: {has_draft}",
            )
    except Exception:
        pass
    
    # If draft missing but we have state data, try to recover
    target_uid = uid if uid else (message.from_user.id if message.from_user else 0)
    if not draft and data.get("file_path"):
        await _repo.yt_draft_upsert(
            target_uid,
            step="schedule",
            file_path=data.get("file_path"),
            title=data.get("title"),
            description=data.get("description"),
            visibility=data.get("visibility"),
            timezone=data.get("timezone"),
        )
        draft = await _repo.yt_draft_get(target_uid)
    
    file_path = str((draft["file_path"] if draft else data.get("file_path")) or "").strip()
    title = str((draft["title"] if draft else data.get("title")) or "").strip()
    description = str((draft["description"] if draft else data.get("description")) or "").strip()
    visibility = str((draft["visibility"] if draft else data.get("visibility")) or "private").strip()
    timezone = str((draft["timezone"] if draft else data.get("timezone")) or "").strip()
    
    # Extract metadata fields from draft or state
    made_for_kids = int((draft["made_for_kids"] if draft else data.get("made_for_kids")) or 0)
    tags = str((draft["tags"] if draft else data.get("tags")) or "").strip()
    category = str((draft["category"] if draft else data.get("category")) or "").strip()
    language = str((draft["language"] if draft else data.get("language")) or "").strip()
    recording_date = str((draft["recording_date"] if draft else data.get("recording_date")) or "").strip() or None
    video_location = str((draft["video_location"] if draft else data.get("video_location")) or "").strip()
    licence = str((draft["licence"] if draft else data.get("licence")) or "Standard YouTube licence").strip()
    allow_embedding = int((draft["allow_embedding"] if draft else data.get("allow_embedding")) or 1)
    shorts_remixing = str((draft["shorts_remixing"] if draft else data.get("shorts_remixing")) or "allow_video_audio").strip()
    comments = str((draft["comments"] if draft else data.get("comments")) or "on").strip()
    age_restricted = int((draft["age_restricted"] if draft else data.get("age_restricted")) or 0)
    paid_promotion = int((draft["paid_promotion"] if draft else data.get("paid_promotion")) or 0)
    altered_content = int((draft["altered_content"] if draft else data.get("altered_content")) or 0)
    
    # Debug: log file check
    fp_exists = os.path.exists(file_path) if file_path else False
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            await message.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG file check</b>\nUser: <code>{uid}</code>\nPath: <code>{file_path[:50] if file_path else 'NONE'}...</code>\nExists: {fp_exists}",
            )
    except Exception:
        pass
    
    if not file_path or not os.path.exists(file_path):
        await message.answer("❌ Video topilmadi. Qaytadan yuboring.")
        await state.clear()
        await _repo.yt_draft_clear(uid if uid else (message.from_user.id if message.from_user else 0))
        return

    # Debug: before creating upload
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            await message.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG creating upload</b>\nUser: <code>{uid}</code>\nTitle: {title[:30] if title else 'NONE'}",
            )
    except Exception:
        pass

    upload_id = await _repo.yt_create_pending_upload(
        user_id=uid if uid else (message.from_user.id if message.from_user else 0),
        file_path=file_path,
        title=title,
        description=description,
        visibility=visibility,
        timezone=timezone,
        scheduled_at=scheduled_at,
        made_for_kids=made_for_kids,
        tags=tags,
        category=category,
        language=language,
        recording_date=recording_date,
        video_location=video_location,
        licence=licence,
        allow_embedding=allow_embedding,
        shorts_remixing=shorts_remixing,
        comments=comments,
        age_restricted=age_restricted,
        paid_promotion=paid_promotion,
        altered_content=altered_content,
    )

    try:
        if _cfg and (_cfg.log_channel or "").strip():
            log_uid = uid if uid else (message.from_user.id if message.from_user else 0)
            await message.bot.send_message(
                _cfg.log_channel,
                "<b>YT QUEUED</b>\n"
                f"User: <code>{int(log_uid)}</code>\n"
                f"ID: <code>{int(upload_id)}</code>\n"
                + (f"Title: <b>{title}</b>\n" if title else "")
                + (f"Visibility: <code>{visibility}</code>\n" if visibility else "")
                + (f"Scheduled (UTC): <code>{scheduled_at}</code>" if scheduled_at else "Now"),
                disable_web_page_preview=True,
            )
    except Exception:
        pass

    await state.clear()
    await _repo.yt_draft_clear(uid if uid else (message.from_user.id if message.from_user else 0))

    if scheduled_at:
        await message.answer(
            "✅ Video rejalashtirildi.\n\n"
            f"ID: <code>{upload_id}</code>\n"
            f"Yuklash vaqti (UTC): <code>{scheduled_at}</code>\n\n"
            "Vaqti kelganda bot avtomatik YouTube’ga yuklaydi.",
        )
    else:
        await message.answer(
            "✅ Video navbatga qo‘shildi.\n\n"
            f"ID: <code>{upload_id}</code>\n"
            "Bot tez orada YouTube’ga yuklaydi.",
        )


@router.callback_query(F.data == "yt:auto:pending")
async def yt_auto_pending(call: CallbackQuery):
    await call.answer()
    rows = await _repo.yt_list_pending_uploads(call.from_user.id, limit=10)
    if not rows:
        await call.message.answer("Hozircha rejalashtirilgan videolar yo‘q.")
        return

    txt = "🗓 <b>Rejalashtirilgan videolar</b>\n\n"
    for r in rows:
        txt += (
            f"• <code>{int(r['id'])}</code> — <b>{(r['status'] or '')}</b>"
            + (f" — <code>{r['scheduled_at']}</code>" if r['scheduled_at'] else "")
            + "\n"
        )
    await call.message.answer(txt)


@router.message(F.video | F.document)
async def yt_auto_draft_video_router(message: Message, state: FSMContext):
    draft = await _repo.yt_draft_get(message.from_user.id)
    if not draft or str(draft["step"] or "") != "video":
        if SkipHandler:
            raise SkipHandler()
        return
    await yt_auto_got_video(message, state)


@router.message(F.text)
async def yt_auto_draft_text_router(message: Message, state: FSMContext):
    # DEBUG: Log entry
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            current_state = await state.get_state()
            draft = await _repo.yt_draft_get(message.from_user.id)
            draft_step = draft["step"] if draft else None
            await message.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG text_router ENTRY</b>\n"
                f"User: <code>{message.from_user.id}</code>\n"
                f"State: <code>{current_state}</code>\n"
                f"Draft step: <code>{draft_step}</code>\n"
                f"Text: <code>{message.text[:50] if message.text else 'None'}</code>"
            )
    except Exception:
        pass
    
    draft = await _repo.yt_draft_get(message.from_user.id)
    if not draft:
        if SkipHandler:
            raise SkipHandler()
        return
    step = str(draft["step"] or "")
    
    # Check metadata states FIRST (before checking draft step)
    current_state = await state.get_state()
    if current_state == YTAutoStates.waiting_tags.state:
        await yt_auto_got_tags(message, state)
        return
    if current_state == YTAutoStates.waiting_language.state:
        await yt_auto_got_language(message, state)
        return
    if current_state == YTAutoStates.waiting_recording_date.state:
        await yt_auto_got_recording_date(message, state)
        return
    if current_state == YTAutoStates.waiting_video_location.state:
        await yt_auto_got_video_location(message, state)
        return
    
    # Then check draft step
    if step == "title":
        await yt_auto_got_title(message, state)
        return
    if step == "description":
        await yt_auto_got_description(message, state)
        return
    if step == "timezone":
        await yt_auto_got_timezone(message, state)
        return
    if step == "schedule_time":
        # Ensure tz is available for legacy state.get_data() path
        try:
            await state.update_data(timezone=str(draft["timezone"] or ""))
        except Exception:
            pass
        await yt_auto_got_schedule_time(message, state)
        return

    await _repo.yt_draft_clear(message.from_user.id)
    await message.answer(
        "❗️ Jarayon holati noaniq bo‘lib qoldi. Qaytadan boshlaymiz.\n\n"
        "<b>🤖 Avtomatlashtirilgan YouTube</b> → <b>📤 Video yuklash</b>",
    )


# Metadata collection handlers
@router.callback_query(F.data == "yt:auto:metadata:menu")
async def yt_auto_metadata_menu(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "⚙️ <b>Qo‘shimcha sozlamalar</b>\n\n"
        "Kerakli maydonlarni tanlang:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:sched:choice")
async def yt_auto_sched_choice(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "⏰ Qachon yuklaymiz?",
        reply_markup=yt_schedule_choice_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:made_for_kids")
async def yt_auto_meta_made_for_kids(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "👶 <b>Made for Kids</b>\n\n"
        "Bu video bolalar uchun mo‘ljallanganmi?\n"
        "(COPPA talablariga ko'ra)",
        reply_markup=yt_yes_no_kb("yt:auto:meta:mfk")
    )


@router.callback_query(F.data.startswith("yt:auto:meta:mfk:"))
async def yt_auto_meta_made_for_kids_set(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    value = (call.data or "").split(":")[-1] == "yes"
    await state.update_data(made_for_kids=1 if value else 0)
    await _repo.yt_draft_upsert(call.from_user.id, step="metadata", made_for_kids=1 if value else 0)
    await call.message.edit_text(
        "✅ Saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:tags")
async def yt_auto_meta_tags(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await state.set_state(YTAutoStates.waiting_tags)
    await state.update_data(last_bot_message_id=call.message.message_id)
    await call.message.edit_text(
        "🏷️ <b>Teglar (Tags)</b>\n\n"
        "Teglarni vergul bilan ajratib yozing (masalan: o'zbek, musiqa, 2024)\n"
        "Maksimal 500 ta, har biri 500 belgidan oshmasligi kerak.\n\n"
        "Yo‘q bo‘lsa <code>-</code> yuboring."
    )


async def yt_auto_got_tags(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    tags = (message.text or "").strip()
    if tags == "-":
        tags = ""
    
    # DEBUG: Log the message info
    try:
        if _cfg and (_cfg.log_channel or "").strip():
            await message.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG got_tags START</b>\n"
                f"User: <code>{message.from_user.id}</code>\n"
                f"Chat ID: <code>{message.chat.id}</code>\n"
                f"Message ID: <code>{message.message_id}</code>\n"
                f"Reply to: <code>{message.reply_to_message.message_id if message.reply_to_message else 'None'}</code>"
            )
    except Exception as e:
        pass
    
    # Get state data BEFORE doing anything else
    try:
        data = await state.get_data()
        last_msg_id = data.get("last_bot_message_id")
        current_state = await state.get_state()
        
        # DEBUG: Log state info
        if _cfg and (_cfg.log_channel or "").strip():
            await message.bot.send_message(
                _cfg.log_channel,
                f"<b>YT DEBUG state</b>\n"
                f"last_msg_id: <code>{last_msg_id}</code>\n"
                f"current_state: <code>{current_state}</code>\n"
                f"data keys: <code>{list(data.keys())}</code>"
            )
    except Exception as e:
        try:
            if _cfg and (_cfg.log_channel or "").strip():
                await message.bot.send_message(
                    _cfg.log_channel,
                    f"<b>YT DEBUG state ERROR</b>\n<code>{str(e)[:200]}</code>"
                )
        except Exception:
            pass
        last_msg_id = None
    
    # Delete user message
    try:
        await message.delete()
    except Exception as e:
        try:
            if _cfg and (_cfg.log_channel or "").strip():
                await message.bot.send_message(
                    _cfg.log_channel,
                    f"<b>YT DEBUG delete failed</b>\n<code>{str(e)[:200]}</code>"
                )
        except Exception:
            pass
    
    # Save data and clear state
    try:
        await state.update_data(tags=tags)
        await _repo.yt_draft_upsert(message.from_user.id, step="metadata", tags=tags)
        await state.set_state(None)
    except Exception as e:
        try:
            if _cfg and (_cfg.log_channel or "").strip():
                await message.bot.send_message(
                    _cfg.log_channel,
                    f"<b>YT DEBUG save failed</b>\n<code>{str(e)[:200]}</code>"
                )
        except Exception:
            pass
        return
    
    # Try to edit the previous bot message
    if last_msg_id:
        try:
            result = await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=last_msg_id,
                text="✅ Teglar saqlandi!\n\nBoshqa sozlamalar:",
                reply_markup=yt_metadata_menu_kb()
            )
            # DEBUG: Log success
            if _cfg and (_cfg.log_channel or "").strip():
                await message.bot.send_message(
                    _cfg.log_channel,
                    f"<b>YT DEBUG edit SUCCESS</b>\n"
                    f"Message ID: <code>{last_msg_id}</code>"
                )
            return
        except Exception as e:
            # DEBUG: Log edit error
            try:
                if _cfg and (_cfg.log_channel or "").strip():
                    await message.bot.send_message(
                        _cfg.log_channel,
                        f"<b>YT DEBUG edit FAILED</b>\n"
                        f"Message ID: <code>{last_msg_id}</code>\n"
                        f"Error: <code>{str(e)[:300]}</code>"
                    )
            except Exception:
                pass
    else:
        # DEBUG: No message ID
        try:
            if _cfg and (_cfg.log_channel or "").strip():
                await message.bot.send_message(
                    _cfg.log_channel,
                    f"<b>YT DEBUG no last_msg_id</b>"
                )
        except Exception:
            pass
    
    # Fallback: send new message
    await message.answer(
        "✅ Teglar saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:category")
async def yt_auto_meta_category(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "📁 <b>Kategoriya tanlang</b>",
        reply_markup=yt_category_kb()
    )


@router.callback_query(F.data.startswith("yt:auto:meta:cat:"))
async def yt_auto_meta_category_set(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    category = (call.data or "").split(":")[-1]
    await state.update_data(category=category)
    await _repo.yt_draft_upsert(call.from_user.id, step="metadata", category=category)
    await call.message.edit_text(
        "✅ Kategoriya saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:language")
async def yt_auto_meta_language(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await state.set_state(YTAutoStates.waiting_language)
    await state.update_data(last_bot_message_id=call.message.message_id)
    await call.message.edit_text(
        "🌐 <b>Video tili</b>\n\n"
        "Til kodini yozing (masalan: uz, en, ru)\n"
        "Yo‘q bo‘lsa <code>-</code> yuboring."
    )


async def yt_auto_got_language(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    language = (message.text or "").strip()
    if language == "-":
        language = ""
    # Get state data BEFORE clearing
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    # Delete user message
    try:
        await message.delete()
    except Exception:
        pass
    # Save data and clear state
    await state.update_data(language=language)
    await _repo.yt_draft_upsert(message.from_user.id, step="metadata", language=language)
    await state.set_state(None)
    # Try to edit the previous bot message
    if last_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=last_msg_id,
                text="✅ Til saqlandi!\n\nBoshqa sozlamalar:",
                reply_markup=yt_metadata_menu_kb()
            )
            return
        except Exception:
            pass
    await message.answer(
        "✅ Til saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:recording_date")
async def yt_auto_meta_recording_date(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await state.set_state(YTAutoStates.waiting_recording_date)
    await state.update_data(last_bot_message_id=call.message.message_id)
    await call.message.edit_text(
        "📅 <b>Suratga olingan sana</b>\n\n"
        "Sanani yozing: <code>YYYY-MM-DD</code>\n"
        "(masalan: 2024-01-15)\n\n"
        "Yo‘q bo‘lsa <code>-</code> yuboring."
    )


async def yt_auto_got_recording_date(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    recording_date = (message.text or "").strip()
    if recording_date == "-":
        recording_date = ""
    # Get state data BEFORE clearing
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    # Delete user message
    try:
        await message.delete()
    except Exception:
        pass
    # Save data and clear state
    await state.update_data(recording_date=recording_date)
    await _repo.yt_draft_upsert(message.from_user.id, step="metadata", recording_date=recording_date if recording_date else None)
    await state.set_state(None)
    # Try to edit the previous bot message
    if last_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=last_msg_id,
                text="✅ Sana saqlandi!\n\nBoshqa sozlamalar:",
                reply_markup=yt_metadata_menu_kb()
            )
            return
        except Exception:
            pass
    await message.answer(
        "✅ Sana saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:video_location")
async def yt_auto_meta_video_location(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await state.set_state(YTAutoStates.waiting_video_location)
    await state.update_data(last_bot_message_id=call.message.message_id)
    await call.message.edit_text(
        "📍 <b>Video joylashuvi</b>\n\n"
        "Videoning suratga olingan joyini yozing:\n"
        "(masalan: Toshkent, O'zbekiston)\n\n"
        "Yo‘q bo‘lsa <code>-</code> yuboring."
    )


async def yt_auto_got_video_location(message: Message, state: FSMContext):
    if await _deny_bot_user(message):
        return
    video_location = (message.text or "").strip()
    if video_location == "-":
        video_location = ""
    # Get state data BEFORE clearing
    data = await state.get_data()
    last_msg_id = data.get("last_bot_message_id")
    # Delete user message
    try:
        await message.delete()
    except Exception:
        pass
    # Save data and clear state
    await state.update_data(video_location=video_location)
    await _repo.yt_draft_upsert(message.from_user.id, step="metadata", video_location=video_location)
    await state.set_state(None)
    # Try to edit the previous bot message
    if last_msg_id:
        try:
            await message.bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=last_msg_id,
                text="✅ Joylashuv saqlandi!\n\nBoshqa sozlamalar:",
                reply_markup=yt_metadata_menu_kb()
            )
            return
        except Exception:
            pass
    await message.answer(
        "✅ Joylashuv saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:licence")
async def yt_auto_meta_licence(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "📄 <b>Litsenziya tanlang</b>",
        reply_markup=yt_licence_kb()
    )


@router.callback_query(F.data.startswith("yt:auto:meta:lic:"))
async def yt_auto_meta_licence_set(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    lic_type = (call.data or "").split(":")[-1]
    licence = "Creative Commons" if lic_type == "creative" else "Standard YouTube licence"
    await state.update_data(licence=licence)
    await _repo.yt_draft_upsert(call.from_user.id, step="metadata", licence=licence)
    await call.message.edit_text(
        "✅ Litsenziya saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:comments")
async def yt_auto_meta_comments(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "💬 <b>Kommentlar sozlamalari</b>",
        reply_markup=yt_comments_kb()
    )


@router.callback_query(F.data.startswith("yt:auto:meta:comments:"))
async def yt_auto_meta_comments_set(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    comments = (call.data or "").split(":")[-1]
    await state.update_data(comments=comments)
    await _repo.yt_draft_upsert(call.from_user.id, step="metadata", comments=comments)
    await call.message.edit_text(
        "✅ Kommentlar sozlamasi saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:age_restricted")
async def yt_auto_meta_age_restricted(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "🔞 <b>Yosh cheklamasi</b>\n\n"
        "Bu video 18+ yosh cheklamasiga ega mi?",
        reply_markup=yt_yes_no_kb("yt:auto:meta:age")
    )


@router.callback_query(F.data.startswith("yt:auto:meta:age:"))
async def yt_auto_meta_age_restricted_set(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    value = (call.data or "").split(":")[-1] == "yes"
    await state.update_data(age_restricted=1 if value else 0)
    await _repo.yt_draft_upsert(call.from_user.id, step="metadata", age_restricted=1 if value else 0)
    await call.message.edit_text(
        "✅ Yosh cheklamasi saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )


@router.callback_query(F.data == "yt:auto:meta:paid_promotion")
async def yt_auto_meta_paid_promotion(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    await call.message.edit_text(
        "💰 <b>To'langan reklama</b>\n\n"
        "Videoda to'langan reklama, mahsulot joylashish yoki homiylik bormi?",
        reply_markup=yt_yes_no_kb("yt:auto:meta:pp")
    )


@router.callback_query(F.data.startswith("yt:auto:meta:pp:"))
async def yt_auto_meta_paid_promotion_set(call: CallbackQuery, state: FSMContext):
    if await _deny_bot_user(call):
        return
    await call.answer()
    value = (call.data or "").split(":")[-1] == "yes"
    await state.update_data(paid_promotion=1 if value else 0)
    await _repo.yt_draft_upsert(call.from_user.id, step="metadata", paid_promotion=1 if value else 0)
    await call.message.edit_text(
        "✅ Reklama sozlamasi saqlandi!\n\n"
        "Boshqa sozlamalar:",
        reply_markup=yt_metadata_menu_kb()
    )
