from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.repo import Repo
from bot.keyboards.menu import back_only_kb
from bot.services.pricing import PRICING
from bot.i18n import t

router = Router()

def setup(repo: Repo):

    @router.callback_query(F.data == "profile")
    async def profile_open(call: CallbackQuery):
        await call.answer()

        bal = await repo.get_balance(call.from_user.id)
        money = int(bal["money_uzs"]) if bal else 0
        points = int(bal["points"]) if bal else 0

        lang = await repo.get_language(call.from_user.id)

        await repo.expire_old_assigned_accounts(days=7)
        accs = await repo.get_recent_user_accounts(user_id=call.from_user.id, days=7, limit=10)

        # RASMDAGIDEK FORMAT
        text = t(lang, "profile.body", user_id=int(call.from_user.id), money=f"{money:,}".replace(",", " "))

        if accs:
            text += "\n\n" + t(lang, "profile.accounts_title")
            for a in accs:
                product_key = str(a["product_key"] or "")
                title = (PRICING.get(product_key) or {}).get("title") or product_key
                login = str(a["login"] or "").strip()
                password = str(a["password"] or "").strip()
                text += (
                    f"\n\n<b>{title}</b>"
                    f"\n{t(lang, 'profile.login')}: <code>{login}</code>"
                    f"\n{t(lang, 'profile.password')}: <code>{password}</code>"
                )

        await call.message.edit_text(text, reply_markup=back_only_kb(await repo.get_language(call.from_user.id)))
