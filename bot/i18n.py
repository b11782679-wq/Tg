from __future__ import annotations

from typing import Any


_LANGS = {"uz", "en", "ru"}


_TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "menu.gemine": "💎 Gemine akkaunt",
        "menu.chatgpt": "🚀 ChatGPT Business",
        "menu.topup": "💳 Hisob To'ldirish",
        "menu.top": "🏆 Top",
        "menu.stats": "📊 Statistikam",
        "menu.referral": "🎁 Referal",
        "menu.profile": "👤 Profil",
        "menu.language": "🌐 Til/Language",
        "menu.contact_admin": "📞 Admin bilan bog‘lanish",
        "back": "⬅️ Ortga",
        "lang.choose": "🌐 Tilni tanlang / Choose language:",
        "lang.uz": "🇺🇿 Uzbek",
        "lang.en": "🇬🇧 English",
        "lang.ru": "🇷🇺 Russian",
        "lang.saved": "✅ Til saqlandi.",
        "home": (
            "<b>"
            "👋 Assalomu alaykum, {name} botiga xush kelibsiz!\n\n"
            "🛒 Ushbu bot orqali siz ilova va saytlardagi premium obunalarni arzon narxlarda xarid qilishingiz mumkin.\n\n"
            "🎁 Shuningdek, referal dasturi orqali do‘stlaringizni taklif qiling va bonuslar evaziga akkauntlarga ega bo‘ling!\n\n"
            "📌 Kerakli xizmatni tanlash uchun quyidagi menyudan foydalaning 👇"
            "</b>"
        ),
        "stats.title": "📊 <b>Statistikam</b>",
        "referral.title": "👥 <b>Referal tizimi</b>",
        "profile.title": "👤 <b>Profil</b>",
        "topup.title": "💳 <b>Hisobni to‘ldirish</b>",
        "topup.open": "💳 Hisob To'ldirish\n\nUsulni tanlang 👇",
        "topup.choose_amount": "💳 Summani tanlang 👇",
        "topup.custom.title": "💳 <b>Boshqa miqdor</b>",
        "topup.custom.body": (
            "Summani xabar qilib yuboring.\n\n"
            "Yuborish formati:\n"
            "- <code>25000</code>\n"
            "- <code>25 000</code>\n\n"
            "Eng kam hisob to‘ldirish miqdori: <b>1000 so'm</b>\n\n"
            "Faqat raqam kiriting (so'm yozmang)."
        ),
        "kb.back_menu": "⬅️ Menyu",
        "kb.back": "⬅️ Ortga",
        "kb.check": "🔄 Tekshirish",
        "kb.pay": "✅ To‘lash",
        "kb.send_proof": "✅ Chek yuborish",
        "kb.other_amount": "✍️ Boshqa miqdor kiritish",
        "top.leaderboard.title": "🏆 <b>Eng Faol Xaridorlar (TOP–5)</b>",
        "top.leaderboard.desc": "📊 Ushbu reytingda belgilangan vaqt oralig‘ida botga eng ko‘p mablag‘ kiritgan foydalanuvchilar joy oladi.",
        "top.period.today": "Bugun",
        "top.period.week": "Shu Hafta",
        "top.period.month": "Shu Oy",
        "top.period.all": "Barcha vaqt",
        "top.contest": "Konkurs",
        "products.buy_points": "🎁 Ball bilan olish (7 ball)",
    },
    "en": {
        "menu.gemine": "💎 Gemini account",
        "menu.chatgpt": "🚀 ChatGPT Business",
        "menu.topup": "💳 Top up balance",
        "menu.top": "🏆 Top",
        "menu.stats": "📊 My stats",
        "menu.referral": "🎁 Referral",
        "menu.profile": "👤 Profile",
        "menu.language": "🌐 Til/Language",
        "menu.contact_admin": "📞 Contact admin",
        "back": "⬅️ Back",
        "lang.choose": "🌐 Choose language:",
        "lang.uz": "🇺🇿 Uzbek",
        "lang.en": "🇬🇧 English",
        "lang.ru": "🇷🇺 Russian",
        "lang.saved": "✅ Language saved.",
        "home": (
            "<b>"
            "👋 Hello, welcome to {name}'s bot!\n\n"
            "🛒 Here you can buy premium subscriptions for apps and services at affordable prices.\n\n"
            "🎁 Invite friends using the referral system and get bonuses!\n\n"
            "📌 Choose a service from the menu below 👇"
            "</b>"
        ),
        "stats.title": "📊 <b>My stats</b>",
        "referral.title": "👥 <b>Referral</b>",
        "profile.title": "👤 <b>Profile</b>",
        "topup.title": "💳 <b>Top up</b>",
        "topup.open": "💳 Top up\n\nChoose a method 👇",
        "topup.choose_amount": "💳 Choose an amount 👇",
        "topup.custom.title": "💳 <b>Custom amount</b>",
        "topup.custom.body": (
            "Send the amount as a message.\n\n"
            "Format:\n"
            "- <code>25000</code>\n"
            "- <code>25 000</code>\n\n"
            "Minimum top up: <b>1000 UZS</b>\n\n"
            "Digits only (no currency text)."
        ),
        "kb.back_menu": "⬅️ Menu",
        "kb.back": "⬅️ Back",
        "kb.check": "🔄 Check",
        "kb.pay": "✅ Pay",
        "kb.send_proof": "✅ Send receipt",
        "kb.other_amount": "✍️ Enter other amount",
        "top.leaderboard.title": "🏆 <b>Top buyers (TOP–5)</b>",
        "top.leaderboard.desc": "📊 Users who topped up the most during the selected period.",
        "top.period.today": "Today",
        "top.period.week": "This week",
        "top.period.month": "This month",
        "top.period.all": "All time",
        "top.contest": "Contest",
        "products.buy_points": "🎁 Buy with points (7 points)",
    },
    "ru": {
        "menu.gemine": "💎 Аккаунт Gemini",
        "menu.chatgpt": "🚀 ChatGPT Business",
        "menu.topup": "💳 Пополнить баланс",
        "menu.top": "🏆 Топ",
        "menu.stats": "📊 Моя статистика",
        "menu.referral": "🎁 Реферал",
        "menu.profile": "👤 Профиль",
        "menu.language": "🌐 Til/Language",
        "menu.contact_admin": "📞 Связаться с админом",
        "back": "⬅️ Назад",
        "lang.choose": "🌐 Выберите язык:",
        "lang.uz": "🇺🇿 Uzbek",
        "lang.en": "🇬🇧 English",
        "lang.ru": "🇷🇺 Russian",
        "lang.saved": "✅ Язык сохранён.",
        "home": (
            "<b>"
            "👋 Привет, добро пожаловать в бот {name}!\n\n"
            "🛒 Здесь вы можете покупать премиум‑подписки на приложения и сервисы по выгодным ценам.\n\n"
            "🎁 Приглашайте друзей по реферальной системе и получайте бонусы!\n\n"
            "📌 Выберите нужный раздел в меню ниже 👇"
            "</b>"
        ),
        "stats.title": "📊 <b>Моя статистика</b>",
        "referral.title": "👥 <b>Реферальная система</b>",
        "profile.title": "👤 <b>Профиль</b>",
        "topup.title": "💳 <b>Пополнение</b>",
        "topup.open": "💳 Пополнение\n\nВыберите способ 👇",
        "topup.choose_amount": "💳 Выберите сумму 👇",
        "topup.custom.title": "💳 <b>Другая сумма</b>",
        "topup.custom.body": (
            "Отправьте сумму сообщением.\n\n"
            "Формат:\n"
            "- <code>25000</code>\n"
            "- <code>25 000</code>\n\n"
            "Минимум: <b>1000 UZS</b>\n\n"
            "Только цифры (без текста валюты)."
        ),
        "kb.back_menu": "⬅️ Меню",
        "kb.back": "⬅️ Назад",
        "kb.check": "🔄 Проверить",
        "kb.pay": "✅ Оплатить",
        "kb.send_proof": "✅ Отправить чек",
        "kb.other_amount": "✍️ Другая сумма",
        "top.leaderboard.title": "🏆 <b>Топ покупателей (TOP–5)</b>",
        "top.leaderboard.desc": "📊 Пользователи, которые пополнили больше всего за выбранный период.",
        "top.period.today": "Сегодня",
        "top.period.week": "Неделя",
        "top.period.month": "Месяц",
        "top.period.all": "За всё время",
        "top.contest": "Конкурс",
        "products.buy_points": "🎁 Купить за баллы (7 баллов)",
    },
}


def normalize_lang(lang: str | None) -> str:
    lang = (lang or "").strip().lower()
    if lang in _LANGS:
        return lang
    return "uz"


def t(lang: str | None, key: str, **kwargs: Any) -> str:
    l = normalize_lang(lang)
    s = _TEXTS.get(l, {}).get(key) or _TEXTS["uz"].get(key) or key
    if kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s
