from __future__ import annotations

from typing import Any


_LANGS = {"uz", "en", "ru"}


_TEXTS: dict[str, dict[str, str]] = {
    "uz": {
        "menu.youtuber": "📺 YouTuberlar uchun",
        "menu.gemine": "💎 Gemine akkaunt",
        "menu.chatgpt": "🚀 ChatGPT Business",
        "menu.chatgpt_plus": "✨ ChatGPT Plus",
        "menu.spotify_premium": "🎧 Spotify Premium",
        "menu.youtube_premium": "▶️ YouTube Premium",
        "menu.super_grok": "⚡ Super Grok",
        "menu.canva_pro": "🎨 Canva Pro",
        "menu.capcut_pro": "🎬 CapCut Pro",
        "menu.topup": "💳 Hisob To'ldirish",
        "menu.top": "🏆 Top",
        "menu.premium": "💎 Premium Obunalar",
        "menu.stats": "📊 Statistikam",
        "menu.referral": "🎁 Referal",
        "menu.profile": "👤 Profil",
        "menu.settings": "⚙️ Sozlamalar",
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
        "topup.method.manual": "🧾 Admin orqali",
        "topup.method.ton": "🪙 TON orqali",
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
        "topup.manual.instructions": (
            "👤 <b>To‘lov tartibi:</b>\n"
            "1️⃣ Admin ko‘rsatgan karta raqamiga to‘lovni amalga oshiring:\n"
            "💳 <code>{card}</code>\n"
            "👤 {owner}\n\n"
            "2️⃣ To‘lov chekini (screenshot yoki fayl) ushbu chatga yuboring 📩\n\n"
            "🆔 Topup ID: <code>{topup_id}</code>\n"
            "💰 Summa: <b>{amount} so'm</b>\n\n"
            "⚠️ Soxta chek yuborish botdan bloklanishga olib keladi.\n\n"
            "✅ Chek yuborilgandan so‘ng admin tomonidan tasdiqlanadi."
        ),
        "topup.ton.instructions": (
            "🪙 <b>TON orqali to‘lov</b>\n\n"
            "Quyidagi TON addressga to‘lov qiling:\n"
            "<code>{address}</code>\n\n"
            "So‘ng to‘lov chekini (screenshot yoki fayl) ushbu chatga yuboring 📩\n\n"
            "🆔 Topup ID: <code>{topup_id}</code>\n"
            "💰 Summa: <b>{amount_label}</b>"
        ),
        "topup.proof.received": (
            "✅ Chek qabul qilindi. Admin tekshiradi va tasdiqlaydi.\n\n"
            "Topup ID: <code>{topup_id}</code>"
        ),
        "topup.custom.only_digits": "❗️ Summani faqat raqam bilan yuboring. Masalan: <code>25000</code> yoki <code>25 000</code>",
        "topup.custom.min_amount": "❗️ Eng kam hisob to‘ldirish miqdori <b>1000 so'm</b>.",
        "topup.custom.invalid_amount": "❗️ Noto‘g‘ri summa. Qaytadan kiriting.",
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
        "sub.join": "📢 Kanalga qo‘shilish",
        "sub.check": "✅ Tekshirish",
        "sub.lock": (
            "🔒 Botdan foydalanish uchun kanalga a’zo bo‘ling:\n"
            "{channel}\n\n"
            "A’zo bo‘lgach ✅ Tekshirish ni bosing."
        ),
        "stats.body": (
            "{title}\n\n"
            "🧾 <b>Barcha buyurtmalar soni:</b> {orders_count}\n"
            "👥 <b>Siz botga taklif qilgan odamlar soni:</b> {invited}\n"
            "🏆 <b>Bot bo‘yicha o‘rningiz:</b> {rank}/{total}\n\n"
            "⭐ <b>Ball:</b> {points}"
        ),
        "referral.body": (
            "👥 <b>Referal tizimi</b>\n\n"
            "⁉️ <b>U qanday ishlaydi?</b>\n"
            "<blockquote>🎁 Botga do'stingizni taklif qiling. Do'stingiz kanalga qo'shilib \"Tekshirish\" tugmasini bosilganda va menyudagi tugmalardan birini bosganda hisobingizga pul qo'shiladi. Har bir taklif qilgan do'stingiz uchun hisobingizga 5000 so'mdan qo'shiladi</blockquote>\n\n"
            "📊 <b>Taklif qilgan do'stlaringiz:</b> {invited} ta\n\n"
            "🔗 <b>Referal havolangizni do'stlaringizga yuborib ularni botga taklif qiling</b>\n"
            "<code>{link}</code>"
        ),
        "profile.body": "🆔 <b>User ID:</b> <code>[{user_id}]</code>\n💰 <b>Balans:</b> {money} so'm",
        "profile.accounts_title": "<b>🧾 Akkauntlar (7 kun):</b>",
        "profile.login": "Login",
        "profile.password": "Parol",
        "plan.1m": "1 oy",
        "plan.1w": "1 hafta",
        "menu.canva_pro_link": "🔗 Canva Pro Link",
        "settings.open": "⚙️ <b>Sozlamalar</b>",
        "premium.open": "💎 <b>Premium Obunalar</b>\n\nQuyidagilardan birini tanlang 👇",
        "products.choose_plan": "📌 Quyidagilardan birini tanlang 👇",
        "products.no_stock": "❌ Hozircha akkaunt qolmagan.\n\nKeyinroq qayta urinib ko‘ring.",
        "products.race": "❌ Xatolik yuz berdi.\n\nKeyinroq qayta urinib ko‘ring.",
        "products.gemine.open": (
            "💎 <b>Gemini Pro akkaunt</b>\n"
            "Ushbu akkauntni xarid qilsangiz, Gemini’ning barcha Pro funksiyalaridan to‘liq foydalanish imkoniyatiga ega bo‘lasiz.\n\n"
            "📌 Kerakli tarifni quyidagilardan tanlang 👇"
        ),
        "products.buy.selected": "Tanlandi:",
        "products.buy.price": "Narx:",
        "products.buy.success_admin": "📞 Admin siz bilan bog‘lanadi.",
        "money.no_balance": (
            "❌ Hisobingizda mablag‘ yetarli emas.\n"
            "Hozirgi balansingiz ushbu amalni bajarish uchun kamlik qiladi.\n"
            "Iltimos, davom etishdan oldin hisobingizni to‘ldiring 💳\n\n"
            "🔄 “Hisobni to‘ldirish” bo‘limi orqali balans qo‘shishingiz mumkin."
        ),
        "points.no_balance": (
            "❌ Ball yetarli emas.\n"
            "Sizda: {points} ball\n"
            "Kerak: {need} ball\n\n"
            "🎁 Referal bo‘limidan do‘st taklif qilib ball yig‘ing."
        ),
        "points.bought": "✅ Ball bilan olindi:",
        "user.blocked": "⛔️ Siz botdan bloklangansiz.",
        "youtuber.welcome": (
            "📺 <b>YouTube kanal tahlili</b>\n\n"
            "Bugun: {used}/{limit} ta bepul audit\n\n"
            "YouTube kanalingiz linkini yuboring:\n"
            "• youtube.com/@username\n"
            "• youtube.com/channel/UC...\n"
            "• @username"
        ),
        "youtuber.invalid_link": (
            "❗️ Noto‘g‘ri YouTube link.\n\n"
            "Misol uchun:\n"
            "• youtube.com/@username\n"
            "• youtube.com/c/channelname\n"
            "• @username"
        ),
        "youtuber.ask_goal": (
            "🎯 <b>Maqsadingiz nima?</b>\n\n"
            "Nima erishmoqchisiz?\n"
            "• Ko‘p obunachi\n"
            "• Ko‘p ko‘rilish\n"
            "• Monetizatsiya\n"
            "• Boshqa...\n\n"
            "Yozib yuboring:"
        ),
        "youtuber.ask_problem": (
            "🔍 <b>Muammolaringiz qanday?</b>\n\n"
            "Kanalingizda nimalar yaxshi ketmayapti?\n"
            "• Views past\n"
            "• Retention kam\n"
            "• CTR past\n"
            "• Shorts ishlamayapti\n"
            "• Boshqa...\n\n"
            "Yozib yuboring (ixtiyoriy):"
        ),
        "youtuber.processing": (
            "⏳ Kanalingiz tekshirilmoqda...\n"
            "Bu bir necha soniya davom etadi."
        ),
        "youtuber.limit_reached": (
            "❗️ Bugungi audit limitidan o‘tdingiz.\n"
            "Kunlik limit: {limit} ta\n\n"
            "Ertaga qayta urinib ko‘ring yoki premium oling."
        ),
        "youtuber.channel_not_found": (
            "❌ Kanal topilmadi.\n\n"
            "Linkni tekshirib qaytadan yuboring:\n"
            "• Kanal ochiq bo‘lishi kerak\n"
            "• To‘g‘ri link yuboring"
        ),
        "youtuber.api_quota_exceeded": (
            "⚠️ YouTube API limit tugadi.\n"
            "Iltimos, birozdan so‘ng qayta urinib ko‘ring."
        ),
        "youtuber.timeout": (
            "⏱️ So‘rov vaqtidan o‘tdi.\n"
            "Qayta urinib ko‘ring."
        ),
        "youtuber.gemini_error": (
            "❌ AI tahlil qilishda xatolik.\n"
            "Qayta urinib ko‘ring."
        ),
        "youtuber.youtube_error": (
            "❌ YouTube ma’lumotlarini olishda xatolik.\n"
            "Qayta urinib ko‘ring."
        ),
        "youtuber.generic_error": (
            "❌ Xatolik yuz berdi.\n"
            "Qayta urinib ko‘ring."
        ),
        "youtuber.done": "✅ Tahlil tayyor! Yuqorida ko‘rib chiqing.",
    },
    "en": {
        "menu.youtuber": "📺 For YouTubers",
        "menu.gemine": "💎 Gemini account",
        "menu.chatgpt": "🚀 ChatGPT Business",
        "menu.chatgpt_plus": "✨ ChatGPT Plus",
        "menu.super_grok": "⚡ Super Grok",
        "menu.canva_pro": "🎨 Canva Pro",
        "menu.canva_pro_link": "🔗 Canva Pro Link",
        "menu.capcut_pro": "🎬 CapCut Pro",
        "menu.topup": "💳 Top up balance",
        "menu.top": "🏆 Top",
        "menu.stats": "📊 My stats",
        "menu.referral": "🎁 Referral",
        "menu.profile": "👤 Profile",
        "menu.settings": "⚙️ Settings",
        "menu.language": "🌐 Til/Language",
        "menu.contact_admin": "📞 Contact admin",
        "back": "⬅️ Back",
        "user.blocked": "⛔️ You are blocked from using this bot.",
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
        "topup.method.manual": "🧾 Via admin",
        "topup.method.ton": "🪙 Pay with TON",
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
        "topup.manual.instructions": (
            "👤 <b>Payment instructions:</b>\n"
            "1️⃣ Make a payment to the card number below:\n"
            "💳 <code>{card}</code>\n"
            "👤 {owner}\n\n"
            "2️⃣ Send the payment receipt (screenshot or file) to this chat 📩\n\n"
            "🆔 Topup ID: <code>{topup_id}</code>\n"
            "💰 Amount: <b>{amount} UZS</b>\n\n"
            "⚠️ Fake receipts may result in a ban.\n\n"
            "✅ After you send the receipt, it will be confirmed by an admin."
        ),
        "topup.ton.instructions": (
            "🪙 <b>TON payment</b>\n\n"
            "Send payment to this TON address:\n"
            "<code>{address}</code>\n\n"
            "Then send the receipt (screenshot or file) to this chat 📩\n\n"
            "🆔 Topup ID: <code>{topup_id}</code>\n"
            "💰 Amount: <b>{amount_label}</b>"
        ),
        "topup.proof.received": (
            "✅ Receipt received. Admin will review and confirm it.\n\n"
            "Topup ID: <code>{topup_id}</code>"
        ),
        "topup.custom.only_digits": "❗️ Send amount as digits only. Example: <code>25000</code> or <code>25 000</code>",
        "topup.custom.min_amount": "❗️ Minimum top up amount is <b>1000 UZS</b>.",
        "topup.custom.invalid_amount": "❗️ Invalid amount. Please try again.",
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
        "sub.join": "📢 Join channel",
        "sub.check": "✅ Check",
        "sub.lock": (
            "🔒 To use the bot, join the channel:\n"
            "{channel}\n\n"
            "After joining, press ✅ Check."
        ),
        "stats.body": (
            "{title}\n\n"
            "🧾 <b>Total orders:</b> {orders_count}\n"
            "👥 <b>Invited users:</b> {invited}\n"
            "🏆 <b>Your rank:</b> {rank}/{total}\n\n"
            "⭐ <b>Points:</b> {points}"
        ),
        "referral.body": (
            "👥 <b>Referral</b>\n\n"
            "⁉️ <b>How it works?</b>\n"
            "<blockquote>🎁 Invite your friend. When your friend joins the channel and presses \"Check\" and uses the menu, you get a bonus. You get 5000 UZS per invited friend.</blockquote>\n\n"
            "📊 <b>Invited friends:</b> {invited}\n\n"
            "🔗 <b>Share this referral link</b>\n"
            "<code>{link}</code>"
        ),
        "profile.body": "🆔 <b>User ID:</b> <code>[{user_id}]</code>\n💰 <b>Balance:</b> {money}",
        "profile.accounts_title": "<b>🧾 Accounts (7 days):</b>",
        "profile.login": "Login",
        "profile.password": "Password",
        "plan.1m": "1 month",
        "plan.1w": "1 week",
        "settings.open": "⚙️ <b>Settings</b>",
        "premium.open": "💎 <b>Premium subscriptions</b>\n\nChoose one 👇",
        "products.choose_plan": "Choose one 👇",
        "products.no_stock": "❌ No accounts in stock right now.\n\nPlease try again later.",
        "products.race": "❌ Something went wrong.\n\nPlease try again later.",
        "products.gemine.open": (
            "💎 <b>Gemini Pro account</b>\n"
            "If you purchase this account, you'll get full access to Gemini Pro features.\n\n"
            "📌 Choose a plan below 👇"
        ),
        "products.buy.selected": "Selected:",
        "products.buy.price": "Price:",
        "products.buy.success_admin": "📞 Admin will contact you.",
        "money.no_balance": (
            "❌ Your balance is not enough.\n"
            "Your current balance is insufficient for this action.\n"
            "Please top up your balance before continuing 💳\n\n"
            "🔄 You can add funds via the “Top up balance” section."
        ),
        "points.no_balance": (
            "❌ Not enough points.\n"
            "You have: {points} points\n"
            "Need: {need} points\n\n"
            "🎁 Invite friends from Referral section to earn points."
        ),
        "points.bought": "✅ Bought with points:",
        "youtuber.welcome": (
            "📺 <b>YouTube Channel Audit</b>\n\n"
            "Today: {used}/{limit} free audits\n\n"
            "Send your YouTube channel link:\n"
            "• youtube.com/@username\n"
            "• youtube.com/channel/UC...\n"
            "• @username"
        ),
        "youtuber.invalid_link": (
            "❗️ Invalid YouTube link.\n\n"
            "Examples:\n"
            "• youtube.com/@username\n"
            "• youtube.com/c/channelname\n"
            "• @username"
        ),
        "youtuber.ask_goal": (
            "🎯 <b>What's your goal?</b>\n\n"
            "What do you want to achieve?\n"
            "• More subscribers\n"
            "• More views\n"
            "• Monetization\n"
            "• Other...\n\n"
            "Type your answer:"
        ),
        "youtuber.ask_problem": (
            "🔍 <b>What problems are you facing?</b>\n\n"
            "What's not working well on your channel?\n"
            "• Low views\n"
            "• Low retention\n"
            "• Low CTR\n"
            "• Shorts not working\n"
            "• Other...\n\n"
            "Type your answer (optional):"
        ),
        "youtuber.processing": (
            "⏳ Analyzing your channel...\n"
            "This will take a few seconds."
        ),
        "youtuber.limit_reached": (
            "❗️ You've reached today's audit limit.\n"
            "Daily limit: {limit}\n\n"
            "Try again tomorrow or upgrade to premium."
        ),
        "youtuber.channel_not_found": (
            "❌ Channel not found.\n\n"
            "Please check the link and try again:\n"
            "• Channel must be public\n"
            "• Use correct link format"
        ),
        "youtuber.api_quota_exceeded": (
            "⚠️ YouTube API quota exceeded.\n"
            "Please try again later."
        ),
        "youtuber.timeout": (
            "⏱️ Request timed out.\n"
            "Please try again."
        ),
        "youtuber.gemini_error": (
            "❌ Error generating AI analysis.\n"
            "Please try again."
        ),
        "youtuber.youtube_error": (
            "❌ Error fetching YouTube data.\n"
            "Please try again."
        ),
        "youtuber.generic_error": (
            "❌ An error occurred.\n"
            "Please try again."
        ),
        "youtuber.done": "✅ Analysis complete! Check it out above.",
    },
    "ru": {
        "menu.youtuber": "📺 Для YouTuberов",
        "menu.gemine": "💎 Аккаунт Gemini",
        "menu.chatgpt": "🚀 ChatGPT Business",
        "menu.chatgpt_plus": "✨ ChatGPT Plus",
        "menu.super_grok": "⚡ Super Grok",
        "menu.canva_pro": "🎨 Canva Pro",
        "menu.capcut_pro": "🎬 CapCut Pro",
        "menu.topup": "💳 Пополнить баланс",
        "menu.top": "🏆 Топ",
        "menu.premium": "💎 Премиум подписки",
        "menu.stats": "📊 Моя статистика",
        "menu.referral": "🎁 Реферал",
        "menu.profile": "👤 Профиль",
        "menu.settings": "⚙️ Настройки",
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
        "topup.method.manual": "🧾 Через админа",
        "topup.method.ton": "🪙 Оплата TON",
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
        "topup.manual.instructions": (
            "👤 <b>Инструкция по оплате:</b>\n"
            "1️⃣ Переведите оплату на карту ниже:\n"
            "💳 <code>{card}</code>\n"
            "👤 {owner}\n\n"
            "2️⃣ Отправьте чек (скриншот или файл) в этот чат 📩\n\n"
            "🆔 Topup ID: <code>{topup_id}</code>\n"
            "💰 Сумма: <b>{amount} UZS</b>\n\n"
            "⚠️ Фальшивые чеки могут привести к блокировке.\n\n"
            "✅ После отправки чека админ проверит и подтвердит."
        ),
        "topup.ton.instructions": (
            "🪙 <b>Оплата TON</b>\n\n"
            "Отправьте оплату на этот TON адрес:\n"
            "<code>{address}</code>\n\n"
            "Затем отправьте чек (скриншот или файл) в этот чат 📩\n\n"
            "🆔 Topup ID: <code>{topup_id}</code>\n"
            "💰 Сумма: <b>{amount_label}</b>"
        ),
        "topup.proof.received": (
            "✅ Чек получен. Админ проверит и подтвердит.\n\n"
            "Topup ID: <code>{topup_id}</code>"
        ),
        "topup.custom.only_digits": "❗️ Отправьте сумму только цифрами. Например: <code>25000</code> или <code>25 000</code>",
        "topup.custom.min_amount": "❗️ Минимальная сумма пополнения <b>1000 UZS</b>.",
        "topup.custom.invalid_amount": "❗️ Неверная сумма. Попробуйте снова.",
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
        "sub.join": "📢 Вступить в канал",
        "sub.check": "✅ Проверить",
        "sub.lock": (
            "🔒 Чтобы пользоваться ботом, вступите в канал:\n"
            "{channel}\n\n"
            "После вступления нажмите ✅ Проверить."
        ),
        "stats.body": (
            "{title}\n\n"
            "🧾 <b>Всего заказов:</b> {orders_count}\n"
            "👥 <b>Приглашено:</b> {invited}\n"
            "🏆 <b>Ваше место:</b> {rank}/{total}\n\n"
            "⭐ <b>Баллы:</b> {points}"
        ),
        "referral.body": (
            "👥 <b>Реферальная система</b>\n\n"
            "⁉️ <b>Как это работает?</b>\n"
            "<blockquote>🎁 Пригласите друга. Когда он вступит в канал и нажмёт \"Проверить\" и воспользуется меню, вам начисляется бонус. 5000 UZS за каждого друга.</blockquote>\n\n"
            "📊 <b>Приглашённые друзья:</b> {invited}\n\n"
            "🔗 <b>Ваша реферальная ссылка</b>\n"
            "<code>{link}</code>"
        ),
        "profile.body": "🆔 <b>User ID:</b> <code>[{user_id}]</code>\n💰 <b>Баланс:</b> {money}",
        "profile.accounts_title": "<b>🧾 Аккаунты (7 дней):</b>",
        "profile.login": "Логин",
        "profile.password": "Пароль",
        "plan.1m": "1 месяц",
        "plan.1w": "1 неделя",
        "settings.open": "⚙️ <b>Настройки</b>",
        "premium.open": "💎 <b>Премиум подписки</b>\n\nВыберите вариант 👇",
        "products.choose_plan": "Выберите вариант 👇",
        "products.no_stock": "❌ Сейчас нет аккаунтов в наличии.\n\nПожалуйста, попробуйте позже.",
        "products.race": "❌ Произошла ошибка.\n\nПожалуйста, попробуйте позже.",
        "products.gemine.open": (
            "💎 <b>Аккаунт Gemini Pro</b>\n"
            "Если вы купите этот аккаунт, вы получите полный доступ к функциям Gemini Pro.\n\n"
            "📌 Выберите тариф ниже 👇"
        ),
        "products.buy.selected": "Выбрано:",
        "products.buy.price": "Цена:",
        "products.buy.success_admin": "📞 Админ свяжется с вами.",
        "money.no_balance": (
            "❌ Недостаточно средств на балансе.\n"
            "Ваш текущий баланс недостаточен для выполнения этого действия.\n"
            "Пожалуйста, пополните баланс перед продолжением 💳\n\n"
            "🔄 Вы можете пополнить баланс в разделе “Пополнить баланс”."
        ),
        "points.no_balance": (
            "❌ Недостаточно баллов.\n"
            "У вас: {points} баллов\n"
            "Нужно: {need} баллов\n\n"
            "🎁 Приглашайте друзей в разделе Реферал, чтобы получить баллы."
        ),
        "points.bought": "✅ Куплено за баллы:",
        "youtuber.welcome": (
            "📺 <b>Анализ YouTube канала</b>\n\n"
            "Сегодня: {used}/{limit} бесплатных аудитов\n\n"
            "Отправьте ссылку на канал:\n"
            "• youtube.com/@username\n"
            "• youtube.com/channel/UC...\n"
            "• @username"
        ),
        "youtuber.invalid_link": (
            "❗️ Неверная ссылка YouTube.\n\n"
            "Примеры:\n"
            "• youtube.com/@username\n"
            "• youtube.com/c/channelname\n"
            "• @username"
        ),
        "youtuber.ask_goal": (
            "🎯 <b>Какая у вас цель?</b>\n\n"
            "Чего хотите добиться?\n"
            "• Больше подписчиков\n"
            "• Больше просмотров\n"
            "• Монетизация\n"
            "• Другое...\n\n"
            "Напишите ответ:"
        ),
        "youtuber.ask_problem": (
            "🔍 <b>С какими проблемами столкнулись?</b>\n\n"
            "Что не работает на канале?\n"
            "• Мало просмотров\n"
            "• Низкое удержание\n"
            "• Низкий CTR\n"
            "• Shorts не работают\n"
            "• Другое...\n\n"
            "Напишите ответ (необязательно):"
        ),
        "youtuber.processing": (
            "⏳ Анализирую канал...\n"
            "Это займет несколько секунд."
        ),
        "youtuber.limit_reached": (
            "❗️ Вы достигли лимита аудитов на сегодня.\n"
            "Дневной лимит: {limit}\n\n"
            "Попробуйте завтра или обновитесь до премиума."
        ),
        "youtuber.channel_not_found": (
            "❌ Канал не найден.\n\n"
            "Проверьте ссылку и попробуйте снова:\n"
            "• Канал должен быть публичным\n"
            "• Используйте правильный формат"
        ),
        "youtuber.api_quota_exceeded": (
            "⚠️ Квота YouTube API исчерпана.\n"
            "Попробуйте позже."
        ),
        "youtuber.timeout": (
            "⏱️ Время запроса истекло.\n"
            "Попробуйте снова."
        ),
        "youtuber.gemini_error": (
            "❌ Ошибка генерации AI анализа.\n"
            "Попробуйте снова."
        ),
        "youtuber.youtube_error": (
            "❌ Ошибка получения данных YouTube.\n"
            "Попробуйте снова."
        ),
        "youtuber.generic_error": (
            "❌ Произошла ошибка.\n"
            "Попробуйте снова."
        ),
        "youtuber.done": "✅ Анализ готов! Посмотрите выше.",
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
