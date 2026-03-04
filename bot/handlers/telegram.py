from __future__ import annotations
import asyncio
import random
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message
from pyrogram import Client
from pyrogram.errors import FloodWait, UserPrivacyRestricted

from bot.db.repo import Repo
from bot.i18n import t
from bot.keyboards.menu import back_only_kb

router = Router()
_repo: Repo | None = None

# --- FSM HOLATLARI ---
class TelegramAuth(StatesGroup):
    api_id = State()
    api_hash = State()
    session_string = State()

class ScraperTask(StatesGroup):
    source_chat = State()
    target_chat = State()

# Foydalanuvchi sessiyalarini vaqtinchalik saqlash
user_clients: dict[int, Client] = {}

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
    await state.update_data(api_id=message.text)
    await message.answer("Endi **API Hash** yuboring:")
    await state.set_state(TelegramAuth.api_hash)

@router.message(TelegramAuth.api_hash)
async def process_api_hash(message: Message, state: FSMContext):
    await state.update_data(api_hash=message.text)
    await message.answer(
        "Endi **Pyrogram StringSession** yuboring:\n\n"
        "1) Lokal kompyuteringizda bir marta session yaratasiz\n"
        "2) Chiqadigan session string’ni shu yerga yuborasiz\n\n"
        "Eslatma: Railway serverda SMS/OTP bilan login kodlar tez eskiradi, shuning uchun StringSession kerak."
    )
    await state.set_state(TelegramAuth.session_string)

@router.message(TelegramAuth.session_string)
async def process_session_string(message: Message, state: FSMContext):
    data = await state.get_data()
    session_string = (message.text or "").strip()
    await state.update_data(session_string=session_string)

    try:
        client = Client(
            name=f"session_{message.from_user.id}",
            api_id=int(data["api_id"]),
            api_hash=data["api_hash"],
            session_string=session_string,
            in_memory=True,
        )
        await client.start()
        user_clients[message.from_user.id] = client

        await message.answer(
            "Akkaunt ulandi! ✅\n\nEndi a'zolarni ko'chirish uchun **Manba guruh** (Source) ID yoki Username yuboring:"
        )
        await state.set_state(ScraperTask.source_chat)
    except Exception as e:
        await message.answer(f"Xatolik: {e}")

# --- KO'CHIRISH HANDLERLARI ---

@router.message(ScraperTask.source_chat)
async def process_source(message: Message, state: FSMContext):
    await state.update_data(source_chat=message.text)
    await message.answer("Maqsadli guruh (Target) ID yoki Username yuboring:")
    await state.set_state(ScraperTask.target_chat)

@router.message(ScraperTask.target_chat)
async def process_target(message: Message, state: FSMContext):
    data = await state.get_data()
    source = data['source_chat']
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
                
                # Professional Delay (15-45 soniya)
                await asyncio.sleep(random.randint(15, 45))
                
            except FloodWait as e:
                await message.answer(f"Telegram cheklovi! {e.value} soniya kutish kerak...")
                await asyncio.sleep(e.value)
            except UserPrivacyRestricted:
                continue
            except Exception:
                continue

        await message.answer(f"Tugadi! 🎉 Jami {count} ta a'zo ko'chirildi.")
    except Exception as e:
        await message.answer(f"Xatolik: {e}")
    finally:
        await state.clear()
