from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.constants import REQUIRED_CHANNEL
from bot.i18n import t

def subscribe_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "sub.join"), url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")
    kb.button(text=t(lang, "sub.check"), callback_data="sub:check")
    kb.adjust(1, 1)
    return kb.as_markup()
