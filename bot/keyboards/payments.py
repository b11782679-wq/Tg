from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.utils.keyboard import InlineKeyboardBuilder

def top_leaderboard_kb(active: str = "today"):
    kb = InlineKeyboardBuilder()

    kb.button(text=("✅ Bugun" if active == "today" else "Bugun"), callback_data="top:period:today")
    kb.button(text=("✅ Shu Hafta" if active == "week" else "Shu Hafta"), callback_data="top:period:week")
    kb.button(text=("✅ Shu Oy" if active == "month" else "Shu Oy"), callback_data="top:period:month")

    kb.button(text="Barcha vaqt", callback_data="top:period:all")
    kb.button(text="Konkurs", callback_data="top:contest")

    kb.button(text="⬅️ Ortga", callback_data="m:home")

    kb.adjust(3, 1, 1, 1)
    return kb.as_markup()

def topup_methods_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text=" Admin orqali", callback_data="t:method:manual")
    kb.button(text="⬅️ Ortga", callback_data="m:home")
    kb.adjust(1, 1)
    return kb.as_markup()

def topup_amounts_kb(provider: str):
    kb = InlineKeyboardBuilder()
    for a in (20000, 50000, 100000, 200000):
        kb.button(text=f"➕ {a:,} so'm".replace(",", " "), callback_data=f"t:amount:{provider}:{a}")
    kb.button(text="✍️ Boshqa miqdor kiritish", callback_data=f"t:custom:{provider}")
    kb.button(text="⬅️ Ortga", callback_data="t:open")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()

def manual_topup_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Chek yuborish", callback_data="t:send_proof")
    kb.button(text="⬅️ Ortga", callback_data="t:open")
    kb.adjust(1, 1)
    return kb.as_markup()

def pay_link_kb(url: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ To‘lash", url=url)
    kb.button(text="🔄 Tekshirish", callback_data="t:check")
    kb.button(text="⬅️ Menyu", callback_data="m:home")
    kb.adjust(1, 1, 1)
    return kb.as_markup()
