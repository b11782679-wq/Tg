from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.menu import main_menu_kb, back_only_kb
from bot.keyboards.products import product_plans_kb
from bot.services.pricing import PRICING
from bot.constants import ACCOUNT_COST_POINTS
from bot.db.repo import Repo
from bot.i18n import t

router = Router()

def setup(repo: Repo):

    async def _safe_show(call: CallbackQuery, text: str, reply_markup):
        try:
            await call.message.edit_text(text, reply_markup=reply_markup)
        except Exception:
            try:
                await call.message.answer(text, reply_markup=reply_markup)
            except Exception:
                pass

    @router.callback_query(F.data == "m:home")
    async def back_home(call: CallbackQuery):
        await call.answer()

        lang = await repo.get_language(call.from_user.id)
        text = t(lang, "home", name=call.from_user.full_name or "Foydalanuvchi")

        # message is not modified bo'lib qolsa ham yiqilmasin
        try:
            await call.message.edit_text(text, reply_markup=main_menu_kb(lang))
        except Exception:
            pass

    @router.callback_query(F.data.startswith("p:open:"))
    async def open_product(call: CallbackQuery):
        _, _, product_key = call.data.split(":")
        product = PRICING[product_key]
        lang = await repo.get_language(call.from_user.id)

        if product_key == "gemine":
            text = (
                "💎 <b>Gemini Pro akkaunt</b>\n"
                "Ushbu akkauntni xarid qilsangiz, Gemini’ning barcha Pro funksiyalaridan to‘liq foydalanish imkoniyatiga ega bo‘lasiz.\n\n"
                "📌 Kerakli tarifni quyidagilardan tanlang 👇"
            )
        else:
            text = (
                f"{product['title']}\n\n" + t(lang, "products.choose_plan")
            )

        await call.answer()
        await call.message.edit_text(text, reply_markup=product_plans_kb(product_key, lang))

    @router.callback_query(F.data.startswith("p:buy:"))
    async def buy_money(call: CallbackQuery):
        await call.answer()
        _, _, product_key, plan_key = call.data.split(":")
        plan = PRICING[product_key]["plans"][plan_key]
        need_uzs = int(plan["price_uzs"])

        def _fmt_money(n: int) -> str:
            return f"{int(n):,}".replace(",", " ")

        ok, reason, payload = await repo.purchase_account(
            user_id=call.from_user.id,
            product_key=product_key,
            plan_key=plan_key,
            price_uzs=need_uzs,
        )

        if not ok:
            if reason == "no_stock":
                await _safe_show(
                    call,
                    t(await repo.get_language(call.from_user.id), "products.no_stock"),
                    reply_markup=back_only_kb(await repo.get_language(call.from_user.id)),
                )
                return

            if reason == "race":
                await _safe_show(
                    call,
                    t(await repo.get_language(call.from_user.id), "products.race"),
                    reply_markup=back_only_kb(await repo.get_language(call.from_user.id)),
                )
                return

            bal = await repo.get_balance(call.from_user.id)
            money_uzs = int(bal["money_uzs"] or 0) if bal else 0
            lang = await repo.get_language(call.from_user.id)
            await _safe_show(
                call,
                t(
                    lang,
                    "money.no_balance",
                    balance=_fmt_money(money_uzs),
                    need=_fmt_money(need_uzs),
                ),
                reply_markup=back_only_kb(await repo.get_language(call.from_user.id)),
            )
            return

        login = str((payload or {}).get("login") or "")
        password = str((payload or {}).get("password") or "")

        msg = (
            f"{t(await repo.get_language(call.from_user.id), 'products.buy.selected')}\n"
            f"{PRICING[product_key]['title']} — {plan['label']}\n"
            f"{t(await repo.get_language(call.from_user.id), 'products.buy.price')} {_fmt_money(need_uzs)} so'm\n\n"
        )

        msg += (
            f"{t(await repo.get_language(call.from_user.id), 'profile.login')}:\n"
            f"{(login or '').strip() or '-'}\n\n"
            f"{t(await repo.get_language(call.from_user.id), 'profile.password')}:\n"
            f"{(password or '').strip() or '-'}"
        )

        await _safe_show(call, msg, reply_markup=back_only_kb(await repo.get_language(call.from_user.id)))

    @router.callback_query(F.data.startswith("p:buy_points:"))
    async def buy_points(call: CallbackQuery):
        _, _, _, product_key = call.data.split(":")
        ok = await repo.deduct_points(call.from_user.id, ACCOUNT_COST_POINTS)

        await call.answer()

        if not ok:
            bal = await repo.get_balance(call.from_user.id)
            lang = await repo.get_language(call.from_user.id)
            await call.message.edit_text(
                t(lang, "points.no_balance", points=int(bal["points"] or 0), need=ACCOUNT_COST_POINTS),
                reply_markup=main_menu_kb(await repo.get_language(call.from_user.id)),
            )
            return

        await call.message.edit_text(
            f"{t(await repo.get_language(call.from_user.id), 'points.bought')}\n"
            f"{PRICING[product_key]['title']}\n\n"
            + t(await repo.get_language(call.from_user.id), "products.buy.success_admin"),
            reply_markup=main_menu_kb(await repo.get_language(call.from_user.id)),
        )
