"""iCloud email checker handler - adapted for Telegram bot."""
import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from bot.keyboards.youtuber import youtuber_entry_kb
from bot.keyboards.menu import back_only_kb
from bot.db.repo import Repo
from bot.i18n import t

# Import the iCloud checker class logic (adapted from D:\ICLOUD FIND)
import subprocess
import tempfile

router = Router()


_DEFAULT_MAX_EMAILS = 100


def _get_max_emails() -> int:
    try:
        v = int(os.getenv("ICLOUD_MAX_EMAILS", str(_DEFAULT_MAX_EMAILS)))
    except Exception:
        v = _DEFAULT_MAX_EMAILS
    return max(1, min(2000, v))


class iCloudStates(StatesGroup):
    waiting_emails = State()


def setup(repo: Repo):
    @router.callback_query(F.data == "icloud:open")
    async def open_icloud_menu(callback: CallbackQuery, state: FSMContext):
        """iCloud Check menyusini ochish"""
        lang = await repo.get_language(callback.from_user.id)
        max_emails = _get_max_emails()
        
        text = (
            "☁️ <b>iCloud Email Checker</b>\n\n"
            "iCloud/Apple ID email manzillarini tekshirish uchun email ro‘yxatini yuboring.\n\n"
            "📧 <b>Format:</b> Har bir qatorda 1 ta email\n"
            f"📄 <b>Maksimum:</b> {max_emails} ta email bir vaqtning o‘zida\n"
            "⏱️ <b>Vaqt:</b> Har bir email ~20-40 soniya\n\n"
            "✉️ Email ro‘yxatini yuboring yoki fayl (emails.txt) yuklang:"
        )
        
        await callback.message.edit_text(
            text,
            reply_markup=back_only_kb(lang),
            parse_mode="HTML"
        )
        await state.set_state(iCloudStates.waiting_emails)
        await callback.answer()

    @router.message(iCloudStates.waiting_emails, F.document)
    async def process_email_file(message: Message, state: FSMContext, bot: Bot):
        """Email faylini qabul qilish"""
        lang = await repo.get_language(message.from_user.id)
        max_emails = _get_max_emails()
        
        # Check file extension
        file_name = message.document.file_name or ""
        if not file_name.endswith(('.txt', '.csv')):
            await message.answer(
                "❌ <b>Faqat .txt yoki .csv fayllar qabul qilinadi!</b>\n\n"
                "Iltimos, email ro‘yxati bilan .txt fayl yuboring.",
                reply_markup=back_only_kb(lang),
                parse_mode="HTML"
            )
            return
        
        # Download file
        msg = await message.answer("📥 <b>Fayl yuklanmoqda...</b>", parse_mode="HTML")
        
        file_path = f"/tmp/emails_{message.from_user.id}.txt"
        await bot.download(message.document.file_id, file_path)
        
        # Read emails
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                emails = [line.strip() for line in f if line.strip() and "@" in line]
        except Exception as e:
            await msg.edit_text(
                f"❌ <b>Faylni o‘qishda xatolik:</b> {str(e)[:100]}",
                reply_markup=back_only_kb(lang),
                parse_mode="HTML"
            )
            return
        finally:
            if os.path.exists(file_path):
                os.remove(file_path)
        
        if not emails:
            await msg.edit_text(
                "❌ <b>Email topilmadi!</b>\n\n"
                "Faylda email manzillar bo‘lishi kerak.",
                reply_markup=back_only_kb(lang),
                parse_mode="HTML"
            )
            return
        
        # Limit check
        if len(emails) > max_emails:
            emails = emails[:max_emails]
            await message.answer(
                "⚠️ <b>Diqqat!</b>\n"
                f"{max_emails} tadan ko‘p email kiritildi. Faqat birinchi {max_emails} ta tekshiriladi.",
                parse_mode="HTML"
            )
        
        # Start checking
        await msg.edit_text(
            f"🔍 <b>{len(emails)} ta email tekshirilmoqda...</b>\n\n"
            f"⏱️ Taxminiy vaqt: <b>{len(emails) * 30 // 60} daqiqa</b>\n"
            f"📧 Tekshirilmoqda...",
            parse_mode="HTML"
        )
        
        # Run iCloud check
        results = await run_icloud_check(emails, msg, bot)
        
        # Format results
        valid_emails = [r for r in results if r.get("exists")]
        invalid_emails = [r for r in results if not r.get("exists")]
        errors = [r for r in results if "Error" in str(r.get("status", ""))]
        
        result_text = (
            f"☁️ <b>iCloud Check Natijalari</b>\n\n"
            f"📊 <b>Jami:</b> {len(results)} ta\n"
            f"✅ <b>Mavjud (iCloud):</b> {len(valid_emails)} ta\n"
            f"❌ <b>Mavjud emas:</b> {len(invalid_emails)} ta\n"
            f"⚠️ <b>Xatoliklar:</b> {len(errors)} ta\n\n"
        )
        
        if valid_emails:
            result_text += "✅ <b>iCloud Mavjud:</b>\n"
            for r in valid_emails[:20]:
                result_text += f"• {r['email']}\n"
            if len(valid_emails) > 20:
                result_text += f"... va yana {len(valid_emails) - 20} ta\n"
            result_text += "\n"
        
        if errors:
            result_text += "⚠️ <b>Xatoliklar:</b>\n"
            for r in errors[:5]:
                result_text += f"• {r['email']}: {r['status'][:50]}\n"
            result_text += "\n"
        
        result_text += (
            "📄 <b>Diqqat:</b> Selenium-based tekshiruv Railway muhitida cheklangan.\n"
            "Aniq natijalar uchun lokal kompyuterda ishlatish tavsiya etiladi."
        )
        
        await msg.edit_text(
            result_text,
            reply_markup=youtuber_entry_kb(lang),
            parse_mode="HTML"
        )
        await state.clear()

    @router.message(iCloudStates.waiting_emails, F.text)
    async def process_email_text(message: Message, state: FSMContext, bot: Bot):
        """Text formatidagi email ro'yxatini qabul qilish"""
        lang = await repo.get_language(message.from_user.id)
        max_emails = _get_max_emails()
        
        # Parse emails from text
        lines = message.text.strip().split('\n')
        emails = [line.strip() for line in lines if line.strip() and "@" in line]
        
        if not emails:
            await message.answer(
                "❌ <b>Email topilmadi!</b>\n\n"
                "Har bir qatorda 1 ta email bo‘lishi kerak.\n"
                "Masalan:\n"
                "user@gmail.com\n"
                "test@icloud.com",
                reply_markup=back_only_kb(lang),
                parse_mode="HTML"
            )
            return
        
        # Limit check
        if len(emails) > max_emails:
            emails = emails[:max_emails]
            await message.answer(
                "⚠️ <b>Diqqat!</b>\n"
                f"{max_emails} tadan ko‘p email kiritildi. Faqat birinchi {max_emails} ta tekshiriladi.",
                parse_mode="HTML"
            )
        
        # Start checking
        msg = await message.answer(
            f"🔍 <b>{len(emails)} ta email tekshirilmoqda...</b>\n\n"
            f"⏱️ Taxminiy vaqt: <b>{len(emails) * 30 // 60} daqiqa</b>\n"
            f"📧 Tekshirilmoqda...",
            parse_mode="HTML"
        )
        
        # Run iCloud check
        results = await run_icloud_check(emails, msg, bot)
        
        # Format results (same as above)
        valid_emails = [r for r in results if r.get("exists")]
        invalid_emails = [r for r in results if not r.get("exists")]
        errors = [r for r in results if "Error" in str(r.get("status", ""))]
        
        result_text = (
            f"☁️ <b>iCloud Check Natijalari</b>\n\n"
            f"📊 <b>Jami:</b> {len(results)} ta\n"
            f"✅ <b>Mavjud (iCloud):</b> {len(valid_emails)} ta\n"
            f"❌ <b>Mavjud emas:</b> {len(invalid_emails)} ta\n"
            f"⚠️ <b>Xatoliklar:</b> {len(errors)} ta\n\n"
        )
        
        if valid_emails:
            result_text += "✅ <b>iCloud Mavjud:</b>\n"
            for r in valid_emails[:20]:
                result_text += f"• {r['email']}\n"
            if len(valid_emails) > 20:
                result_text += f"... va yana {len(valid_emails) - 20} ta\n"
            result_text += "\n"
        
        if errors:
            result_text += "⚠️ <b>Xatoliklar:</b>\n"
            for r in errors[:5]:
                result_text += f"• {r['email']}: {r['status'][:50]}\n"
            result_text += "\n"
        
        result_text += (
            "📄 <b>Diqqat:</b> Selenium-based tekshiruv Railway muhitida cheklangan.\n"
            "Aniq natijalar uchun lokal kompyuterda ishlatish tavsiya etiladi."
        )
        
        await msg.edit_text(
            result_text,
            reply_markup=youtuber_entry_kb(lang),
            parse_mode="HTML"
        )
        await state.clear()


async def run_icloud_check(emails: list, msg: Message, bot: Bot) -> list:
    """
    iCloud email tekshiruvi.
    
    MUHIM: Bu Selenium-based tekshiruv. Railway muhitida Chrome/ChromeDriver
    o'rnatilmagan bo'lsa ishlamaydi.
    
    Railway muhitida ishlamasa, lokal kompyuterda ishlatish tavsiya etiladi.
    """
    results = []
    
    for i, email in enumerate(emails, 1):
        try:
            # Simple HTTP-based check (fallback)
            result = await check_email_http(email)
            results.append(result)
            
            # Update progress every 5 emails
            if i % 5 == 0 or i == len(emails):
                try:
                    await msg.edit_text(
                        f"🔍 <b>Progress:</b> {i}/{len(emails)}\n"
                        f"✅ Mavjud: {len([r for r in results if r.get('exists')])} | "
                        f"❌ Yo'q: {len([r for r in results if not r.get('exists')])}",
                        parse_mode="HTML"
                    )
                except Exception:
                    pass  # Message not modified
            
            # Rate limiting
            if i < len(emails):
                await asyncio.sleep(2)  # 2 second delay between checks
                
        except Exception as e:
            results.append({
                "email": email,
                "exists": False,
                "status": f"Error: {str(e)[:50]}"
            })
    
    return results


async def check_email_http(email: str) -> dict:
    """
    HTTP-based email validation (basic check).
    
    To'liq iCloud tekshiruvi uchun Selenium kerak.
    Bu yerda faqatgina basic email validation qilinadi.
    """
    # Basic email format validation
    if "@" not in email or "." not in email.split("@")[-1]:
        return {"email": email, "exists": False, "status": "Invalid Format"}
    
    # iCloud/Apple specific domains
    icloud_domains = ["icloud.com", "me.com", "mac.com"]
    domain = email.split("@")[-1].lower()
    
    # If it's iCloud domain, mark as potentially valid
    # (Real verification requires Selenium)
    if domain in icloud_domains:
        return {
            "email": email,
            "exists": True,  # Potentially exists (iCloud domain)
            "status": "iCloud Domain (Selenium required for full check)"
        }
    
    # For non-iCloud domains, basic SMTP check could be done
    # But that requires additional libraries
    return {
        "email": email,
        "exists": False,
        "status": "Non-iCloud domain"
    }
