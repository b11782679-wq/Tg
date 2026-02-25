"""Keyboards for YouTuber audit feature."""

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def goal_selection_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """Keyboard for selecting YouTube channel goal."""
    buttons = [
        [
            InlineKeyboardButton(text="📈 Ko'p obunachi", callback_data="goal:subscribers"),
        ],
        [
            InlineKeyboardButton(text="👁 Ko'p ko'rish", callback_data="goal:views"),
        ],
        [
            InlineKeyboardButton(text="💰 Monetizatsiya", callback_data="goal:monetization"),
        ],
        [
            InlineKeyboardButton(text="📝 Boshqa...", callback_data="goal:other"),
        ],
        [
            InlineKeyboardButton(text="🔙 Ortga", callback_data="m:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def problem_selection_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """Keyboard for selecting YouTube channel problems."""
    buttons = [
        [
            InlineKeyboardButton(text="📉 Views past", callback_data="problem:views"),
        ],
        [
            InlineKeyboardButton(text="⏱ Retention kam", callback_data="problem:retention"),
        ],
        [
            InlineKeyboardButton(text="🖱 CTR past", callback_data="problem:ctr"),
        ],
        [
            InlineKeyboardButton(text="📱 Shorts ishlmayapti", callback_data="problem:shorts"),
        ],
        [
            InlineKeyboardButton(text="📝 Boshqa...", callback_data="problem:other"),
        ],
        [
            InlineKeyboardButton(text="🔙 Ortga", callback_data="m:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confirm_audit_kb(lang: str = "uz") -> InlineKeyboardMarkup:
    """Keyboard for confirming audit generation."""
    buttons = [
        [
            InlineKeyboardButton(text="✅ Tahlil qilish", callback_data="audit:confirm"),
            InlineKeyboardButton(text="🔙 Ortga", callback_data="m:home"),
        ],
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
