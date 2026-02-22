from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import t

def top_leaderboard_kb(active: str = "today", lang: str = "uz"):
    kb = InlineKeyboardBuilder()

    kb.button(text=(("✅ " if active == "today" else "") + t(lang, "top.period.today")), callback_data="top:period:today")
    kb.button(text=(("✅ " if active == "week" else "") + t(lang, "top.period.week")), callback_data="top:period:week")
    kb.button(text=(("✅ " if active == "month" else "") + t(lang, "top.period.month")), callback_data="top:period:month")

    kb.button(text=t(lang, "top.period.all"), callback_data="top:period:all")
    kb.button(text=t(lang, "top.contest"), callback_data="top:contest")

    kb.button(text=t(lang, "kb.back"), callback_data="m:home")

    kb.adjust(3, 1, 1, 1)
    return kb.as_markup()

def topup_methods_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "topup.method.manual"), callback_data="t:method:manual")
    kb.button(text=t(lang, "topup.method.ton"), callback_data="t:method:ton")
    kb.button(text=t(lang, "kb.back"), callback_data="m:home")
    kb.adjust(1, 1, 1)
    return kb.as_markup()

def topup_amounts_kb(provider: str, lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    for a in (20000, 50000, 100000, 200000):
        kb.button(text=f"➕ {a:,} so'm".replace(",", " "), callback_data=f"t:amount:{provider}:{a}")
    kb.button(text=t(lang, "kb.other_amount"), callback_data=f"t:custom:{provider}")
    kb.button(text=t(lang, "kb.back"), callback_data="t:open")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()

def manual_topup_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "kb.send_proof"), callback_data="t:send_proof")
    kb.button(text=t(lang, "kb.back"), callback_data="t:open")
    kb.adjust(1, 1)
    return kb.as_markup()

def pay_link_kb(url: str):
    kb = InlineKeyboardBuilder()
    # NOTE: this kb is used for external providers, keep Uzbek by default
    kb.button(text=t("uz", "kb.pay"), url=url)
    kb.button(text=t("uz", "kb.check"), callback_data="t:check")
    kb.button(text=t("uz", "kb.back_menu"), callback_data="m:home")
    kb.adjust(1, 1, 1)
    return kb.as_markup()
