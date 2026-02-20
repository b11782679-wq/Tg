from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot.constants import REQUIRED_CHANNEL
from bot.keyboards.subscribe import subscribe_kb
from bot.keyboards.menu import main_menu_kb
from bot.utils.subscribe import is_subscribed
from bot.db.repo import Repo
from bot.i18n import t

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
    lang = await msg.bot.get_chat(msg.chat.id) if False else None
    # language is stored per user, this helper is rarely used; keep Uzbek by default
    lang = await msg.bot.get_chat(msg.chat.id) if False else "uz"
    await msg.answer(t(lang, "sub.lock", channel=REQUIRED_CHANNEL), reply_markup=subscribe_kb(lang))


async def show_subscribe_message_callback(call: CallbackQuery):
    lang = await call.bot.get_chat(call.message.chat.id) if False else "uz"
    await call.message.edit_text(
        t(lang, "sub.lock", channel=REQUIRED_CHANNEL),
        reply_markup=subscribe_kb(lang),
    )


def setup(repo: Repo):

    @router.callback_query(F.data == "sub:check")
    async def sub_check(call: CallbackQuery):
        await call.answer()

        ok = await is_subscribed(call.bot, call.from_user.id)
        if not ok:
            lang = await repo.get_language(call.from_user.id)
            await call.message.edit_text(
                t(lang, "sub.lock", channel=REQUIRED_CHANNEL),
                reply_markup=subscribe_kb(lang),
            )
            return

        # ✅ Home menu qaytaramiz
        lang = await repo.get_language(call.from_user.id)
        await call.message.edit_text(
            t(lang, "home", name=call.from_user.full_name or "Foydalanuvchi"),
            reply_markup=main_menu_kb(lang),
        )
