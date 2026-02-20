from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.repo import Repo
from bot.keyboards.menu import back_only_kb
from bot.i18n import t

router = Router()

def setup(repo: Repo):

    @router.callback_query(F.data == "stats")
    async def stats_page(call: CallbackQuery):
        await call.answer()

        orders_count = await repo.get_orders_count(call.from_user.id)
        ref = await repo.get_ref_stats(call.from_user.id)
        invited = ref.get("invited", 0)

        rank, points, total = await repo.get_rank_by_points(call.from_user.id)

        lang = await repo.get_language(call.from_user.id)

        text = t(
            lang,
            "stats.body",
            title=t(lang, "stats.title"),
            orders_count=orders_count,
            invited=invited,
            rank=rank,
            total=total,
            points=points,
        )

        await call.message.edit_text(text, reply_markup=back_only_kb(await repo.get_language(call.from_user.id)))
