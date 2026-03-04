from __future__ import annotations

from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from bot.db.repo import Repo
from bot.i18n import t
from bot.keyboards.menu import back_only_kb

router = Router()
_repo: Repo | None = None


def setup(repo: Repo) -> None:
    global _repo
    _repo = repo


@router.callback_query(F.data == "telegram:open")
async def telegram_open(call: CallbackQuery, state: FSMContext):
    if _repo is None:
        await call.answer()
        return

    lang = await _repo.get_language(call.from_user.id)
    await state.clear()

    await call.message.edit_text(
        t(lang, "telegram.open"),
        reply_markup=back_only_kb(lang),
        disable_web_page_preview=True,
    )
    await call.answer()
