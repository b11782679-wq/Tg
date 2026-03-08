from __future__ import annotations
import asyncio
import random
import uuid
from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from pyrogram import Client
from pyrogram.errors import FloodWait, UserPrivacyRestricted, SessionPasswordNeeded, PhoneCodeExpired
from pyrogram.errors import (
    ApiIdInvalid,
    ApiIdPublishedFlood,
    PhoneNumberInvalid,
    PhoneNumberBanned,
    PhoneCodeInvalid,
    PhoneCodeEmpty,
    PhoneNumberFlood,
    PasswordHashInvalid,
)

from bot.db.repo import Repo
from bot.keyboards.menu import back_only_kb

router = Router()
_repo: Repo | None = None


class TelegramAuth(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    otp = State()
    two_fa = State()


class ScraperTask(StatesGroup):
    source_chat = State()
    target_chat = State()


user_clients: dict[int, Client] = {}


def _err_detail(e: BaseException) -> str:
    code = getattr(e, "CODE", None)
    msg = getattr(e, "MESSAGE", None)
    if code is not None or msg is not None:
        return f"({code} {msg})".strip()
    return f"({type(e).__name__})"


def _format_auth_error(e: BaseException) -> str:
    # Most actionable Telegram auth errors first.
    if isinstance(e, FloodWait):
        sec = int(getattr(e, "value", 0) or 0)
        sec = max(sec, 1)
        return (
            "Telegram vaqtincha cheklov qo'ydi: juda ko'p urinish.\n\n"
            f"Kutish kerak: {sec} soniya.\n"
            "Keyin qayta urinib ko'ring."
        )

    if isinstance(e, PhoneNumberBanned):
        return (
            "Bu telefon raqam Telegram tomonidan bloklangan (banned).\n\n"
            "Boshqa raqam bilan urinib ko'ring yoki Telegram support orqali yechib oling."
        )

    if isinstance(e, PhoneNumberInvalid):
        return (
            "Telefon raqam formati noto'g'ri.\n\n"
            "Masalan: +998901234567 ko'rinishida yuboring."
        )

    if isinstance(e, (ApiIdInvalid, ApiIdPublishedFlood)):
        return (
            "API ID / API HASH noto'g'ri yoki Telegram bu API'ni cheklagan.\n\n"
            "my.telegram.org saytidan API ID/HASH ni qayta tekshiring yoki yangisini yarating."
        )

    if isinstance(e, PhoneNumberFlood):
        return (
            "Bu raqam uchun kod yuborish juda ko'p bo'ldi (PHONE_NUMBER_FLOOD).\n\n"
            "Bir necha soat kuting va qayta urinib ko'ring."
        )

    if isinstance(e, PhoneCodeExpired):
        return (
            "Tasdiqlash kodi muddati tugagan.\n\n"
            "Yangi kod so'rang va kelishi bilan 1-2 daqiqada yuboring."
        )

    if isinstance(e, (PhoneCodeInvalid, PhoneCodeEmpty)):
        return (
            "Tasdiqlash kodi noto'g'ri kiritilgan.\n\n"
            "Telegram yuborgan eng oxirgi kodni (5 raqam) aynan o'sha holatda yuboring."
        )

    if isinstance(e, SessionPasswordNeeded):
        return (
            "Akkountda 2FA (ikki bosqichli parol) yoqilgan.\n\n"
            "Davom etish uchun 2FA parolni yuboring."
        )

    if isinstance(e, PasswordHashInvalid):
        return (
            "2FA parol noto'g'ri.\n\n"
            "Parolni to'g'ri kiriting yoki Telegram ilovasida parolni tiklang."
        )

    return f"Noma'lum xatolik {_err_detail(e)}"


def _format_auth_error_full(e: BaseException) -> str:
    """Userga 1-urinishdayoq aniq sabab + texnik RPC detail chiqarish."""
    base = _format_auth_error(e)
    detail = _err_detail(e)
    if detail and detail not in base:
        return base + "\n\nTexnik: " + detail
    return base


# ---------------------------------------------------------------------------
# YORDAMCHI FUNKSIYALAR
# ---------------------------------------------------------------------------

def _make_client(api_id: int, api_hash: str, session_string: str | None = None) -> Client:
    """
    Har safar YANGI unikal nom bilan Client yaratadi.
    Bu Pyrogram local cache / .session fayl konfliktini bartaraf etadi.
    """
    unique_name = f"tg_{uuid.uuid4().hex}"
    kwargs: dict = dict(
        name=unique_name,
        api_id=api_id,
        api_hash=api_hash,
        in_memory=True,
        # Real qurilma kabi ko'rinish uchun
        device_model="Samsung Galaxy S23",
        system_version="Android 13",
        app_version="9.6.7",
        lang_code="uz",
    )
    if session_string:
        kwargs["session_string"] = session_string
    return Client(**kwargs)


async def _safe_disconnect(client: Client) -> None:
    try:
        await client.disconnect()
    except Exception:
        pass


async def _send_code_safe(client: Client, phone: str) -> tuple[str | None, BaseException | None]:
    """
    Returns: (phone_code_hash, None)  — muvaffaqiyatli
             (None, exc)             — xato (FloodWait ham shu yerda)
    """
    try:
        code_info = await client.send_code(phone)
        return code_info.phone_code_hash, None
    except Exception as e:
        return None, e


async def _try_connect_saved_session(user_id: int) -> Client | None:
    if _repo is None:
        return None
    saved = await _repo.telegram_get_session(user_id)
    if not saved:
        return None
    session_string = str(saved.get("session_string") or "").strip()
    if not session_string:
        return None
    try:
        client = _make_client(
            api_id=int(saved["api_id"]),
            api_hash=str(saved["api_hash"]),
            session_string=session_string,
        )
        await client.start()
        user_clients[user_id] = client
        return client
    except Exception:
        return None


def setup(repo: Repo) -> None:
    global _repo
    _repo = repo


# ---------------------------------------------------------------------------
# MENYUNI OCHISH
# ---------------------------------------------------------------------------

@router.callback_query(F.data == "telegram:open")
async def telegram_open(call: CallbackQuery, state: FSMContext):
    if _repo is None:
        await call.answer()
        return

    lang = await _repo.get_language(call.from_user.id)
    await state.clear()

    client = await _try_connect_saved_session(call.from_user.id)
    if client is not None:
        await call.message.edit_text(
            "Akkaunt ulandi! ✅\n\nEndi a'zolarni ko'chirish uchun **Manba guruh** (Source) ID yoki Username yuboring:",
            reply_markup=back_only_kb(lang),
            disable_web_page_preview=True,
        )
        await state.set_state(ScraperTask.source_chat)
        await call.answer()
        return

    await call.message.edit_text(
        "Telegram Scraper & Adder xizmatiga xush kelibsiz!\n\nAkkauntingizni ulash uchun **API ID** yuboring:",
        reply_markup=back_only_kb(lang),
        disable_web_page_preview=True,
    )
    await state.set_state(TelegramAuth.api_id)
    await call.answer()


# ---------------------------------------------------------------------------
# AVTORIZATSIYA
# ---------------------------------------------------------------------------

@router.message(TelegramAuth.api_id)
async def process_api_id(message: Message, state: FSMContext):
    api_id_text = (message.text or "").strip()
    if not api_id_text.isdigit():
        await message.answer("API ID faqat raqamlardan iborat bolishi kerak. Qaytadan yuboring:")
        return
    await state.update_data(api_id=api_id_text)
    await message.answer("Endi **API Hash** yuboring:")
    await state.set_state(TelegramAuth.api_hash)


@router.message(TelegramAuth.api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    await state.update_data(api_hash=(message.text or "").strip())
    await message.answer(
        "Telefon raqamingizni yuboring (masalan: +998901234567).\n\n"
        "Agar sizda tayyor **StringSession** bolsa, uni ham yuborishingiz mumkin."
    )
    await state.set_state(TelegramAuth.phone)


@router.message(TelegramAuth.phone)
async def process_phone(message: Message, state: FSMContext):
    if _repo is None:
        return

    data = await state.get_data()
    text = (message.text or "").strip()
    if not text:
        await message.answer("Telefon raqam yoki StringSession yuboring.")
        return

    # --- StringSession ---
    if "+" not in text and len(text) > 120:
        old = user_clients.pop(message.from_user.id, None)
        if old:
            await _safe_disconnect(old)
        try:
            client = _make_client(
                api_id=int(data["api_id"]),
                api_hash=str(data["api_hash"]),
                session_string=text,
            )
            await client.start()
            user_clients[message.from_user.id] = client
            await _repo.telegram_upsert_session(
                user_id=message.from_user.id,
                api_id=int(data["api_id"]),
                api_hash=str(data["api_hash"]),
                session_string=text,
            )
            await message.answer(
                "Akkaunt ulandi! ✅\n\nEndi a'zolarni ko'chirish uchun **Manba guruh** (Source) ID yoki Username yuboring:"
            )
            await state.set_state(ScraperTask.source_chat)
        except Exception as e:
            await message.answer(_format_auth_error(e))
        return

    # --- Telefon raqam ---
    phone = text
    await state.update_data(phone=phone, otp_expired_attempts=0)

    old = user_clients.pop(message.from_user.id, None)
    if old:
        await _safe_disconnect(old)

    client = _make_client(
        api_id=int(data["api_id"]),
        api_hash=str(data["api_hash"]),
    )

    try:
        await client.connect()
    except Exception as e:
        await message.answer(_format_auth_error_full(e))
        return

    user_clients[message.from_user.id] = client

    phone_code_hash, err = await _send_code_safe(client, phone)

    if err is not None:
        await _safe_disconnect(client)
        user_clients.pop(message.from_user.id, None)
        await message.answer(_format_auth_error_full(err))
        return

    await state.update_data(phone_code_hash=phone_code_hash)
    await message.answer("Telegramdan kelgan tasdiqlash kodini yuboring:")
    await state.set_state(TelegramAuth.otp)


@router.message(TelegramAuth.otp)
async def process_otp(message: Message, state: FSMContext):
    if _repo is None:
        return

    data = await state.get_data()
    client = user_clients.get(message.from_user.id)
    if not client:
        await message.answer("Sessiya topilmadi. Qaytadan boshlang.")
        await state.clear()
        return

    phone = str(data.get("phone") or "").strip()
    phone_code_hash = str(data.get("phone_code_hash") or "").strip()
    otp = (message.text or "").strip().replace(" ", "").replace("-", "")
    expired_attempts = int(data.get("otp_expired_attempts") or 0)
    MAX_RETRIES = 3

    try:
        await client.sign_in(phone, phone_code_hash, otp)

    except PhoneCodeExpired:
        expired_attempts += 1
        await state.update_data(otp_expired_attempts=expired_attempts)

        if expired_attempts >= MAX_RETRIES:
            await message.answer(
                f"Kod {MAX_RETRIES} marta eskirib qoldi.\n\n"
                "Iltimos, /start orqali qaytadan boshlang va yangi kod kelishi bilan darhol yuboring."
            )
            await _safe_disconnect(client)
            user_clients.pop(message.from_user.id, None)
            await state.clear()
            return

        if not client.is_connected:
            try:
                await client.connect()
            except Exception as e:
                await message.answer(_format_auth_error_full(e))
                user_clients.pop(message.from_user.id, None)
                await state.clear()
                return

        new_hash, err = await _send_code_safe(client, phone)
        if err is not None:
            await message.answer(_format_auth_error_full(err))
            return

        await state.update_data(phone_code_hash=new_hash)
        remaining = MAX_RETRIES - expired_attempts
        await message.answer(
            f"Kodning muddati tugagan. Yangi kod yuborildi.\n"
            f"Yangi tasdiqlash kodini yuboring (Urinish: {expired_attempts}/{MAX_RETRIES}, {remaining} ta imkoniyat qoldi):"
        )
        await state.set_state(TelegramAuth.otp)
        return

    except SessionPasswordNeeded:
        await message.answer("Ikki bosqichli parol (2FA) so'ralmoqda. Parolni yuboring:")
        await state.set_state(TelegramAuth.two_fa)
        return

    except FloodWait as e:
        await message.answer(_format_auth_error_full(e))
        return

    except Exception as e:
        await message.answer(_format_auth_error_full(e))
        return

    # Muvaffaqiyatli login
    await state.update_data(otp_expired_attempts=0)
    try:
        session_string = await client.export_session_string()
        await _repo.telegram_upsert_session(
            user_id=message.from_user.id,
            api_id=int(data["api_id"]),
            api_hash=str(data["api_hash"]),
            session_string=session_string,
        )
    except Exception:
        pass

    await message.answer(
        "Akkaunt ulandi! ✅\n\nEndi a'zolarni ko'chirish uchun **Manba guruh** (Source) ID yoki Username yuboring:"
    )
    await state.set_state(ScraperTask.source_chat)


@router.message(TelegramAuth.two_fa)
async def process_2fa(message: Message, state: FSMContext):
    if _repo is None:
        return

    data = await state.get_data()
    client = user_clients.get(message.from_user.id)
    if not client:
        await message.answer("Sessiya topilmadi. Qaytadan boshlang.")
        await state.clear()
        return

    try:
        await client.check_password(str(message.text or ""))
    except FloodWait as e:
        await message.answer(_format_auth_error_full(e))
        return
    except Exception as e:
        await message.answer(_format_auth_error_full(e) + "\n\nQaytadan yuboring:")
        return

    try:
        session_string = await client.export_session_string()
        await _repo.telegram_upsert_session(
            user_id=message.from_user.id,
            api_id=int(data["api_id"]),
            api_hash=str(data["api_hash"]),
            session_string=session_string,
        )
    except Exception:
        pass

    await message.answer(
        "Akkaunt ulandi! ✅\n\nEndi a'zolarni ko'chirish uchun **Manba guruh** (Source) ID yoki Username yuboring:"
    )
    await state.set_state(ScraperTask.source_chat)


# ---------------------------------------------------------------------------
# KO'CHIRISH HANDLERLARI
# ---------------------------------------------------------------------------

@router.message(ScraperTask.source_chat)
async def process_source(message: Message, state: FSMContext):
    await state.update_data(source_chat=message.text)
    await message.answer("Maqsadli guruh (Target) ID yoki Username yuboring:")
    await state.set_state(ScraperTask.target_chat)


@router.message(ScraperTask.target_chat)
async def process_target(message: Message, state: FSMContext):
    data = await state.get_data()
    source = data["source_chat"]
    target = message.text
    client = user_clients.get(message.from_user.id)

    if not client:
        await message.answer("Sessiya topilmadi. Qaytadan boshlang.")
        return

    status_msg = await message.answer("Jarayon boshlandi... 🚀")
    count = 0
    try:
        async for member in client.get_chat_members(source):
            if member.user.is_bot or member.user.is_deleted:
                continue
            try:
                await client.add_chat_members(target, member.user.id)
                count += 1
                if count % 5 == 0:
                    await status_msg.edit_text(f"Holat: {count} ta a'zo qo'shildi...")
                await asyncio.sleep(random.randint(15, 45))
            except FloodWait as e:
                wait_sec = int(e.value)
                await message.answer(f"Telegram cheklovi! {wait_sec} soniya kutilmoqda...")
                await asyncio.sleep(wait_sec)
            except UserPrivacyRestricted:
                continue
            except Exception:
                continue

        await message.answer(f"Tugadi! Jami {count} ta a'zo ko'chirildi.")
    except Exception as e:
        await message.answer(f"Xatolik: {e}")
    finally:
        await state.clear()
