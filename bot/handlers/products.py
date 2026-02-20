from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.keyboards.menu import main_menu_kb, back_only_kb
from bot.keyboards.products import product_plans_kb
from bot.services.pricing import PRICING
from bot.constants import ACCOUNT_COST_POINTS
from bot.db.repo import Repo

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

        name = (call.from_user.full_name or "Foydalanuvchi")
        text = (
            "<b>"
            f"👋 Assalomu alaykum, {name} botiga xush kelibsiz!\n\n"
            "🛒 Ushbu bot orqali siz ilova va saytlardagi premium obunalarni arzon narxlarda xarid qilishingiz mumkin.\n\n"
            "🎁 Shuningdek, referal dasturi orqali do‘stlaringizni taklif qiling va bonuslar evaziga akkauntlarga ega bo‘ling!\n\n"
            "📌 Kerakli xizmatni tanlash uchun quyidagi menyudan foydalaning 👇"
            "</b>"
        )

        # message is not modified bo'lib qolsa ham yiqilmasin
        try:
            await call.message.edit_text(text, reply_markup=main_menu_kb())
        except Exception:
            pass

    @router.callback_query(F.data.startswith("p:open:"))
    async def open_product(call: CallbackQuery):
        _, _, product_key = call.data.split(":")
        product = PRICING[product_key]

        if product_key == "gemine":
            text = (
                "💎 <b>Gemini Pro akkaunt</b>\n"
                "Ushbu akkauntni xarid qilsangiz, Gemini’ning barcha Pro funksiyalaridan to‘liq foydalanish imkoniyatiga ega bo‘lasiz.\n\n"
                "📌 Kerakli tarifni quyidagilardan tanlang 👇"
            )
        else:
            text = (
                f"{product['title']}\n\n"
                "Quyidagilardan birini tanlang 👇"
            )

        await call.answer()
        await call.message.edit_text(text, reply_markup=product_plans_kb(product_key))

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
                    "❌ Hozircha akkaunt qolmagan.\n\n"
                    "Keyinroq qayta urinib ko‘ring.",
                    reply_markup=back_only_kb(),
                )
                return

            if reason == "race":
                await _safe_show(
                    call,
                    "❌ Xatolik yuz berdi.\n\nKeyinroq qayta urinib ko‘ring.",
                    reply_markup=back_only_kb(),
                )
                return

            bal = await repo.get_balance(call.from_user.id)
            money_uzs = int(bal["money_uzs"] or 0) if bal else 0
            await _safe_show(
                call,
                "❌ Balansingiz yetarli emas!\n"
                f"💰 Sizning balansingiz: {_fmt_money(money_uzs)} so‘m\n"
                f"💳 Kerakli summa: {_fmt_money(need_uzs)} so‘m\n"
                "Iltimos, “Hisobni to‘ldirish” bo‘limi orqali balansingizni to‘ldiring 🔄",
                reply_markup=back_only_kb(),
            )
            return

        login = str((payload or {}).get("login") or "")
        password = str((payload or {}).get("password") or "")

        msg = (
            f"Tanlandi:\n"
            f"{PRICING[product_key]['title']} — {plan['label']}\n"
            f"Narx: {_fmt_money(need_uzs)} so'm\n\n"
        )

        msg += (
            "Login:\n"
            f"{(login or '').strip() or '-'}\n\n"
            "Parol:\n"
            f"{(password or '').strip() or '-'}"
        )

        await _safe_show(call, msg, reply_markup=back_only_kb())

    @router.callback_query(F.data.startswith("p:buy_points:"))
    async def buy_points(call: CallbackQuery):
        _, _, _, product_key = call.data.split(":")
        ok = await repo.deduct_points(call.from_user.id, ACCOUNT_COST_POINTS)

        await call.answer()

        if not ok:
            bal = await repo.get_balance(call.from_user.id)
            await call.message.edit_text(
                f"❌ Ball yetarli emas.\n"
                f"Sizda: {bal['points']} ball\n"
                f"Kerak: {ACCOUNT_COST_POINTS} ball\n\n"
                "🎁 Referal bo‘limidan do‘st taklif qilib ball yig‘ing.",
                reply_markup=main_menu_kb()
            )
            return

        await call.message.edit_text(
            f"✅ Ball bilan olindi:\n"
            f"{PRICING[product_key]['title']}\n\n"
            "📞 Admin siz bilan bog‘lanadi.",
            reply_markup=main_menu_kb()
        )
