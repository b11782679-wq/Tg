from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.services.pricing import PRICING
from bot.i18n import t

def products_menu_kb(lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    kb.button(text=t(lang, "menu.gemine"), callback_data="p:open:gemine")
    kb.button(text=t(lang, "menu.chatgpt"), callback_data="p:open:chatgpt_business")
    kb.button(text=t(lang, "menu.chatgpt_plus"), callback_data="p:open:chatgpt_plus")
    kb.button(text=t(lang, "back"), callback_data="m:home")
    kb.adjust(2, 1, 1)
    return kb.as_markup()

def product_plans_kb(product_key: str, lang: str = "uz"):
    kb = InlineKeyboardBuilder()
    product = PRICING[product_key]
    for plan_key, p in product["plans"].items():
        kb.button(
            text=f"✅ {p['label']} — {p['price_uzs']:,} so'm".replace(",", " "),
            callback_data=f"p:buy:{product_key}:{plan_key}",
        )
    if product_key not in ("chatgpt_business", "chatgpt_plus", "gemine"):
        kb.button(text=t(lang, "products.buy_points"), callback_data=f"p:buy_points:{product_key}")
    kb.button(text=t(lang, "back"), callback_data="m:home")
    if product_key not in ("chatgpt_business", "chatgpt_plus", "gemine"):
        kb.adjust(1, 1, 1)
    else:
        kb.adjust(1, 1)
    return kb.as_markup()
