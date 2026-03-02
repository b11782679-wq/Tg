from __future__ import annotations

import asyncio
import os
from typing import Optional

from aiogram import Router, F
from aiogram.filters import StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from aiogram.types import BufferedInputFile

from bot.db.repo import Repo
from bot.i18n import t
from bot.keyboards.menu import back_only_kb, main_menu_kb


router = Router()
_repo: Repo | None = None


def setup(repo: Repo) -> None:
    global _repo
    _repo = repo


class TTSStates(StatesGroup):
    waiting_text = State()


def _get_gemini_api_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def _tts_sync(text: str, api_key: str) -> bytes:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model="gemini-2.5-flash-preview-tts",
        contents=text,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Kore",
                    )
                )
            ),
        ),
    )

    return response.candidates[0].content.parts[0].inline_data.data


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

    api_key = _get_gemini_api_key()
    if not api_key:
        await message.answer(t(lang, "tts.error"), reply_markup=back_only_kb(lang))
        await state.clear()
        return

    processing = await message.answer(t(lang, "tts.processing"))

    try:
        wav_bytes = await _generate_tts(text=text, api_key=api_key)
    except Exception:
        try:
            await processing.delete()
        except Exception:
            pass
        await message.answer(t(lang, "tts.error"), reply_markup=back_only_kb(lang))
        await state.clear()
        return

    try:
        await processing.delete()
    except Exception:
        pass

    try:
        audio = BufferedInputFile(wav_bytes, filename="tts.wav")
        await message.answer_audio(audio)
    except Exception:
        await message.answer(t(lang, "tts.error"), reply_markup=back_only_kb(lang))
        await state.clear()
        return

    await state.clear()
    await message.answer(
        t(lang, "home", name=message.from_user.full_name or "Foydalanuvchi"),
        reply_markup=main_menu_kb(lang),
    )
