from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import t

ADMIN_USERNAME = "behruz_0887"

def main_menu_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()

    kb.button(text=t(lang, "menu.premium"), callback_data="p:menu")

    kb.button(text=t(lang, "menu.topup"), callback_data="t:open")
    kb.button(text=t(lang, "menu.top"), callback_data="top:open")

    kb.button(text=t(lang, "menu.settings"), callback_data="settings:open")

    kb.adjust(1, 2, 1)
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
