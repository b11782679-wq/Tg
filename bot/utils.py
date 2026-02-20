from aiogram import Bot
from bot.constants import REQUIRED_CHANNEL

async def is_subscribed(bot: Bot, user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(REQUIRED_CHANNEL, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception:
        # Bot kanalga admin qilinmagan bo‘lsa yoki boshqa xatolik bo‘lsa
        return False
