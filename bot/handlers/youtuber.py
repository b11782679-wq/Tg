import logging
import os
from typing import Any

from aiogram import F, Router
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from bot.db.repo import Repo
from bot.i18n import t
from bot.keyboards.menu import main_menu_kb, back_only_kb
from bot.services import youtube, gemini
from bot.services.youtube import YouTubeError, ChannelNotFoundError, QuotaExceededError
from bot.services.gemini import GeminiError, GeminiTimeoutError

logger = logging.getLogger(__name__)
router = Router()
_repo: Repo | None = None

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
        reply_markup=back_only_kb(lang)
    )
    await state.set_state(YouTuberAuditStates.waiting_for_goal)


@router.message(StateFilter(YouTuberAuditStates.waiting_for_goal))
async def receive_goal(message: Message, state: FSMContext):
    """Receive user's goal."""
    lang = await _repo.get_language(message.from_user.id)
    goal = message.text.strip() if message.text else ""
    
    await state.update_data(goal=goal)
    await message.answer(
        t(lang, "youtuber.ask_problem"),
        reply_markup=back_only_kb(lang)
    )
    await state.set_state(YouTuberAuditStates.waiting_for_problem)


@router.message(StateFilter(YouTuberAuditStates.waiting_for_problem))
async def receive_problem_and_generate_audit(message: Message, state: FSMContext):
    """Receive user's problem and generate the audit."""
    lang = await _repo.get_language(message.from_user.id)
    problem = message.text.strip() if message.text else ""
    
    data = await state.get_data()
    channel_url = data.get("channel_url", "")
    goal = data.get("goal", "")
    
    # Show processing message
    processing_msg = await message.answer(t(lang, "youtuber.processing"))
    
    try:
        # Step 1: Fetch channel data from YouTube API
        channel_data = await youtube.fetch_channel_data(channel_url)
        
        # Step 2: Generate audit with Gemini
        audit_text = await gemini.generate_audit(
            channel_data=channel_data,
            user_goal=goal,
            user_problem=problem,
            lang=lang,
        )
        
        # Step 3: Record usage
        await _record_usage(message.from_user.id)
        
        # Step 4: Send audit (might be long, split if needed)
        await processing_msg.delete()
        await _send_long_message(message, audit_text, lang)
        
        # Show menu again
        await message.answer(
            t(lang, "youtuber.done"),
            reply_markup=main_menu_kb(lang)
        )
        
    except ChannelNotFoundError:
        await processing_msg.delete()
        await message.answer(
            t(lang, "youtuber.channel_not_found"),
            reply_markup=back_only_kb(lang)
        )
    except QuotaExceededError:
        await processing_msg.delete()
        await message.answer(
            t(lang, "youtuber.api_quota_exceeded"),
            reply_markup=back_only_kb(lang)
        )
    except GeminiTimeoutError:
        await processing_msg.delete()
        await message.answer(
            t(lang, "youtuber.timeout"),
            reply_markup=back_only_kb(lang)
        )
    except GeminiError as e:
        logger.error(f"Gemini error for user {message.from_user.id}: {e}")
        await processing_msg.delete()
        await message.answer(
            t(lang, "youtuber.gemini_error"),
            reply_markup=back_only_kb(lang)
        )
    except YouTubeError as e:
        logger.error(f"YouTube API error for user {message.from_user.id}: {e}")
        await processing_msg.delete()
        await message.answer(
            t(lang, "youtuber.youtube_error"),
            reply_markup=back_only_kb(lang)
        )
    except Exception as e:
        logger.exception(f"Unexpected error in youtuber audit: {e}")
        await processing_msg.delete()
        await message.answer(
            t(lang, "youtuber.generic_error"),
            reply_markup=back_only_kb(lang)
        )
    finally:
        await state.clear()


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
    """Send long message split into chunks if needed."""
    MAX_LENGTH = 4000  # Leave room for formatting
    
    if len(text) <= MAX_LENGTH:
        await message.answer(text)
        return
    
    # Split by sections (assuming markdown headers)
    chunks = []
    current_chunk = ""
    
    lines = text.split("\n")
    for line in lines:
        if len(current_chunk) + len(line) + 1 > MAX_LENGTH:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line + "\n"
        else:
            current_chunk += line + "\n"
    
    if current_chunk:
        chunks.append(current_chunk)
    
    for i, chunk in enumerate(chunks):
        await message.answer(chunk)


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
