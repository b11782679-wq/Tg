from aiogram import Router, F
from aiogram.types import CallbackQuery
from bot.db.repo import Repo
from bot.services.referral import build_ref_link
from bot.keyboards.menu import back_only_kb
from bot.i18n import t

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

        lang = await repo.get_language(call.from_user.id)
        text = t(lang, "referral.body", invited=invited, link=link)

        await call.message.edit_text(text, reply_markup=back_only_kb(await repo.get_language(call.from_user.id)))
