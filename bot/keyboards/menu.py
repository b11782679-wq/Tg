from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import t

ADMIN_USERNAME = "behruz_0887"

def main_menu_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()

    kb.button(text=t(lang, "menu.gemine"), callback_data="p:open:gemine")
    kb.button(text=t(lang, "menu.chatgpt"), callback_data="p:open:chatgpt_business")
    kb.button(text=t(lang, "menu.chatgpt_plus"), callback_data="p:open:chatgpt_plus")
    kb.button(text=t(lang, "menu.super_grok"), callback_data="p:open:super_grok")
    kb.button(text=t(lang, "menu.canva_pro"), callback_data="p:open:canva_pro")
    kb.button(text=t(lang, "menu.capcut_pro"), callback_data="p:open:capcut_pro")

    kb.button(text=t(lang, "menu.topup"), callback_data="t:open")
    kb.button(text=t(lang, "menu.top"), callback_data="top:open")

    kb.button(text=t(lang, "menu.settings"), callback_data="settings:open")

    kb.adjust(2, 2, 2, 2, 1)
    return kb.as_markup()


def settings_menu_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()

    kb.button(text=t(lang, "menu.profile"), callback_data="profile")
    kb.button(text=t(lang, "menu.referral"), callback_data="referral")
    kb.button(text=t(lang, "menu.language"), callback_data="lang:open")
    kb.button(text=t(lang, "menu.stats"), callback_data="stats")

    kb.button(text=t(lang, "menu.contact_admin"), url=f"https://t.me/{ADMIN_USERNAME}")
    kb.button(text=t(lang, "back"), callback_data="m:home")

    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()

def back_only_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "back"), callback_data="m:home")
    kb.adjust(1)
    return kb.as_markup()
