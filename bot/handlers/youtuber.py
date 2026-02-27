import logging
import os
from typing import Any
import asyncio
import re

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.db.repo import Repo
from bot.i18n import t
from bot.keyboards.menu import main_menu_kb, back_only_kb
from bot.keyboards.youtuber import goal_selection_kb, problem_selection_kb, confirm_audit_kb, audit_issues_kb
from bot.services import youtube, gemini
from bot.services.youtube import YouTubeError, ChannelNotFoundError, QuotaExceededError
from bot.services.gemini import GeminiError, GeminiTimeoutError

logger = logging.getLogger(__name__)
router = Router()
_repo: Repo | None = None

_LAST_AUDITS: dict[int, dict[str, Any]] = {}

AUDIT_TOTAL_TIMEOUT_SECONDS = int(os.getenv("YOUTUBER_TOTAL_TIMEOUT", "180"))

# Daily usage limit per user
DAILY_AUDIT_LIMIT = int(os.getenv("YOUTUBER_DAILY_LIMIT", "3"))


def setup(repo: Repo) -> None:
    global _repo
    _repo = repo


class YouTuberAuditStates(StatesGroup):
    waiting_for_link = State()
    waiting_for_goal = State()
    waiting_for_problem = State()
    confirming = State()


@router.callback_query(F.data == "youtuber:open")
async def open_youtuber_menu(call: CallbackQuery, state: FSMContext):
    """Open the YouTuber audit menu."""
    lang = await _repo.get_language(call.from_user.id)
    
    # Check daily limit
    usage_count = await _get_daily_usage(call.from_user.id)
    if usage_count >= DAILY_AUDIT_LIMIT:
        await call.message.edit_text(
            t(lang, "youtuber.limit_reached", limit=DAILY_AUDIT_LIMIT),
            reply_markup=main_menu_kb(lang)
        )
        await call.answer()
        return
    
    await call.message.edit_text(
        t(lang, "youtuber.welcome", used=usage_count, limit=DAILY_AUDIT_LIMIT),
        reply_markup=back_only_kb(lang)
    )
    await call.answer()
    await state.set_state(YouTuberAuditStates.waiting_for_link)


@router.message(StateFilter(YouTuberAuditStates.waiting_for_link))
async def receive_channel_link(message: Message, state: FSMContext):
    """Receive YouTube channel link from user."""
    lang = await _repo.get_language(message.from_user.id)
    channel_url = message.text.strip() if message.text else ""
    
    if not channel_url or not _is_valid_youtube_url(channel_url):
        await message.answer(
            t(lang, "youtuber.invalid_link"),
            reply_markup=back_only_kb(lang)
        )
        return
    
    await state.update_data(channel_url=channel_url)
    await message.answer(
        t(lang, "youtuber.ask_goal"),
        reply_markup=goal_selection_kb(lang)
    )
    await state.set_state(YouTuberAuditStates.waiting_for_goal)


@router.callback_query(F.data.startswith("goal:"), StateFilter(YouTuberAuditStates.waiting_for_goal))
async def receive_goal_callback(call: CallbackQuery, state: FSMContext):
    """Receive user's goal from inline keyboard."""
    logger.info(f"Goal callback received: {call.data} from user {call.from_user.id}")
    lang = await _repo.get_language(call.from_user.id)
    goal_key = call.data.split(":")[1]
    
    # Map goal keys to full text
    goal_map = {
        "subscribers": "Ko'p obunachi",
        "views": "Ko'p ko'rish",
        "monetization": "Monetizatsiya",
        "other": "Boshqa",
    }
    goal = goal_map.get(goal_key, goal_key)
    
    await state.update_data(goal=goal, goal_key=goal_key)
    await state.set_state(YouTuberAuditStates.waiting_for_problem)
    await call.message.edit_text(
        t(lang, "youtuber.ask_problem"),
        reply_markup=problem_selection_kb(lang)
    )
    await call.answer()


@router.callback_query(F.data.startswith("problem:"), StateFilter(YouTuberAuditStates.waiting_for_problem))
async def receive_problem_callback(call: CallbackQuery, state: FSMContext):
    """Receive user's problem from inline keyboard and generate audit."""
    logger.info(f"Problem callback received: {call.data} from user {call.from_user.id}")
    lang = await _repo.get_language(call.from_user.id)
    problem_key = call.data.split(":")[1]
    
    # Map problem keys to full text
    problem_map = {
        "views": "Views past",
        "retention": "Retention kam",
        "ctr": "CTR past",
        "shorts": "Shorts ishlmayapti",
        "other": "Boshqa",
    }
    problem = problem_map.get(problem_key, problem_key)
    
    await state.update_data(problem=problem, problem_key=problem_key)
    
    # Show confirmation and start processing
    await call.message.edit_text(
        t(lang, "youtuber.processing"),
        reply_markup=None
    )
    await call.answer()
    
    # Get all data and generate audit
    data = await state.get_data()
    await _generate_and_send_audit(call.message, data, lang, state)


async def _generate_and_send_audit(
    message: Message,
    data: dict[str, Any],
    lang: str,
    state: FSMContext
) -> None:
    """Generate and send the audit report."""
    channel_url = data.get("channel_url", "")
    goal = data.get("goal", "")
    problem = data.get("problem", "")
    
    processing_msg = await message.answer(t(lang, "youtuber.processing"))

    try:
        async def _do_work() -> tuple[dict[str, Any], str]:
            channel_data = await youtube.fetch_channel_data(channel_url)
            audit_text = await gemini.generate_audit(
                channel_data=channel_data,
                user_goal=goal,
                user_problem=problem,
                lang=lang,
            )
            return channel_data, audit_text

        channel_data, audit_text = await asyncio.wait_for(
            _do_work(),
            timeout=float(AUDIT_TOTAL_TIMEOUT_SECONDS),
        )

        await _record_usage(message.from_user.id)

        await _send_long_message(message, audit_text, lang)

        issues = _extract_audit_issues(audit_text)
        if issues:
            _LAST_AUDITS[int(message.from_user.id)] = {
                "channel_data": channel_data,
                "audit_text": audit_text,
                "issues": issues,
                "lang": lang,
            }
            await message.answer(
                "👇 Kamchilikni tanlang (batafsil tushuntirish uchun):",
                reply_markup=audit_issues_kb(issues, lang),
            )

        await message.answer(
            t(lang, "youtuber.done"),
        )

    except asyncio.TimeoutError:
        await message.answer(
            t(lang, "youtuber.timeout"),
            reply_markup=back_only_kb(lang)
        )
    except ChannelNotFoundError:
        await message.answer(
            t(lang, "youtuber.channel_not_found"),
            reply_markup=back_only_kb(lang)
        )
    except QuotaExceededError:
        await message.answer(
            t(lang, "youtuber.api_quota_exceeded"),
            reply_markup=back_only_kb(lang)
        )
    except GeminiTimeoutError:
        await message.answer(
            t(lang, "youtuber.timeout"),
            reply_markup=back_only_kb(lang)
        )
    except GeminiError as e:
        logger.error(f"Gemini error for user {message.from_user.id}: {e}")
        await message.answer(
            f"❌ {t(lang, 'youtuber.gemini_error')}\n\n<code>{str(e)[:200]}</code>",
            reply_markup=back_only_kb(lang)
        )
    except YouTubeError as e:
        logger.error(f"YouTube API error for user {message.from_user.id}: {e}")
        await message.answer(
            t(lang, "youtuber.youtube_error"),
            reply_markup=back_only_kb(lang)
        )
    except Exception as e:
        logger.exception(f"Unexpected error in youtuber audit: {e}")
        await message.answer(
            f"{t(lang, 'youtuber.generic_error')}\n\n<code>{str(e)[:250]}</code>",
            reply_markup=back_only_kb(lang)
        )
    finally:
        try:
            await processing_msg.delete()
        except Exception:
            pass
        await state.clear()


@router.callback_query(F.data.startswith("audit_issue:"))
async def audit_issue_detail(call: CallbackQuery):
    if _repo is None:
        await call.answer("Xatolik: tizim sozlanmagan", show_alert=True)
        return

    lang = await _repo.get_language(call.from_user.id)
    payload = _LAST_AUDITS.get(int(call.from_user.id))
    if not payload:
        await call.answer("Ma'lumot topilmadi. Qaytadan audit qiling.", show_alert=True)
        return

    try:
        idx = int(call.data.split(":", 1)[1])
    except Exception:
        await call.answer("Noto'g'ri tanlov", show_alert=True)
        return

    issues: list[str] = payload.get("issues") or []
    if idx < 0 or idx >= len(issues):
        await call.answer("Noto'g'ri tanlov", show_alert=True)
        return

    issue_title = issues[idx]
    await call.answer()
    await call.message.answer("⏳ Batafsil tahlil tayyorlanyapti...")

    try:
        detail = await gemini.generate_audit_detail(
            channel_data=payload.get("channel_data") or {},
            issue_title=issue_title,
            audit_text=payload.get("audit_text") or "",
            lang=lang,
        )
        await _send_long_message(call.message, detail, lang)
    except GeminiTimeoutError:
        await call.message.answer(t(lang, "youtuber.timeout"), reply_markup=back_only_kb(lang))
    except GeminiError as e:
        await call.message.answer(
            f"❌ {t(lang, 'youtuber.gemini_error')}\n\n<code>{str(e)[:400]}</code>",
            reply_markup=back_only_kb(lang),
        )


def _extract_audit_issues(audit_text: str) -> list[str]:
    if not audit_text:
        return []

    issues: list[str] = []
    for raw in audit_text.splitlines():
        line = (raw or "").strip()
        if not line:
            continue

        if re.match(r"^[^\w\s]\s*\d+\.", line):
            issues.append(line)
            continue
        if re.match(r"^\d+\.", line):
            issues.append(line)

    seen: set[str] = set()
    out: list[str] = []
    for it in issues:
        if it in seen:
            continue
        seen.add(it)
        out.append(it)
    return out


@router.callback_query(F.data == "m:home", StateFilter(YouTuberAuditStates))
async def cancel_youtuber_flow(call: CallbackQuery, state: FSMContext):
    """Cancel the flow and return to main menu."""
    lang = await _repo.get_language(call.from_user.id)
    await state.clear()
    await call.message.edit_text(
        t(lang, "menu.back"),
        reply_markup=main_menu_kb(lang)
    )
    await call.answer()


def _is_valid_youtube_url(url: str) -> bool:
    """Check if URL is a valid YouTube channel URL or handle."""
    if not url:
        return False
    url = url.lower()
    valid_patterns = [
        "youtube.com",
        "youtu.be",
        "@",
        "channel/",
        "c/",
        "user/",
    ]
    # Also accept @username format without full URL
    if url.startswith("@") and len(url) > 1:
        return True
    # Check if it's a channel ID format (UC...)
    if url.startswith("uc") and len(url) == 24:
        return True
    return any(pattern in url for pattern in valid_patterns)


async def _send_long_message(message: Message, text: str, lang: str):
    """Send long message split into chunks by sections."""
    MAX_LENGTH = 4000  # Leave room for formatting

    def _is_section_header(line: str) -> bool:
        l = (line or "").strip()
        if not l:
            return False
        if l.startswith("**") or l.startswith("##") or l.startswith("==="):
            return True
        if l.startswith("---"):
            return True
        if re.match(r"^[^\w\s]\s*\d+\.", l):
            return True
        return False

    def _hard_split(chunk: str) -> list[str]:
        s = (chunk or "").strip()
        if not s:
            return []
        if len(s) <= MAX_LENGTH:
            return [s]
        out: list[str] = []
        rest = s
        while len(rest) > MAX_LENGTH:
            cut = rest.rfind("\n", 0, MAX_LENGTH)
            if cut < 100:
                cut = rest.rfind(" ", 0, MAX_LENGTH)
            if cut < 100:
                cut = MAX_LENGTH
            out.append(rest[:cut].strip())
            rest = rest[cut:].strip()
        if rest:
            out.append(rest)
        return out

    if len(text) <= MAX_LENGTH:
        await message.answer(text)
        return

    sections: list[str] = []
    current_section = ""
    for raw_line in (text or "").split("\n"):
        line = raw_line.rstrip("\r")
        if _is_section_header(line) and current_section.strip():
            sections.append(current_section.strip())
            current_section = line + "\n"
        else:
            current_section += line + "\n"
    if current_section.strip():
        sections.append(current_section.strip())

    chunks: list[str] = []
    current_chunk = ""
    for section in sections:
        if not current_chunk:
            current_chunk = section
            continue

        if len(current_chunk) + len(section) + 2 > MAX_LENGTH:
            chunks.extend(_hard_split(current_chunk))
            current_chunk = section
        else:
            current_chunk += "\n\n" + section
    if current_chunk:
        chunks.extend(_hard_split(current_chunk))

    for chunk in chunks:
        if not chunk:
            continue
        await message.answer(chunk)
        await asyncio.sleep(0.1)


async def _get_daily_usage(user_id: int) -> int:
    """Get today's audit usage count for user."""
    # TODO: Implement in repo if needed
    # For now, simple in-memory or skip
    return 0


async def _record_usage(user_id: int) -> None:
    """Record an audit usage for today."""
    # TODO: Implement in repo if needed
    pass


import os  # noqa: E402
