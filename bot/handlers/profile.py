from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.repo import Repo
from bot.keyboards.menu import back_only_kb
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
                title = (PRICING.get(product_key) or {}).get("title") or product_key
                login = str(a["login"] or "").strip()
                password = str(a["password"] or "").strip()

                # Special display for Canva Pro Link
                if product_key == "canva_pro_link" and login:
                    text += (
                        f"\n\n<b>{title}</b>\n"
                        f"🔗 <a href='{login}'>Canva Pro ga o'tish</a>"
                    )
                else:
                    text += (
                        f"\n\n<b>{title}</b>"
                        f"\n{t(lang, 'profile.login')}: <code>{login}</code>"
                        f"\n{t(lang, 'profile.password')}: <code>{password}</code>"
                    )

        await call.message.edit_text(text, reply_markup=back_only_kb(await repo.get_language(call.from_user.id)))
