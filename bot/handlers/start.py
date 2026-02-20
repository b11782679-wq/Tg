from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from bot.keyboards.menu import main_menu_kb
from bot.db.repo import Repo
from bot.i18n import t

from bot.utils.subscribe import is_subscribed
from bot.keyboards.subscribe import subscribe_kb
from bot.constants import REQUIRED_CHANNEL, REF_MONEY_BONUS_UZS

router = Router()


def setup(repo: Repo):

    @router.message(CommandStart())
    async def start(message: Message):
        # /start <referrer_id> parsing
        referrer_id = None
        args = (message.text or "").split(maxsplit=1)
        if len(args) == 2:
            payload = (args[1] or "").strip()
            if payload.isdigit():
                referrer_id = int(payload)
            elif payload.startswith("ref_"):
                code = payload[4:]
                referrer_id = await repo.get_user_id_by_ref_code(code)

        user_id = message.from_user.id

        # ✅ Userni bazaga yozamiz (referrer_id users jadvalida saqlanadi)
        await repo.ensure_user(
            user_id=user_id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
            referrer_id=referrer_id,
        )

        # ✅ Referral link bo'lsa: referrals jadvaliga 1 marta yozamiz va referrerga xabar beramiz
        if referrer_id and referrer_id != user_id:
            created = await repo.create_referral_if_new(referrer_id, user_id)
            if created:
                try:
                    await message.bot.send_message(
                        referrer_id,
                        "📩 <b>Yangi referal!</b>\n\n"
                        "Kimdur sizni referalingizdan ro‘yxatdan o‘tdi.\n"
                        f"Agar kanalga qo‘shilsa hisobingizga <b>{REF_MONEY_BONUS_UZS} so'm</b> qo‘shiladi ✅",
                    )
                except Exception:
                    # referrer botni block qilgan bo‘lishi mumkin
                    pass

        # ✅ Kanalga a’zo bo‘lmasa — bot ishlamaydi
        ok = await is_subscribed(message.bot, user_id)
        if not ok:
            lang = await repo.get_language(user_id)
            await message.answer(
                t(lang, "sub.lock", channel=REQUIRED_CHANNEL),
                reply_markup=subscribe_kb(lang),
            )
            return

        # ✅ A’zo bo‘lsa — menyu
        lang = await repo.get_language(user_id)
        await message.answer(
            t(lang, "home", name=message.from_user.full_name or "Foydalanuvchi"),
            reply_markup=main_menu_kb(lang),
        )
