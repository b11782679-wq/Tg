from typing import Callable, Awaitable, Any, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from bot.utils.subscribe import is_subscribed
from bot.keyboards.subscribe import subscribe_kb
from bot.constants import REQUIRED_CHANNEL
from bot.db.repo import Repo


class SubscribeMiddleware(BaseMiddleware):
    def __init__(self, repo: Repo | None = None):
        super().__init__()
        self.repo = repo

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        bot = data["bot"]
        repo = self.repo

        # ✅ /start ni bloklamaymiz (referral yozilishi kerak)
        if isinstance(event, Message):
            txt = (event.text or "").strip().lower()
            if txt.startswith("/start"):
                return await handler(event, data)

        # ✅ sub:check ni ham bloklamaymiz (tekshiruv + bonus shu yerda)
        if isinstance(event, CallbackQuery):
            if (event.data or "") == "sub:check":
                return await handler(event, data)

        # Qolgan hamma joyda kanalga a'zolik shart
        user_id = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id:
            ok = await is_subscribed(bot, user_id)
            if not ok:
                text = (
                    "🔒 Botdan foydalanish uchun kanalga a’zo bo‘ling:\n"
                    f"{REQUIRED_CHANNEL}\n\n"
                    "A’zo bo‘lgach ✅ Tekshirish ni bosing."
                )
                if isinstance(event, Message):
                    await event.answer(text, reply_markup=subscribe_kb())
                else:
                    await event.answer()
                    await event.message.edit_text(text, reply_markup=subscribe_kb())
                return

            if repo is not None:
                try:
                    reward = await repo.activate_ref_action_and_reward(invited_id=user_id)
                    if reward:
                        referrer_id, amount = reward
                        try:
                            await bot.send_message(
                                referrer_id,
                                f"✅ <b>Referalingiz aktiv bo‘ldi!</b>\n\n"
                                f"Hisobingizga <b>{amount} so'm</b> qo‘shildi 🎉",
                            )
                        except Exception:
                            pass
                except Exception:
                    pass

        return await handler(event, data)
