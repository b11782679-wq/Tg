from aiogram.utils.keyboard import InlineKeyboardBuilder
from bot.services.pricing import PRICING

def products_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💎 Gemine akkaunt", callback_data="p:open:gemine")
    kb.button(text="🚀 ChatGPT Business", callback_data="p:open:chatgpt_business")
    kb.button(text="⬅️ Ortga", callback_data="m:home")
    kb.adjust(2, 1)
    return kb.as_markup()

def product_plans_kb(product_key: str):
    kb = InlineKeyboardBuilder()
    product = PRICING[product_key]
    for plan_key, p in product["plans"].items():
        kb.button(
            text=f"✅ {p['label']} — {p['price_uzs']:,} so'm".replace(",", " "),
            callback_data=f"p:buy:{product_key}:{plan_key}",
        )
    if product_key not in ("chatgpt_business", "gemine"):
        kb.button(text="🎁 Ball bilan olish (7 ball)", callback_data=f"p:buy_points:{product_key}")
    kb.button(text="⬅️ Ortga", callback_data="m:home")
    if product_key not in ("chatgpt_business", "gemine"):
        kb.adjust(1, 1, 1)
    else:
        kb.adjust(1, 1)
    return kb.as_markup()
