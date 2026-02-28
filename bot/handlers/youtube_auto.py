from __future__ import annotations

import os
import secrets
import time
import hmac
import hashlib
from pathlib import Path

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import StatesGroup, State
from aiogram.types import CallbackQuery, Message

from bot.config import Config
from bot.db.repo import Repo
from bot.keyboards.youtube_auto import yt_auto_menu_kb, yt_visibility_kb, yt_schedule_choice_kb
from bot.services.youtube_uploader import to_utc_sqlite_datetime

from google_auth_oauthlib.flow import Flow


router = Router()
_repo: Repo | None = None
_cfg: Config | None = None


class YTAutoStates(StatesGroup):
    waiting_video = State()
    waiting_title = State()
    waiting_description = State()
    waiting_timezone = State()
    waiting_schedule_time = State()


def setup(repo: Repo, cfg: Config):
    global _repo, _cfg
    _repo = repo
    _cfg = cfg


@router.callback_query(F.data == "yt:auto:noop")
async def yt_noop(call: CallbackQuery):
    await call.answer()


@router.callback_query(F.data == "yt:auto:menu")
async def yt_auto_menu(call: CallbackQuery, state: FSMContext):
    await state.clear()
    token = await _repo.yt_get_token(call.from_user.id)
    is_connected = bool(token)
    txt = "🤖 <b>Avtomatlashtirilgan YouTube</b>\n\nQuyidagilardan birini tanlang 👇"
    await call.message.edit_text(txt, reply_markup=yt_auto_menu_kb(is_connected=is_connected))
    await call.answer()


@router.callback_query(F.data == "yt:auto:connect")
async def yt_auto_connect(call: CallbackQuery):
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
    await call.answer()
    await _repo.yt_disconnect(call.from_user.id)
    await state.clear()
    await call.message.answer("✅ Ulanish uzildi.")


@router.callback_query(F.data == "yt:auto:upload")
async def yt_auto_upload_start(call: CallbackQuery, state: FSMContext):
    await call.answer()
    token = await _repo.yt_get_token(call.from_user.id)
    if not token:
        await call.message.answer("❗️ Avval kanalni ulang (Kanalni ulash).")
        return

    await state.clear()
    await state.set_state(YTAutoStates.waiting_video)
    await call.message.answer("📤 Videoni yuboring (Telegram video yoki document).")


@router.message(YTAutoStates.waiting_video)
async def yt_auto_got_video(message: Message, state: FSMContext):
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
    await state.set_state(YTAutoStates.waiting_title)
    await message.answer("✍️ Video sarlavhasini (Title) yozing:")


@router.message(YTAutoStates.waiting_title)
async def yt_auto_got_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("❗️ Title bo‘sh bo‘lmasin.")
        return
    await state.update_data(title=title)
    await state.set_state(YTAutoStates.waiting_description)
    await message.answer("📝 Description (ixtiyoriy). Bo‘sh qoldirish uchun <code>-</code> yuboring:")


@router.message(F.text, F.reply_to_message)
async def yt_auto_reply_without_state(message: Message, state: FSMContext):
    cur = await state.get_state()
    if cur:
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


@router.message(YTAutoStates.waiting_description)
async def yt_auto_got_description(message: Message, state: FSMContext):
    desc = (message.text or "").strip()
    if desc == "-":
        desc = ""
    await state.update_data(description=desc)
    await message.answer("🔒 Visibility tanlang:", reply_markup=yt_visibility_kb())


@router.callback_query(F.data.startswith("yt:auto:vis:"))
async def yt_auto_set_visibility(call: CallbackQuery, state: FSMContext):
    await call.answer()
    vis = (call.data or "").split(":")[-1]
    if vis not in ("public", "unlisted", "private"):
        vis = "private"
    await state.update_data(visibility=vis)
    await state.set_state(YTAutoStates.waiting_timezone)
    await call.message.answer(
        "🌍 Timezone yozing (masalan: <code>Asia/Tashkent</code>).\n"
        "Ro‘yxat: https://en.wikipedia.org/wiki/List_of_tz_database_time_zones",
        disable_web_page_preview=True,
    )


@router.message(YTAutoStates.waiting_timezone)
async def yt_auto_got_timezone(message: Message, state: FSMContext):
    tz = (message.text or "").strip()
    if not tz:
        await message.answer("❗️ Timezone bo‘sh bo‘lmasin.")
        return
    await state.update_data(timezone=tz)
    await message.answer("⏰ Qachon yuklaymiz?", reply_markup=yt_schedule_choice_kb())


@router.callback_query(F.data == "yt:auto:sched:now")
async def yt_auto_schedule_now(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await _finalize_upload(call.message, state, scheduled_at=None)


@router.callback_query(F.data == "yt:auto:sched:set")
async def yt_auto_schedule_set(call: CallbackQuery, state: FSMContext):
    await call.answer()
    await state.set_state(YTAutoStates.waiting_schedule_time)
    await call.message.answer("📅 Vaqt kiriting: <code>YYYY-MM-DD HH:MM</code> (timezone bo‘yicha)")


@router.message(YTAutoStates.waiting_schedule_time)
async def yt_auto_got_schedule_time(message: Message, state: FSMContext):
    data = await state.get_data()
    tz = str(data.get("timezone") or "").strip()
    raw = (message.text or "").strip()
    try:
        utc_dt = to_utc_sqlite_datetime(raw, tz)
    except Exception as e:
        await message.answer(f"❌ Vaqt xato: <code>{str(e)[:200]}</code>")
        return

    await _finalize_upload(message, state, scheduled_at=utc_dt)


async def _finalize_upload(message: Message, state: FSMContext, scheduled_at: str | None):
    data = await state.get_data()

    file_path = str(data.get("file_path") or "").strip()
    title = str(data.get("title") or "").strip()
    description = str(data.get("description") or "").strip()
    visibility = str(data.get("visibility") or "private").strip()
    timezone = str(data.get("timezone") or "").strip()

    if not file_path or not os.path.exists(file_path):
        await message.answer("❌ Video topilmadi. Qaytadan yuboring.")
        await state.clear()
        return

    upload_id = await _repo.yt_create_pending_upload(
        user_id=message.from_user.id,
        file_path=file_path,
        title=title,
        description=description,
        visibility=visibility,
        timezone=timezone,
        scheduled_at=scheduled_at,
    )

    await state.clear()

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
