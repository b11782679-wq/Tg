import time
import asyncio
from datetime import datetime
from typing import Callable, Awaitable, Any, Dict

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery


def _clip(s: str, n: int = 220) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _now_hhmm() -> str:
    try:
        return datetime.now().strftime("%H:%M")
    except Exception:
        return ""


class ActivityLogMiddleware(BaseMiddleware):
    def __init__(self, log_chat: int | str):
        super().__init__()
        self.log_chat = str(log_chat).strip() if log_chat is not None else ""
        self._last_sent_by_user: dict[int, float] = {}
        self._last_sent_global: float = 0.0

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        if self.log_chat:
            try:
                bot = data.get("bot")
                now = time.time()

                if now - self._last_sent_global >= 0.25:
                    user_id = None
                    username = ""
                    full_name = ""
                    text = ""

                    event_label = ""
                    if isinstance(event, Message) and event.from_user:
                        user_id = int(event.from_user.id)
                        username = str(event.from_user.username or "")
                        full_name = str(event.from_user.full_name or "")
                        event_label = "Xabar"
                        if event.text:
                            text = _clip(event.text, 500)
                        elif event.photo:
                            text = "Rasm (photo)"
                        elif event.document:
                            text = "Fayl (document)"
                        else:
                            text = "Xabar"

                    if isinstance(event, CallbackQuery) and event.from_user:
                        user_id = int(event.from_user.id)
                        username = str(event.from_user.username or "")
                        full_name = str(event.from_user.full_name or "")
                        event_label = "Tugma bosildi"
                        text = _clip(str(event.data or ""), 500)

                    if user_id is not None:
                        last_u = self._last_sent_by_user.get(user_id, 0.0)
                        if now - last_u >= 0.8:
                            self._last_sent_by_user[user_id] = now
                            self._last_sent_global = now
                            uname = ("@" + username) if username else ""
                            ts = _now_hhmm()
                            header = f"<b>🧾 LOG</b>  <code>{ts}</code>" if ts else "<b>🧾 LOG</b>"
                            msg = (
                                f"{header}\n"
                                f"<b>Event:</b> {event_label}\n"
                                f"<b>User:</b> <code>{user_id}</code> {uname} {full_name}\n"
                                f"<b>Data:</b> <code>{_clip(text, 800)}</code>"
                            )
                            asyncio.create_task(bot.send_message(self.log_chat, msg))
            except Exception:
                pass

        return await handler(event, data)
