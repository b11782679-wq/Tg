from aiogram import Router, F
from aiogram.types import CallbackQuery, Message

from bot.keyboards.payments import (
    topup_methods_kb,
    topup_amounts_kb,
    top_leaderboard_kb,
    manual_topup_kb,
)
from bot.db.repo import Repo
from bot.i18n import t
import os
from datetime import datetime
import asyncio

router = Router()


def _fmt_money(n: int) -> str:
    return f"{n:,}".replace(",", " ")


def _now_hhmm() -> str:
    try:
        return datetime.now().strftime("%H:%M")
    except Exception:
        return ""


def _render_top5(rows) -> str:
    if not rows:
        return "-"
    lines = []
    for i, (_, name, total) in enumerate(rows, start=1):
        lines.append(f"{i}. {name} — {_fmt_money(total)} so'm")
    return "\n".join(lines)


async def _show_top(call: CallbackQuery, repo: Repo, period: str):
    rows = await repo.get_topup_leaderboard(period=period, limit=5)
    lang = await repo.get_language(call.from_user.id)
    text = (
        f"{t(lang, 'top.leaderboard.title')}\n"
        f"{t(lang, 'top.leaderboard.desc')}\n\n"
        f"{_render_top5(rows)}"
    )
    await call.message.edit_text(text, reply_markup=top_leaderboard_kb(active=period, lang=lang))


def setup(repo: Repo):

    awaiting_custom_amount: dict[int, str] = {}
    log_chat = (os.getenv("LOG_CHANNEL") or "@brainrot_videos").strip() or "@brainrot_videos"

    # =========================
    # TOP-5 Leaderboard (rasmdagidek)
    # =========================
    @router.callback_query(F.data == "top:open")
    async def top_open(call: CallbackQuery):
        await call.answer()
        await _show_top(call, repo, period="today")

    @router.callback_query(F.data.startswith("top:period:"))
    async def top_period(call: CallbackQuery):
        await call.answer()
        period = call.data.split(":")[2]  # today/week/month/all
        await _show_top(call, repo, period=period)

    @router.callback_query(F.data == "top:contest")
    async def top_contest(call: CallbackQuery):
        await call.answer()
        lang = await repo.get_language(call.from_user.id)
        await call.message.edit_text(
            t(lang, "top.contest"),
            reply_markup=top_leaderboard_kb(active="today", lang=lang),
        )

    # =========================
    # Top-up (balans to‘ldirish) oqimi
    # =========================
    @router.callback_query(F.data == "t:open")
    async def topup_open(call: CallbackQuery):
        await call.answer()
        lang = await repo.get_language(call.from_user.id)
        await call.message.edit_text(
            t(lang, "topup.open"),
            reply_markup=topup_methods_kb(lang),
        )

    @router.callback_query(F.data.startswith("t:method:"))
    async def topup_method(call: CallbackQuery):
        provider = call.data.split(":")[2]
        await call.answer()
        lang = await repo.get_language(call.from_user.id)
        await call.message.edit_text(
            t(lang, "topup.choose_amount"),
            reply_markup=topup_amounts_kb(provider, lang),
        )

    @router.callback_query(F.data.startswith("t:custom:"))
    async def topup_custom_amount(call: CallbackQuery):
        provider = call.data.split(":")[2]
        awaiting_custom_amount[int(call.from_user.id)] = str(provider)
        await call.answer()
        lang = await repo.get_language(call.from_user.id)
        await call.message.edit_text(
            t(lang, "topup.custom.title") + "\n\n" + t(lang, "topup.custom.body"),
            reply_markup=topup_amounts_kb(provider, lang),
        )

    @router.callback_query(F.data.startswith("t:amount:"))
    async def topup_amount(call: CallbackQuery):
        _, _, provider, amount = call.data.split(":")
        amount = int(amount)

        await call.answer()
        topup_id = await repo.create_topup(call.from_user.id, provider, amount)

        if log_chat:
            try:
                ts = _now_hhmm()
                header = f"<b>💳 TOPUP YARATILDI</b>  <code>{ts}</code>" if ts else "<b>💳 TOPUP YARATILDI</b>"
                log_text = (
                    f"{header}\n"
                    f"<b>User:</b> <code>{int(call.from_user.id)}</code>\n"
                    f"<b>Topup ID:</b> <code>{int(topup_id)}</code>\n"
                    f"<b>Summa:</b> <b>{_fmt_money(amount)} so'm</b>"
                )
                asyncio.create_task(call.bot.send_message(log_chat, log_text))
            except Exception:
                pass
        await call.message.edit_text(
            "👤 <b>To‘lov tartibi:</b>\n"
            "1️⃣ Admin ko‘rsatgan karta raqamiga to‘lovni amalga oshiring:\n"
            "💳 <code>5614 6887 1574 1061</code>\n"
            "👤 Shonazarov Behruz\n\n"
            "2️⃣ To‘lov chekini (screenshot yoki fayl) ushbu chatga yuboring 📩\n\n"
            f"🆔 Topup ID: <code>{topup_id}</code>\n"
            f"💰 Summa: <b>{_fmt_money(amount)} so'm</b>\n\n"
            "⚠️ Soxta chek yuborish botdan bloklanishga olib keladi.\n\n"
            "✅ Chek yuborilgandan so‘ng admin tomonidan tasdiqlanadi.",
            reply_markup=manual_topup_kb(await repo.get_language(call.from_user.id)),
        )
        return

    @router.callback_query(F.data == "t:send_proof")
    async def topup_send_proof(call: CallbackQuery):
        lang = await repo.get_language(call.from_user.id)
        await call.answer(t(lang, "kb.send_proof"), show_alert=True)

    @router.callback_query(F.data == "t:check")
    async def topup_check(call: CallbackQuery):
        await call.answer("⏳ ...", show_alert=True)

    @router.message(F.photo | F.document)
    async def topup_proof_message(message: Message):
        if not message.from_user:
            return

        pending = await repo.find_pending_manual_topup_needing_proof(message.from_user.id)
        if not pending:
            return

        proof_type = "photo" if message.photo else "document"
        proof_file_id = ""
        if message.photo:
            proof_file_id = message.photo[-1].file_id
        elif message.document:
            proof_file_id = message.document.file_id

        if not proof_file_id:
            return

        ok = await repo.attach_topup_proof(
            topup_id=int(pending["id"]),
            user_id=message.from_user.id,
            proof_file_id=proof_file_id,
            proof_type=proof_type,
            proof_caption=message.caption or "",
        )
        if ok:
            if log_chat:
                try:
                    ts = _now_hhmm()
                    header = f"<b>🧾 CHEK YUBORILDI</b>  <code>{ts}</code>" if ts else "<b>🧾 CHEK YUBORILDI</b>"
                    log_text = (
                        f"{header}\n"
                        f"<b>User:</b> <code>{int(message.from_user.id)}</code>\n"
                        f"<b>Topup ID:</b> <code>{int(pending['id'])}</code>\n"
                        f"<b>Tur:</b> <code>{proof_type}</code>"
                    )
                    asyncio.create_task(message.bot.send_message(log_chat, log_text))
                except Exception:
                    pass
            await message.answer(
                "✅ Chek qabul qilindi. Admin tekshiradi va tasdiqlaydi.\n\n"
                f"Topup ID: <code>{int(pending['id'])}</code>"
            )

    @router.message(F.text)
    async def topup_custom_amount_message(message: Message):
        if not message.from_user:
            return

        user_id = int(message.from_user.id)
        lang = await repo.get_language(user_id)
        provider = awaiting_custom_amount.get(user_id)
        if not provider:
            return

        raw = (message.text or "").strip()
        cleaned = raw.replace(" ", "").replace("'", "")
        if not cleaned.isdigit():
            await message.answer(
                "❗️ Summani faqat raqam bilan yuboring. Masalan: <code>25000</code> yoki <code>25 000</code>"
            )
            return

        amount = int(cleaned)
        if amount < 1000:
            await message.answer("❗️ Eng kam hisob to‘ldirish miqdori <b>1000 so'm</b>.")
            return
        if amount > 50_000_000:
            await message.answer("❗️ Noto‘g‘ri summa. Qaytadan kiriting.")
            return

        awaiting_custom_amount.pop(user_id, None)
        topup_id = await repo.create_topup(user_id, provider, amount)

        await message.answer(
            "👤 <b>To‘lov tartibi:</b>\n"
            "1️⃣ Admin ko‘rsatgan karta raqamiga to‘lovni amalga oshiring:\n"
            "💳 <code>5614 6887 1574 1061</code>\n"
            "👤 Shonazarov Behruz\n\n"
            "2️⃣ To‘lov chekini (screenshot yoki fayl) ushbu chatga yuboring 📩\n\n"
            f"🆔 Topup ID: <code>{topup_id}</code>\n"
            f"💰 Summa: <b>{_fmt_money(amount)} so'm</b>\n\n"
            "⚠️ Soxta chek yuborish botdan bloklanishga olib keladi.\n\n"
            "✅ Chek yuborilgandan so‘ng admin tomonidan tasdiqlanadi.",
            reply_markup=manual_topup_kb(lang),
        )
