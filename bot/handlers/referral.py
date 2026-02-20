from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.db.repo import Repo
from bot.services.referral import build_ref_link
from bot.keyboards.menu import back_only_kb

router = Router()

def setup(repo: Repo):

    @router.callback_query(F.data == "referral")
    async def referral_page(call: CallbackQuery):
        await call.answer()

        me = await call.bot.get_me()
        u = await repo.get_user(call.from_user.id)
        code = "" if not u else str(u["referral_code"] or "")
        link = build_ref_link(me.username, code)

        stats = await repo.get_ref_stats(call.from_user.id)
        invited = stats.get("invited", 0)

        text = (
            "👥 <b>Referal tizimi</b>\n\n"
            "⁉️ <b>U qanday ishlaydi?</b>\n"
            "<blockquote>🎁 Botga do'stingizni taklif qiling. Do'stingiz kanalga qo'shilib "
            "\"Tekshirish\" tugmasini bosilganda va menyudagi tugmalardan birini bosganda hisobingizga pul qo'shiladi. "
            "Har bir taklif qilgan do'stingiz uchun hisobingizga 5000 so'mdan qo'shiladi</blockquote>\n\n"
            f"📊 <b>Taklif qilgan do'stlaringiz:</b> {invited} ta\n\n"
            "🔗 <b>Referal havolangizni do'stlaringizga yuborib ularni botga taklif qiling</b>\n"
            f"<code>{link}</code>"
        )

        await call.message.edit_text(text, reply_markup=back_only_kb())
