from aiogram.utils.keyboard import InlineKeyboardBuilder

def profile_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🆔 User Id", callback_data="profile:id")
    kb.button(text="💰 Balans", callback_data="profile:balance")
    kb.button(text="⬅️ Ortga", callback_data="m:home")
    kb.adjust(2, 1)
    return kb.as_markup()
