from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Iterable
from typing import Optional

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.types import BufferedInputFile

from bot.db.repo import Repo
from bot.i18n import t
from bot.keyboards.menu import back_only_kb


router = Router()
_repo: Repo | None = None

logger = logging.getLogger(__name__)


def setup(repo: Repo) -> None:
    global _repo
    _repo = repo


class TTSStates(StatesGroup):
    waiting_text = State()


def _get_elevenlabs_api_key() -> str:
    return (os.getenv("ELEVENLABS_API_KEY") or "").strip()


def _tts_sync(text: str, api_key: str) -> bytes:
    from elevenlabs.client import ElevenLabs

    voice_id = (os.getenv("ELEVENLABS_VOICE_ID") or "JBFqnCBsd6RMkjVDRZzb").strip()
    model_id = (os.getenv("ELEVENLABS_MODEL_ID") or "eleven_multilingual_v2").strip()
    output_format = (os.getenv("ELEVENLABS_OUTPUT_FORMAT") or "mp3_44100_128").strip()

    client = ElevenLabs(api_key=api_key)
    audio = client.text_to_speech.convert(
        text=text,
        voice_id=voice_id,
        model_id=model_id,
        output_format=output_format,
    )

    if isinstance(audio, (bytes, bytearray)):
        return bytes(audio)

    # ElevenLabs SDK may return an iterator/stream of chunks
    if isinstance(audio, Iterable) and not isinstance(audio, (str, bytes, bytearray)):
        buf = bytearray()
        for chunk in audio:
            if not chunk:
                continue
            if isinstance(chunk, (bytes, bytearray)):
                buf.extend(chunk)
            else:
                try:
                    buf.extend(bytes(chunk))
                except Exception:
                    continue
        return bytes(buf)

    try:
        return bytes(audio)
    except Exception:
        return b""  # will be handled by caller


async def _generate_tts(text: str, api_key: str, timeout_seconds: float = 40.0) -> bytes:
    return await asyncio.wait_for(asyncio.to_thread(_tts_sync, text, api_key), timeout=timeout_seconds)


@router.callback_query(F.data == "tts:open")
async def tts_open(call: CallbackQuery, state: FSMContext):
    if _repo is None:
        await call.answer()
        return

    lang = await _repo.get_language(call.from_user.id)
    await state.clear()
    await call.message.edit_text(
        t(lang, "tts.open") + "\n\n" + t(lang, "tts.ask_text"),
        reply_markup=back_only_kb(lang),
        disable_web_page_preview=True,
    )
    await call.answer()
    await state.set_state(TTSStates.waiting_text)


@router.message(StateFilter(TTSStates.waiting_text))
async def tts_receive_text(message: Message, state: FSMContext):
    if _repo is None:
        return

    lang = await _repo.get_language(message.from_user.id)

    text = (message.text or "").strip()
    if not text:
        await message.answer(t(lang, "tts.ask_text"), reply_markup=back_only_kb(lang))
        return

    if len(text) > 1200:
        await message.answer(t(lang, "tts.too_long"), reply_markup=back_only_kb(lang))
        return

    api_key = _get_elevenlabs_api_key()
    if not api_key:
        await message.answer(t(lang, "tts.error"), reply_markup=back_only_kb(lang))
        return

    processing = await message.answer(t(lang, "tts.processing"))

    try:
        mp3_bytes = await _generate_tts(text=text, api_key=api_key)
        if not mp3_bytes:
            raise RuntimeError("ElevenLabs returned empty audio")
    except Exception as e:
        logger.exception("TTS generation failed")
        try:
            await processing.delete()
        except Exception:
            pass
        err = str(e)[:250]
        await message.answer(
            t(lang, "tts.error") + (f"\n\n<code>{err}</code>" if err else ""),
            reply_markup=back_only_kb(lang),
        )
        return

    try:
        await processing.delete()
    except Exception:
        pass

    try:
        audio = BufferedInputFile(mp3_bytes, filename="tts.mp3")
        await message.answer_audio(audio)
    except Exception as e:
        logger.exception("Sending TTS audio failed")
        err = str(e)[:250]
        await message.answer(
            t(lang, "tts.error") + (f"\n\n<code>{err}</code>" if err else ""),
            reply_markup=back_only_kb(lang),
        )
        return

    await state.set_state(TTSStates.waiting_text)
