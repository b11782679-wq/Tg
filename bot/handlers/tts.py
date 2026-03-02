from __future__ import annotations

import asyncio
import base64
import io
import logging
import os
import wave
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


def _get_gemini_api_key() -> str:
    return (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or "").strip()


def _get_gemini_api_keys() -> list[str]:
    raw = (
        os.getenv("GEMINI_API_KEYS")
        or os.getenv("GOOGLE_API_KEYS")
        or os.getenv("GEMINI_API_KEY")
        or os.getenv("GOOGLE_API_KEY")
        or ""
    )
    keys = [k.strip() for k in raw.replace(";", ",").split(",") if k.strip()]
    return keys


def _is_quota_error(exc: Exception) -> bool:
    s = (str(exc) or "").upper()
    return "RESOURCE_EXHAUSTED" in s or "HTTP 429" in s or " 429" in s


def _pcm_to_wav_bytes(pcm: bytes, channels: int = 1, rate: int = 24000, sample_width: int = 2) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(int(channels))
        wf.setsampwidth(int(sample_width))
        wf.setframerate(int(rate))
        wf.writeframes(pcm)
    return buf.getvalue()


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

    candidates = list(getattr(response, "candidates", None) or [])
    for c in candidates:
        content = getattr(c, "content", None)
        parts = list(getattr(content, "parts", None) or []) if content is not None else []
        for p in parts:
            inline = getattr(p, "inline_data", None)
            if inline is None:
                continue
            data = getattr(inline, "data", None)
            if not data:
                continue

            if isinstance(data, str):
                try:
                    data = base64.b64decode(data)
                except Exception:
                    data = data.encode("utf-8", errors="ignore")
            if not isinstance(data, (bytes, bytearray)):
                data = bytes(data)
            return bytes(data)

    # If no inline audio found, raise a descriptive error
    finish_reasons: list[str] = []
    for c in candidates:
        fr = getattr(c, "finish_reason", None)
        if fr is not None:
            finish_reasons.append(str(fr))

    pf = getattr(response, "prompt_feedback", None)
    pf_text = ""
    if pf is not None:
        try:
            pf_text = str(pf)
        except Exception:
            pf_text = ""

    raise RuntimeError(
        "Gemini TTS returned no audio. "
        + (f"finish_reasons={finish_reasons}. " if finish_reasons else "")
        + (f"prompt_feedback={pf_text}" if pf_text else "")
    )


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

    api_keys = _get_gemini_api_keys()
    if not api_keys:
        await message.answer(t(lang, "tts.error"), reply_markup=back_only_kb(lang))
        return

    processing = await message.answer(t(lang, "tts.processing"))

    last_exc: Exception | None = None
    wav_bytes: bytes | None = None
    for api_key in api_keys:
        try:
            pcm_bytes = await _generate_tts(text=text, api_key=api_key)
            wav_bytes = _pcm_to_wav_bytes(pcm_bytes)
            last_exc = None
            break
        except Exception as e:
            last_exc = e
            if _is_quota_error(e) and api_key != api_keys[-1]:
                continue
            break

    if wav_bytes is None:
        e = last_exc or RuntimeError("Unknown TTS error")
        logger.exception("TTS generation failed", exc_info=e)
        try:
            await processing.delete()
        except Exception:
            pass
        if _is_quota_error(e):
            await message.answer(t(lang, "tts.quota"), reply_markup=back_only_kb(lang))
        else:
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
        audio = BufferedInputFile(wav_bytes, filename="tts.wav")
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
