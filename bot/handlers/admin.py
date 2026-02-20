from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from bot.config import Config
from bot.db.repo import Repo

router = Router()


def setup(repo: Repo, cfg: Config):

    @router.message(Command("admin"))
    async def admin_cmd(message: Message):
        if message.from_user and message.from_user.id != cfg.admin_id:
            return
        url = f"http://{cfg.admin_panel_host}:{cfg.admin_panel_port}/admin"
        await message.answer(f"Admin panel: {url}")

    @router.message(Command("getlogchatid"))
    async def getlogchatid_cmd(message: Message):
        if message.from_user and message.from_user.id != cfg.admin_id:
            return

        fchat = getattr(message, "forward_from_chat", None)
        if (not fchat or not getattr(fchat, "id", None)) and getattr(message, "reply_to_message", None):
            fchat = getattr(message.reply_to_message, "forward_from_chat", None)
        if not fchat or not getattr(fchat, "id", None):
            await message.answer(
                "Kanaldan bitta postni shu botga <b>forward</b> qiling.\n"
                "Keyin o‘sha forward qilingan postga <b>reply</b> qilib <code>/getlogchatid</code> yuboring."
            )
            return

        chat_id = int(fchat.id)
        await message.answer(
            f"LOG_CHANNEL: <code>{chat_id}</code>\n\n"
            "Shuni .env faylga qo‘ying: <code>LOG_CHANNEL=...</code>\n"
            "Public kanal bo‘lsa username ham bo‘ladi: <code>LOG_CHANNEL=@brainrot_videos</code>"
        )

    @router.message(Command("pinglog"))
    async def pinglog_cmd(message: Message):
        if message.from_user and message.from_user.id != cfg.admin_id:
            return

        if not cfg.log_channel:
            await message.answer("LOG_CHANNEL sozlanmagan.")
            return

        try:
            await message.bot.send_message(cfg.log_channel, "<b>LOG TEST</b> — ping")
            await message.answer("✅ Log kanalga test xabar yuborildi.")
        except Exception:
            await message.answer("❗️ Log kanalga yuborib bo‘lmadi (ID noto‘g‘ri yoki botning huquqi yetarli emas).")
