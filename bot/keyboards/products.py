from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.services.pricing import PRICING
from bot.i18n import t
import os

def products_menu_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "menu.gemine"), callback_data="p:open:gemine")
    kb.button(text=t(lang, "menu.chatgpt"), callback_data="p:open:chatgpt_business")
    kb.button(text=t(lang, "menu.chatgpt_plus"), callback_data="p:open:chatgpt_plus")
    kb.button(text=t(lang, "menu.super_grok"), callback_data="p:open:super_grok")
    kb.button(text=t(lang, "back"), callback_data="m:home")
    kb.adjust(2, 2, 1)
    return kb.as_markup()

def product_plans_kb(product_key: str, lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    product = PRICING[product_key]
    uzs_per_usd_env = (os.getenv("UZS_PER_USD") or "").strip()
    try:
        uzs_per_usd = float(uzs_per_usd_env) if uzs_per_usd_env else 12200.0
    except Exception:
        uzs_per_usd = 12200.0

    for plan_key, p in product["plans"].items():
        label = str(p.get("label") or "")
        if str(plan_key) == "1m":
            label = t(lang, "plan.1m")
        price_uzs = int(p["price_uzs"])
        if str(lang) in ("en", "ru"):
            usd = float(price_uzs) / max(uzs_per_usd, 1.0)
            price_label = f"${usd:,.2f}".replace(",", " ")
        else:
            price_label = f"{price_uzs:,} so'm".replace(",", " ")
        kb.button(
            text=f"✅ {label} — {price_label}",
            callback_data=f"p:buy:{product_key}:{plan_key}",
        )
    if product_key not in ("chatgpt_business", "chatgpt_plus", "super_grok", "gemine"):
        kb.button(text=t(lang, "products.buy_points"), callback_data=f"p:buy_points:{product_key}")
    kb.button(text=t(lang, "back"), callback_data="m:home")
    if product_key not in ("chatgpt_business", "chatgpt_plus", "super_grok", "gemine"):
        kb.adjust(1, 1, 1)
    else:
        kb.adjust(1, 1)
    return kb.as_markup()
