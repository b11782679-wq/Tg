"""iCloud email checker handler - adapted for Telegram bot."""
import os
import asyncio
from aiogram import Router, F, Bot
from aiogram.types import CallbackQuery, Message
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, WebDriverException

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


def _use_selenium() -> bool:
    v = (os.getenv("ICLOUD_USE_SELENIUM", "").strip() or "0").lower()
    return v in {"1", "true", "yes", "on"}


def _is_headless() -> bool:
    v = (os.getenv("ICLOUD_HEADLESS", "").strip() or "1").lower()
    return v in {"1", "true", "yes", "on"}


def _get_workers() -> int:
    try:
        v = int(os.getenv("ICLOUD_WORKERS", "3"))
    except Exception:
        v = 3
    return max(1, min(8, v))


class ICloudSeleniumChecker:
    def __init__(self):
        self.driver = None
        self._setup_driver()

    def _setup_driver(self):
        chrome_options = Options()
        if _is_headless():
            chrome_options.add_argument("--headless=new")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1280,720")
        chrome_options.add_argument("--lang=en-US")
        chrome_options.add_argument("--log-level=3")

        if os.path.exists("/usr/bin/chromium"):
            chrome_options.binary_location = "/usr/bin/chromium"
        elif os.path.exists("/usr/bin/chromium-browser"):
            chrome_options.binary_location = "/usr/bin/chromium-browser"

        service = None
        if os.path.exists("/usr/bin/chromedriver"):
            service = Service("/usr/bin/chromedriver")

        if service:
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        else:
            self.driver = webdriver.Chrome(options=chrome_options)

    def close(self):
        try:
            if self.driver:
                self.driver.quit()
        except Exception:
            pass

    def check_email(self, email: str) -> dict:
        try:
            self.driver.get("https://appleid.apple.com/sign-in")

            email_input = None
            selectors = [
                (By.ID, "account_name_text_field"),
                (By.NAME, "account_name"),
                (By.CSS_SELECTOR, "input[type='text']"),
                (By.XPATH, "//input[contains(@id, 'account')]"),
            ]
            for sel_type, sel_val in selectors:
                try:
                    email_input = WebDriverWait(self.driver, 12).until(
                        EC.presence_of_element_located((sel_type, sel_val))
                    )
                    if email_input.is_displayed():
                        break
                except Exception:
                    continue

            if not email_input:
                return {"email": email, "exists": False, "status": "Element Not Found"}

            try:
                email_input.click()
            except Exception:
                pass
            try:
                email_input.clear()
            except Exception:
                pass
            email_input.send_keys(email)

            next_btn = None
            btn_selectors = [
                (By.ID, "sign-in"),
                (By.ID, "continue"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ]
            for sel_type, sel_val in btn_selectors:
                try:
                    next_btn = WebDriverWait(self.driver, 8).until(
                        EC.element_to_be_clickable((sel_type, sel_val))
                    )
                    break
                except Exception:
                    continue
            if next_btn:
                try:
                    next_btn.click()
                except Exception:
                    pass

            try:
                WebDriverWait(self.driver, 10).until(
                    lambda d: (
                        "password" in (d.page_source or "").lower()
                        or "not found" in (d.page_source or "").lower()
                        or "doesn't exist" in (d.page_source or "").lower()
                    )
                )
            except Exception:
                pass

            try:
                pwd = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
                if any(el.is_displayed() for el in pwd):
                    return {"email": email, "exists": True, "status": "Valid"}
            except Exception:
                pass

            src = (self.driver.page_source or "").lower()
            if "password" in src:
                return {"email": email, "exists": True, "status": "Valid"}
            if "not found" in src or "doesn't exist" in src:
                return {"email": email, "exists": False, "status": "Not Found"}
            return {"email": email, "exists": False, "status": "Unknown"}

        except TimeoutException:
            return {"email": email, "exists": False, "status": "Timeout"}
        except WebDriverException as e:
            return {"email": email, "exists": False, "status": f"Error: {str(e)[:80]}"}
        except Exception as e:
            return {"email": email, "exists": False, "status": f"Error: {str(e)[:80]}"}


class iCloudStates(StatesGroup):
    waiting_emails = State()


def _estimate_minutes(n: int) -> int:
    if n <= 0:
        return 0
    if _use_selenium():
        workers = _get_workers()
        # Conservative estimate per email; actual depends on Apple response time.
        per_email_sec = 20
        total_sec = int((n * per_email_sec) / max(1, workers))
    else:
        per_email_sec = 3
        total_sec = int(n * per_email_sec)
    return max(1, int((total_sec + 59) // 60))


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
        mode = "Selenium" if _use_selenium() else "HTTP"
        workers = _get_workers() if _use_selenium() else 1
        eta_min = _estimate_minutes(len(emails))
        await msg.edit_text(
            f"🔍 <b>{len(emails)} ta email tekshirilmoqda...</b>\n\n"
            f"⚙️ Rejim: <b>{mode}</b> | Workers: <b>{workers}</b>\n"
            f"⏱️ Taxminiy vaqt: <b>{eta_min} daqiqa</b>\n"
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
        mode = "Selenium" if _use_selenium() else "HTTP"
        workers = _get_workers() if _use_selenium() else 1
        eta_min = _estimate_minutes(len(emails))
        msg = await message.answer(
            f"🔍 <b>{len(emails)} ta email tekshirilmoqda...</b>\n\n"
            f"⚙️ Rejim: <b>{mode}</b> | Workers: <b>{workers}</b>\n"
            f"⏱️ Taxminiy vaqt: <b>{eta_min} daqiqa</b>\n"
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

    selenium_enabled = _use_selenium()

    total = len(emails)
    processed = 0
    processed_lock = asyncio.Lock()
    results_lock = asyncio.Lock()

    async def _bump_progress():
        nonlocal processed
        async with processed_lock:
            processed += 1
            p = processed
        if p % 10 == 0 or p == total:
            try:
                mode = "Selenium" if selenium_enabled else "HTTP"
                workers = _get_workers() if selenium_enabled else 1
                async with results_lock:
                    ok_n = len([r for r in results if r.get('exists')])
                    bad_n = len([r for r in results if not r.get('exists')])
                await msg.edit_text(
                    f"🔍 <b>Progress:</b> {p}/{total}\n"
                    f"⚙️ Rejim: <b>{mode}</b> | Workers: <b>{workers}</b>\n"
                    f"✅ Mavjud: {ok_n} | "
                    f"❌ Yo'q: {bad_n}",
                    parse_mode="HTML"
                )
            except Exception:
                pass

    if selenium_enabled:
        workers = _get_workers()
        if workers > total:
            workers = total

        buckets: list[list[str]] = [[] for _ in range(workers)]
        for idx, email in enumerate(emails):
            buckets[idx % workers].append(email)

        async def _selenium_worker(worker_emails: list[str]) -> list[dict]:
            local_results: list[dict] = []
            checker = None
            try:
                checker = await asyncio.to_thread(ICloudSeleniumChecker)
            except Exception as e:
                for em in worker_emails:
                    r = {"email": em, "exists": False, "status": f"Selenium init failed: {str(e)[:80]}"}
                    local_results.append(r)
                    async with results_lock:
                        results.append(r)
                    await _bump_progress()
                return local_results

            try:
                for em in worker_emails:
                    try:
                        r = await asyncio.to_thread(checker.check_email, em)
                        r = r or {"email": em, "exists": False, "status": "Unknown"}
                        if r.get("status") in {"Valid", "Not Found"}:
                            r["status"] = f"{r['status']} (Selenium)"
                        local_results.append(r)
                    except Exception as e:
                        r = {"email": em, "exists": False, "status": f"Error: {str(e)[:80]}"}
                        local_results.append(r)
                        async with results_lock:
                            results.append(r)
                        await _bump_progress()
                        continue

                    async with results_lock:
                        results.append(r)
                    await _bump_progress()
            finally:
                if checker:
                    try:
                        await asyncio.to_thread(checker.close)
                    except Exception:
                        pass
            return local_results

        tasks = [asyncio.create_task(_selenium_worker(bucket)) for bucket in buckets if bucket]
        for done in await asyncio.gather(*tasks):
            results.extend(done)

    else:
        for i, email in enumerate(emails, 1):
            try:
                result = await check_email_http(email)
                results.append(result)
            except Exception as e:
                results.append({
                    "email": email,
                    "exists": False,
                    "status": f"Error: {str(e)[:80]}"
                })
            await _bump_progress()
            if i < len(emails):
                await asyncio.sleep(2)
    
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
