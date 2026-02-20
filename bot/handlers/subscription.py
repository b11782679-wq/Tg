from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot.constants import REQUIRED_CHANNEL
from bot.keyboards.subscribe import subscribe_kb
from bot.keyboards.menu import main_menu_kb
from bot.utils.subscribe import is_subscribed
from bot.db.repo import Repo

router = Router()


def home_text(full_name: str) -> str:
    name = (full_name or "Foydalanuvchi")
    return (
        "<b>"
        f"👋 Assalomu alaykum, {name} botiga xush kelibsiz!\n\n"
        "🛒 Ushbu bot orqali siz ilova va saytlardagi premium obunalarni arzon narxlarda xarid qilishingiz mumkin.\n\n"
        "🎁 Shuningdek, referal dasturi orqali do‘stlaringizni taklif qiling va bonuslar evaziga akkauntlarga ega bo‘ling!\n\n"
        "📌 Kerakli xizmatni tanlash uchun quyidagi menyudan foydalaning 👇"
        "</b>"
    )


async def show_subscribe_message_message(msg: Message):
    text = (
        "🔒 Botdan foydalanish uchun kanalga a’zo bo‘ling:\n"
        f"{REQUIRED_CHANNEL}\n\n"
        "A’zo bo‘lgach ✅ Tekshirish ni bosing."
    )
    await msg.answer(text, reply_markup=subscribe_kb())


async def show_subscribe_message_callback(call: CallbackQuery):
    text = (
        "🔒 Botdan foydalanish uchun kanalga a’zo bo‘ling:\n"
        f"{REQUIRED_CHANNEL}\n\n"
        "A’zo bo‘lgach ✅ Tekshirish ni bosing."
    )
    await call.message.edit_text(text, reply_markup=subscribe_kb())


def setup(repo: Repo):

    @router.callback_query(F.data == "sub:check")
    async def sub_check(call: CallbackQuery):
        await call.answer()

        ok = await is_subscribed(call.bot, call.from_user.id)
        if not ok:
            await show_subscribe_message_callback(call)
            return

        # ✅ Home menu qaytaramiz
        await call.message.edit_text(
            home_text(call.from_user.full_name),
            reply_markup=main_menu_kb(),
        )
