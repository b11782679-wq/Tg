from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.repo import Repo
from bot.keyboards.menu import back_to_settings_kb
from bot.services.pricing import PRICING
from bot.i18n import t
import os

router = Router()

def setup(repo: Repo):

    @router.callback_query(F.data == "profile")
    async def profile_open(call: CallbackQuery):
        await call.answer()

        bal = await repo.get_balance(call.from_user.id)
        money = int(bal["money_uzs"]) if bal else 0
        points = int(bal["points"]) if bal else 0

        lang = await repo.get_language(call.from_user.id)

        uzs_per_usd_env = (os.getenv("UZS_PER_USD") or "").strip()
        try:
            uzs_per_usd = float(uzs_per_usd_env) if uzs_per_usd_env else 12200.0
        except Exception:
            uzs_per_usd = 12200.0

        if str(lang) in ("en", "ru"):
            usd = float(int(money)) / max(float(uzs_per_usd), 1.0)
            money_label = f"${usd:,.2f}".replace(",", " ")
        else:
            money_label = f"{money:,}".replace(",", " ")

        await repo.expire_old_assigned_accounts(days=7)
        accs = await repo.get_recent_user_accounts(user_id=call.from_user.id, days=7, limit=10)

        # RASMDAGIDEK FORMAT
        text = t(lang, "profile.body", user_id=int(call.from_user.id), money=money_label)

        if accs:
            text += "\n\n" + t(lang, "profile.accounts_title")
            for a in accs:
                product_key = str(a["product_key"] or "")
                if product_key == "gemine_3m":
                    base_title = (PRICING.get("gemine") or {}).get("title") or "Gemini Pro"
                    title = f"{base_title} — 3 oy"
                else:
                    title = (PRICING.get(product_key) or {}).get("title") or product_key
                login = str(a["login"] or "").strip()
                password = str(a["password"] or "").strip()

                # Special display for Canva Pro Link
                if product_key in ("canva_pro_link", "gemine_3m") and login:
                    text += f"\n\n<blockquote><b>{title}</b>\n🔗 <code>{login}</code></blockquote>"
                else:
                    text += (
                        f"\n\n<blockquote><b>{title}</b>"
                        f"\nL: <code>{login or '-'}</code>"
                        f"\nP: <code>{password or '-'}</code>"
                        f"</blockquote>"
                    )

        await call.message.edit_text(
            text,
            reply_markup=back_to_settings_kb(await repo.get_language(call.from_user.id)),
            disable_web_page_preview=True,
        )
