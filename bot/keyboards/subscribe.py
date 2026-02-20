from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.constants import REQUIRED_CHANNEL

def subscribe_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📢 Kanalga qo‘shilish", url=f"https://t.me/{REQUIRED_CHANNEL.lstrip('@')}")
    kb.button(text="✅ Tekshirish", callback_data="sub:check")
    kb.adjust(1, 1)
    return kb.as_markup()
