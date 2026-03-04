from __future__ import annotations
import asyncio
import random
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from pyrogram import Client
from pyrogram.errors import FloodWait, UserPrivacyRestricted, SessionPasswordNeeded, PhoneCodeExpired

from bot.db.repo import Repo
from bot.i18n import t
from bot.keyboards.menu import back_only_kb

router = Router()
_repo: Repo | None = None

# --- FSM HOLATLARI ---
class TelegramAuth(StatesGroup):
    api_id = State()
    api_hash = State()
    phone = State()
    otp = State()
    two_fa = State()
    session_string = State()

class ScraperTask(StatesGroup):
    source_chat = State()
    target_chat = State()

# Foydalanuvchi sessiyalarini vaqtinchalik saqlash
user_clients: dict[int, Client] = {}


async def _safe_disconnect(client: Client) -> None:
    """Xatoliksiz disconnect."""
    try:
        await client.disconnect()
    except Exception:
        pass


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
        client = Client(
            name=f"session_{user_id}",
            api_id=int(saved["api_id"]),
            api_hash=str(saved["api_hash"]),
            session_string=session_string,
            in_memory=True,
        )
        await client.start()
        user_clients[user_id] = client
        return client
    except Exception:
        return None


def setup(repo: Repo) -> None:
    global _repo
    _repo = repo


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


# --- AVTORIZATSIYA HANDLERLARI ---

@router.message(TelegramAuth.api_id)
async def process_api_id(message: Message, state: FSMContext):
    api_id_text = (message.text or "").strip()
    if not api_id_text.isdigit():
        await message.answer("❌ API ID faqat raqamlardan iborat bo'lishi kerak. Qaytadan yuboring:")
        return
    await state.update_data(api_id=api_id_text)
    await message.answer("Endi **API Hash** yuboring:")
    await state.set_state(TelegramAuth.api_hash)


@router.message(TelegramAuth.api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    await state.update_data(api_hash=(message.text or "").strip())
    await message.answer(
        "Telefon raqamingizni yuboring (masalan: +998901234567).\n\n"
        "Agar sizda tayyor **StringSession** bo'lsa, uni ham yuborishingiz mumkin."
    )
    await state.set_state(TelegramAuth.phone)


async def _send_code_with_flood_guard(
    client: Client,
    phone: str,
    message: Message,
    state: FSMContext,
) -> str | None:
    """
    Kod yuboradi. Muvaffaqiyatli bo'lsa phone_code_hash qaytaradi.
    FLOOD_WAIT bo'lsa foydalanuvchiga xabar beradi va None qaytaradi.
    Boshqa xato bo'lsa None qaytaradi.
    """
    try:
        code_info = await client.send_code(phone)
        return code_info.phone_code_hash
    except FloodWait as e:
        wait_sec = int(e.value)
        await message.answer(
            f"⏳ Telegram cheklovi (FLOOD_WAIT).\n\n"
            f"Iltimos, **{wait_sec} soniya** kuting, so'ng telefon raqamni qaytadan yuboring."
        )
        await _safe_disconnect(client)
        user_clients.pop(message.from_user.id, None)
        await state.set_state(TelegramAuth.phone)
        return None
    except Exception as e:
        await message.answer(f"❌ Kod yuborishda xatolik: {e}")
        await _safe_disconnect(client)
        user_clients.pop(message.from_user.id, None)
        await state.set_state(TelegramAuth.phone)
        return None


@router.message(TelegramAuth.phone)
async def process_phone(message: Message, state: FSMContext):
    if _repo is None:
        return

    data = await state.get_data()
    text = (message.text or "").strip()
    if not text:
        await message.answer("Telefon raqam yoki StringSession yuboring.")
        return

    # Agar foydalanuvchi StringSession yuborgan bo'lsa (uzun matn, '+' yo'q)
    if "+" not in text and len(text) > 120:
        session_string = text
        try:
            client = Client(
                name=f"session_{message.from_user.id}",
                api_id=int(data["api_id"]),
                api_hash=str(data["api_hash"]),
                session_string=session_string,
                in_memory=True,
            )
            await client.start()
            user_clients[message.from_user.id] = client
            await _repo.telegram_upsert_session(
                user_id=message.from_user.id,
                api_id=int(data["api_id"]),
                api_hash=str(data["api_hash"]),
                session_string=session_string,
            )
            await message.answer(
                "Akkaunt ulandi! ✅\n\nEndi a'zolarni ko'chirish uchun **Manba guruh** (Source) ID yoki Username yuboring:"
            )
            await state.set_state(ScraperTask.source_chat)
        except Exception as e:
            await message.answer(f"❌ StringSession xatoligi: {e}\n\nQaytadan urinib ko'ring.")
        return

    phone = text
    await state.update_data(phone=phone, otp_expired_attempts=0)

    # Oldingi client qolgan bo'lsa tozalab ketamiz
    old_client = user_clients.pop(message.from_user.id, None)
    if old_client:
        await _safe_disconnect(old_client)

    client = Client(
        name=f"session_{message.from_user.id}",
        api_id=int(data["api_id"]),
        api_hash=str(data["api_hash"]),
        in_memory=True,
    )

    try:
        await client.connect()
    except Exception as e:
        await message.answer(f"❌ Ulanishda xatolik: {e}")
        return

    # Clientni darhol saqlaymiz — send_code FLOOD_WAIT bersa ham disconnect qilinsin
    user_clients[message.from_user.id] = client

    phone_code_hash = await _send_code_with_flood_guard(client, phone, message, state)
    if phone_code_hash is None:
        # _send_code_with_flood_guard ichida client disconnect va state o'zgartirilgan
        return

    await state.update_data(phone_code_hash=phone_code_hash)
    await message.answer("📩 Telegramdan kelgan tasdiqlash kodini yuboring:")
    await state.set_state(TelegramAuth.otp)


@router.message(TelegramAuth.otp)
async def process_otp(message: Message, state: FSMContext):
    if _repo is None:
        return

    data = await state.get_data()
    client = user_clients.get(message.from_user.id)
    if not client:
        await message.answer("❌ Sessiya topilmadi. Qaytadan boshlang.")
        await state.clear()
        return

    phone = str(data.get("phone") or "").strip()
    phone_code_hash = str(data.get("phone_code_hash") or "").strip()
    otp = (message.text or "").strip().replace(" ", "").replace("-", "")
    expired_attempts = int(data.get("otp_expired_attempts") or 0)

    try:
        await client.sign_in(phone, phone_code_hash, otp)

    except PhoneCodeExpired:
        expired_attempts += 1
        await state.update_data(otp_expired_attempts=expired_attempts)

        MAX_RETRIES = 3
        if expired_attempts >= MAX_RETRIES:
            await message.answer(
                f"❌ Kod {MAX_RETRIES} marta eskirib qoldi.\n\n"
                "Iltimos, /start orqali qaytadan boshlang va yangi kod kelishi bilan darhol yuboring."
            )
            await _safe_disconnect(client)
            user_clients.pop(message.from_user.id, None)
            await state.clear()
            return

        # Yangi kod so'raymiz — client hali ulangan bo'lishi kerak
        # Agar client uzilgan bo'lsa, qayta ulaymiz
        if not client.is_connected:
            try:
                await client.connect()
            except Exception as e:
                await message.answer(f"❌ Qayta ulanishda xatolik: {e}\n\nQaytadan boshlang.")
                user_clients.pop(message.from_user.id, None)
                await state.clear()
                return

        new_hash = await _send_code_with_flood_guard(client, phone, message, state)
        if new_hash is None:
            # FLOOD_WAIT — foydalanuvchiga aytildi, state o'zgardi
            return

        await state.update_data(phone_code_hash=new_hash)
        remaining = MAX_RETRIES - expired_attempts
        await message.answer(
            f"⚠️ Kodning muddati tugagan. Yangi kod yuborildi.\n"
            f"Yangi tasdiqlash kodini yuboring: (Urinish: {expired_attempts}/{MAX_RETRIES}, {remaining} ta imkoniyat qoldi)"
        )
        await state.set_state(TelegramAuth.otp)
        return

    except SessionPasswordNeeded:
        await message.answer("🔐 Ikki bosqichli parol (2FA) so'ralmoqda. Parolni yuboring:")
        await state.set_state(TelegramAuth.two_fa)
        return

    except FloodWait as e:
        wait_sec = int(e.value)
        await message.answer(
            f"⏳ Telegram cheklovi (FLOOD_WAIT).\n\n"
            f"**{wait_sec} soniya** kuting, keyin kodni qaytadan yuboring."
        )
        # State o'zgartirmaymiz — foydalanuvchi kutib, OTPni qaytadan yuboradi
        return

    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
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
        await message.answer("❌ Sessiya topilmadi. Qaytadan boshlang.")
        await state.clear()
        return

    try:
        await client.check_password(str(message.text or ""))
    except FloodWait as e:
        wait_sec = int(e.value)
        await message.answer(
            f"⏳ Telegram cheklovi (FLOOD_WAIT).\n\n"
            f"**{wait_sec} soniya** kuting, keyin parolni qaytadan yuboring."
        )
        return
    except Exception as e:
        await message.answer(f"❌ Parol noto'g'ri: {e}\n\nQaytadan yuboring:")
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


# --- KO'CHIRISH HANDLERLARI ---

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
        await message.answer("❌ Sessiya topilmadi. Qaytadan boshlang.")
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
                    await status_msg.edit_text(f"⏳ Holat: {count} ta a'zo qo'shildi...")

                # Tasodifiy kechikish (15–45 soniya)
                await asyncio.sleep(random.randint(15, 45))

            except FloodWait as e:
                wait_sec = int(e.value)
                await message.answer(
                    f"⏳ Telegram cheklovi! **{wait_sec} soniya** kutilmoqda..."
                )
                await asyncio.sleep(wait_sec)
            except UserPrivacyRestricted:
                continue
            except Exception:
                continue

        await message.answer(f"🎉 Tugadi! Jami **{count}** ta a'zo ko'chirildi.")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        await state.clear()
