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
                InlineKeyboardButton(text="+10 min", callback_data="yt:auto:sched:preset:10m"),
            ],
            [
                InlineKeyboardButton(text="+1 soat", callback_data="yt:auto:sched:preset:1h"),
                InlineKeyboardButton(text="Ertaga 10:00", callback_data="yt:auto:sched:preset:tom10"),
            ],
            [
                InlineKeyboardButton(text="✍️ Qo‘lda", callback_data="yt:auto:sched:set"),
            ],
            [
                InlineKeyboardButton(text="⚙️ Qo‘shimcha sozlamalar", callback_data="yt:auto:metadata:menu"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:menu"),
            ],
        ]
    )


def yt_timezone_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🇺🇿 Asia/Tashkent", callback_data="yt:auto:tz:Asia/Tashkent"),
                InlineKeyboardButton(text="🌍 UTC", callback_data="yt:auto:tz:UTC"),
            ],
            [
                InlineKeyboardButton(text="🇷🇺 Europe/Moscow", callback_data="yt:auto:tz:Europe/Moscow"),
            ],
            [
                InlineKeyboardButton(text="✍️ Qo‘lda yozish", callback_data="yt:auto:tz:manual"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:vis:back"),
            ],
        ]
    )


def yt_metadata_menu_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="👶 Made for Kids", callback_data="yt:auto:meta:made_for_kids"),
                InlineKeyboardButton(text="🏷️ Teglar", callback_data="yt:auto:meta:tags"),
            ],
            [
                InlineKeyboardButton(text="📁 Kategoriya", callback_data="yt:auto:meta:category"),
                InlineKeyboardButton(text="🌐 Til", callback_data="yt:auto:meta:language"),
            ],
            [
                InlineKeyboardButton(text="📅 Sana", callback_data="yt:auto:meta:recording_date"),
                InlineKeyboardButton(text="📍 Joy", callback_data="yt:auto:meta:video_location"),
            ],
            [
                InlineKeyboardButton(text="📄 Litsenziya", callback_data="yt:auto:meta:licence"),
                InlineKeyboardButton(text="💬 Kommentlar", callback_data="yt:auto:meta:comments"),
            ],
            [
                InlineKeyboardButton(text="🔞 Yosh cheklamasi", callback_data="yt:auto:meta:age_restricted"),
                InlineKeyboardButton(text="💰 Reklama", callback_data="yt:auto:meta:paid_promotion"),
            ],
            [
                InlineKeyboardButton(text="✅ Tayyor", callback_data="yt:auto:sched:choice"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:upload"),
            ],
        ]
    )


def yt_yes_no_kb(callback_prefix: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=f"{callback_prefix}:yes"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data=f"{callback_prefix}:no"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:metadata:menu"),
            ],
        ]
    )


def yt_category_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🎬 Film & Animatsiya", callback_data="yt:auto:meta:cat:film_animation"),
                InlineKeyboardButton(text="🚗 Avto & Transport", callback_data="yt:auto:meta:cat:autos_vehicles"),
            ],
            [
                InlineKeyboardButton(text="🎵 Musiqa", callback_data="yt:auto:meta:cat:music"),
                InlineKeyboardButton(text="🐾 Hayvonlar", callback_data="yt:auto:meta:cat:pets_animals"),
            ],
            [
                InlineKeyboardButton(text="⚽ Sport", callback_data="yt:auto:meta:cat:sports"),
                InlineKeyboardButton(text="🎮 Gaming", callback_data="yt:auto:meta:cat:gaming"),
            ],
            [
                InlineKeyboardButton(text="👥 Odamlar & Bloglar", callback_data="yt:auto:meta:cat:people_blogs"),
                InlineKeyboardButton(text="😂 Komediya", callback_data="yt:auto:meta:cat:comedy"),
            ],
            [
                InlineKeyboardButton(text="📰 Yangiliklar", callback_data="yt:auto:meta:cat:news_politics"),
                InlineKeyboardButton(text="📚 Ta'lim", callback_data="yt:auto:meta:cat:education"),
            ],
            [
                InlineKeyboardButton(text="🔬 Fan & Texnika", callback_data="yt:auto:meta:cat:science_tech"),
                InlineKeyboardButton(text="🔧 Qo'llanma", callback_data="yt:auto:meta:cat:howto_style"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:metadata:menu"),
            ],
        ]
    )


def yt_licence_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="📄 Standard YouTube", callback_data="yt:auto:meta:lic:standard"),
            ],
            [
                InlineKeyboardButton(text="🔄 Creative Commons", callback_data="yt:auto:meta:lic:creative"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:metadata:menu"),
            ],
        ]
    )


def yt_comments_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="💬 Yoqilgan", callback_data="yt:auto:meta:comments:on"),
            ],
            [
                InlineKeyboardButton(text="🚫 O'chirilgan", callback_data="yt:auto:meta:comments:off"),
            ],
            [
                InlineKeyboardButton(text="✅ Tekshiruvdan keyin", callback_data="yt:auto:meta:comments:moderated"),
            ],
            [
                InlineKeyboardButton(text="🔙 Ortga", callback_data="yt:auto:metadata:menu"),
            ],
        ]
    )
