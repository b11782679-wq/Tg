from aiogram import Router, F
from aiogram.types import CallbackQuery

from bot.db.repo import Repo
from bot.i18n import t, normalize_lang
from bot.keyboards.language import language_kb
from bot.keyboards.menu import main_menu_kb

router = Router()


def setup(repo: Repo):
    @router.callback_query(F.data == "lang:open")
    async def lang_open(call: CallbackQuery):
        await call.answer()
        lang = await repo.get_language(call.from_user.id)
        await call.message.edit_text(t(lang, "lang.choose"), reply_markup=language_kb(lang))

    @router.callback_query(F.data.startswith("lang:set:"))
    async def lang_set(call: CallbackQuery):
        await call.answer()
        _, _, lang_code = (call.data or "").split(":", maxsplit=2)
        lang_code = normalize_lang(lang_code)
        await repo.set_language(call.from_user.id, lang_code)

        name = call.from_user.full_name or ""
        text = t(lang_code, "home", name=name or "Foydalanuvchi")
        try:
            await call.message.edit_text(text, reply_markup=main_menu_kb(lang_code))
        except Exception:
            pass
