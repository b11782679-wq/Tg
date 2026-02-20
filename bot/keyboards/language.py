from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.i18n import t


def language_kb(lang: str):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "lang.uz"), callback_data="lang:set:uz")
    kb.button(text=t(lang, "lang.en"), callback_data="lang:set:en")
    kb.button(text=t(lang, "lang.ru"), callback_data="lang:set:ru")
    kb.button(text=t(lang, "back"), callback_data="m:home")
    kb.adjust(1, 1, 1, 1)
    return kb.as_markup()
