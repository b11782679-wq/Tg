from aiogram.utils.keyboard import InlineKeyboardBuilder

ADMIN_USERNAME = "behruz_0887"

def main_menu_kb():
    kb = InlineKeyboardBuilder()

    kb.button(text="💎 Gemine akkaunt", callback_data="p:open:gemine")
    kb.button(text="🚀 ChatGPT Business", callback_data="p:open:chatgpt_business")

    kb.button(text="💳 Hisob To'ldirish", callback_data="t:open")
    kb.button(text="🏆 Top", callback_data="top:open")

    kb.button(text="📊 Statistikam", callback_data="stats")

    kb.button(text="🎁 Referal", callback_data="referral")
    kb.button(text="👤 Profil", callback_data="profile")

    # ✅ Admin eng pastda va URL orqali ochiladi
    kb.button(text="📞 Admin bilan bog‘lanish", url="https://t.me/behruz_0887")

    kb.adjust(2, 2, 2, 1, 1)
    return kb.as_markup()

def back_only_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ Ortga", callback_data="m:home")
    kb.adjust(1)
    return kb.as_markup()
