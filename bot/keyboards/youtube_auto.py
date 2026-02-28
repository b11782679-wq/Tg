from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def yt_auto_menu_kb(is_connected: bool) -> InlineKeyboardMarkup:
    buttons: list[list[InlineKeyboardButton]] = []

    if is_connected:
        buttons.append([InlineKeyboardButton(text="🔌 Ulanilgan", callback_data="yt:auto:noop")])
    else:
        buttons.append([InlineKeyboardButton(text="🔗 Kanalni ulash", callback_data="yt:auto:connect")])

    buttons.append([InlineKeyboardButton(text="📤 Video yuklash", callback_data="yt:auto:upload")])
    buttons.append([InlineKeyboardButton(text="🗓 Rejalashtirilgan videolar", callback_data="yt:auto:pending")])
    buttons.append([InlineKeyboardButton(text="🔌 Ulanishni uzish", callback_data="yt:auto:disconnect")])
    buttons.append([InlineKeyboardButton(text="🔙 Ortga", callback_data="youtuber:open")])

    return InlineKeyboardMarkup(inline_keyboard=buttons)


def yt_visibility_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🌐 Public", callback_data="yt:auto:vis:public"),
                InlineKeyboardButton(text="🔗 Unlisted", callback_data="yt:auto:vis:unlisted"),
            ],
            [
                InlineKeyboardButton(text="🔒 Private", callback_data="yt:auto:vis:private"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:menu"),
            ],
        ]
    )


def yt_schedule_choice_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="⚡ Hozir", callback_data="yt:auto:sched:now"),
                InlineKeyboardButton(text="⏰ Vaqt belgilash", callback_data="yt:auto:sched:set"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:menu"),
            ],
        ]
    )
