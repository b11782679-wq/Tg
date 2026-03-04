import asyncio
import os
import traceback
import secrets
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from aiogram.types import ErrorEvent

import uvicorn
from fastapi import FastAPI

from bot.config import load_config
from bot.db.sqlite import init_db
from bot.db.repo import Repo

from bot.web.admin_app import create_admin_app, create_youtube_oauth_router

from bot.middlewares.subscribe import SubscribeMiddleware
from bot.middlewares.activity_log import ActivityLogMiddleware

from bot.handlers import subscription as h_subscription
from bot.handlers import start as h_start
from bot.handlers import products as h_products
from bot.handlers import youtuber as h_youtuber
from bot.handlers import language as h_language
from bot.handlers import referral as h_referral
from bot.handlers import stats as h_stats
from bot.handlers import profile as h_profile
from bot.handlers import tts as h_tts
from bot.handlers import telegram as h_telegram
from bot.handlers import topup as h_topup
from bot.handlers import admin as h_admin
from bot.handlers import youtube_auto as h_youtube_auto

from bot.services.youtube_uploader import upload_video


async def start():
    cfg = load_config()
    await init_db(cfg.db_path)
    repo = Repo(cfg.db_path)

    bot = Bot(
        token=cfg.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )

    dp = Dispatcher()

    async def _send_admin_error(title: str, exc: BaseException):
        if not cfg.admin_chat_id:
            return
        try:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            tb = (tb or "")[-3500:]
            await bot.send_message(cfg.admin_chat_id, f"<b>{title}</b>\n\n<code>{tb}</code>")
        except Exception:
            pass

    async def _send_log(text: str):
        if not cfg.log_channel:
            return
        try:
            await bot.send_message(cfg.log_channel, text, disable_web_page_preview=True)
        except Exception:
            pass

    @dp.error()
    async def _global_error_handler(event: ErrorEvent):
        try:
            update = getattr(event, "update", None)
            message = None
            if update:
                message = getattr(update, "message", None)
                if not message:
                    cq = getattr(update, "callback_query", None)
                    message = getattr(cq, "message", None) if cq else None
                if not message:
                    iq = getattr(update, "inline_query", None)
                    message = getattr(iq, "message", None) if iq else None

            if message:
                try:
                    await message.answer("❌ Xatolik yuz berdi. Iltimos, qaytadan urinib ko‘ring.")
                except Exception:
                    pass

            tb = "".join(traceback.format_exception(type(event.exception), event.exception, event.exception.__traceback__))
            tb = (tb or "")[-3500:]
            if cfg.admin_chat_id:
                try:
                    await bot.send_message(
                        cfg.admin_chat_id,
                        "<b>BOT ERROR</b>\n\n" + f"<code>{tb}</code>",
                    )
                except Exception:
                    pass
        except Exception:
            pass

    # Kanalga a’zolikni hamma joyda tekshiradi
    dp.message.middleware(SubscribeMiddleware(repo))
    dp.callback_query.middleware(SubscribeMiddleware(repo))

    if cfg.log_channel:
        dp.message.middleware(ActivityLogMiddleware(cfg.log_channel))
        dp.callback_query.middleware(ActivityLogMiddleware(cfg.log_channel))

    # subscription: sub:check tugmasi ishlashi uchun (FAqat 1 marta)
    h_subscription.setup(repo)
    dp.include_router(h_subscription.router)

    # qolgan handlerlar
    h_start.setup(repo)
    h_products.setup(repo)
    h_youtuber.setup(repo)
    h_language.setup(repo)
    h_referral.setup(repo)
    h_stats.setup(repo)
    h_profile.setup(repo)
    h_tts.setup(repo)
    h_telegram.setup(repo)
    h_topup.setup(repo)
    h_admin.setup(repo, cfg)
    h_youtube_auto.setup(repo, cfg)

    dp.include_router(h_start.router)
    dp.include_router(h_products.router)
    dp.include_router(h_youtuber.router)
    dp.include_router(h_language.router)
    dp.include_router(h_referral.router)
    dp.include_router(h_stats.router)
    dp.include_router(h_profile.router)
    dp.include_router(h_tts.router)
    dp.include_router(h_telegram.router)
    dp.include_router(h_topup.router)
    dp.include_router(h_admin.router)
    dp.include_router(h_youtube_auto.router)

    app = FastAPI()

    @app.middleware("http")
    async def _security_headers(request, call_next):
        response = await call_next(request)
        path = getattr(request.url, "path", "") or ""
        if path.startswith("/admin") or path.startswith("/yt/oauth"):
            response.headers.setdefault("X-Frame-Options", "DENY")
            response.headers.setdefault("X-Content-Type-Options", "nosniff")
            response.headers.setdefault("Referrer-Policy", "no-referrer")
            response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
            response.headers.setdefault("Cross-Origin-Opener-Policy", "same-origin")
            response.headers.setdefault("Cross-Origin-Resource-Policy", "same-origin")
            response.headers.setdefault("Cache-Control", "no-store")
            response.headers.setdefault("Pragma", "no-cache")
        return response
    admin_router = create_admin_app(cfg, repo)
    app.include_router(admin_router, prefix="/admin")

    yt_oauth_router = create_youtube_oauth_router(cfg, repo)
    app.include_router(yt_oauth_router)

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=cfg.admin_panel_host,
            port=cfg.admin_panel_port,
            log_level="warning",
        )
    )

    async def _yt_worker():
        while True:
            try:
                try:
                    reset_n = await repo.yt_reset_stuck_uploads(max_age_minutes=25)
                    if reset_n and cfg.admin_chat_id:
                        try:
                            await bot.send_message(cfg.admin_chat_id, f"<b>YT RECOVERY</b>\n\nReset stuck uploads: <code>{int(reset_n)}</code>")
                        except Exception:
                            pass
                    if reset_n:
                        await _send_log(f"<b>YT RECOVERY</b>\nReset stuck uploads: <code>{int(reset_n)}</code>")
                except Exception as e:
                    await _send_admin_error("YT WORKER RECOVERY ERROR", e)

                try:
                    bad = await repo.yt_fail_unconnected_due_uploads(limit=10)
                    for r in bad:
                        uid = int(r["user_id"])
                        up_id = int(r["id"])
                        title = str(r["title"] or "")
                        try:
                            await bot.send_message(
                                uid,
                                "❌ YouTube upload bekor qilindi.\n\n"
                                f"ID: <code>{up_id}</code>\n"
                                "Sabab: kanal ulanmagan.\n\n"
                                "Iltimos: <b>🤖 Avtomatlashtirilgan YouTube</b> → <b>🔗 Kanalni ulash</b> ni bosing.",
                            )
                        except Exception as e:
                            await _send_log(
                                "<b>YT UNCONNECTED NOTIFY FAILED</b>\n"
                                f"User: <code>{uid}</code>\n"
                                f"Upload ID: <code>{up_id}</code>\n"
                                f"Error: <code>{str(e)[:350]}</code>"
                            )
                            await _send_admin_error(f"YT UNCONNECTED NOTIFY FAILED (id={int(up_id)})", e)
                        await _send_log(
                            "<b>YT UNCONNECTED</b>\n"
                            f"User: <code>{uid}</code>\n"
                            f"Upload ID: <code>{up_id}</code>\n"
                            + (f"Title: <b>{title}</b>" if title else "")
                        )
                except Exception as e:
                    await _send_admin_error("YT FAIL UNCONNECTED ERROR", e)

                due = await repo.yt_claim_due_uploads(limit=3)
                for r in due:
                    upload_id = int(r["id"])
                    user_id = int(r["user_id"])
                    file_path = str(r["file_path"] or "")
                    tg_file_id = str(r["tg_file_id"] or "")
                    title = str(r["title"] or "")
                    description = str(r["description"] or "")
                    visibility = str(r["visibility"] or "private")
                    scheduled_at = str(r["scheduled_at"] or "").strip() or None
                    # Extract metadata fields
                    made_for_kids = int(r["made_for_kids"] or 0)
                    tags = str(r["tags"] or "")
                    category = str(r["category"] or "")
                    language = str(r["language"] or "")
                    recording_date = str(r["recording_date"] or "").strip() or None
                    video_location = str(r["video_location"] or "")
                    licence = str(r["licence"] or "Standard YouTube licence")
                    allow_embedding = int(r["allow_embedding"] or 1)
                    shorts_remixing = str(r["shorts_remixing"] or "allow_video_audio")
                    comments = str(r["comments"] or "on")
                    age_restricted = int(r["age_restricted"] or 0)
                    paid_promotion = int(r["paid_promotion"] or 0)
                    altered_content = int(r["altered_content"] or 0)

                    try:
                        try:
                            await bot.send_message(
                                user_id,
                                "⏳ YouTube upload boshlandi...\n\n"
                                f"ID: <code>{upload_id}</code>\n"
                                + (f"Title: <b>{title}</b>\n" if title else "")
                                + (f"Visibility: <code>{visibility}</code>" if visibility else ""),
                            )
                        except Exception:
                            pass

                        await _send_log(
                            "<b>YT UPLOAD START</b>\n"
                            f"User: <code>{user_id}</code>\n"
                            f"ID: <code>{upload_id}</code>\n"
                            + (f"Title: <b>{title}</b>\n" if title else "")
                            + (f"Visibility: <code>{visibility}</code>" if visibility else "")
                        )

                        token_json = await repo.yt_get_token(user_id)
                        if not token_json:
                            raise RuntimeError("Not connected")

                        if not file_path or (not os.path.exists(file_path)):
                            # Fallback: re-download from Telegram using stored file_id
                            if tg_file_id:
                                tmp_dir = Path("tmp") / "yt"
                                tmp_dir.mkdir(parents=True, exist_ok=True)
                                safe_name = secrets.token_hex(12) + "_video.mp4"
                                dest = tmp_dir / safe_name
                                try:
                                    tg_file = await bot.get_file(tg_file_id)
                                    await bot.download_file(tg_file.file_path, destination=dest)
                                    file_path = str(dest)
                                except Exception as e:
                                    raise RuntimeError(f"File not found (redownload failed: {str(e)[:120]})")
                            else:
                                raise RuntimeError("File not found")

                        try:
                            size_bytes = int(os.path.getsize(file_path))
                        except Exception:
                            size_bytes = 0
                        timeout_sec = 180 if size_bytes < (100 * 1024 * 1024) else 300

                        try:
                            video_id, new_token_json = await asyncio.wait_for(
                                asyncio.to_thread(
                                    upload_video,
                                    token_json,
                                    file_path,
                                    title,
                                    description,
                                    visibility,
                                    scheduled_at,
                                    made_for_kids,
                                    tags,
                                    category,
                                    language,
                                    recording_date,
                                    video_location,
                                    licence,
                                    allow_embedding,
                                    shorts_remixing,
                                    comments,
                                    age_restricted,
                                    paid_promotion,
                                    altered_content,
                                ),
                                timeout=float(timeout_sec),
                            )
                        except asyncio.TimeoutError:
                            raise RuntimeError(f"Upload timeout ({timeout_sec}s)")
                        if new_token_json and new_token_json != token_json:
                            await repo.yt_set_token(user_id, new_token_json)

                        try:
                            os.remove(file_path)
                        except Exception:
                            pass

                        await repo.yt_mark_upload_done(upload_id)
                        await repo.yt_delete_pending_upload(upload_id)

                        await bot.send_message(
                            user_id,
                            "✅ YouTube’ga video yuklandi!\n\n"
                            f"Video ID: <code>{video_id}</code>\n"
                            f"Link: https://youtu.be/{video_id}",
                            disable_web_page_preview=True,
                        )
                        await _send_log(
                            "<b>YT UPLOAD DONE</b>\n"
                            f"User: <code>{user_id}</code>\n"
                            f"ID: <code>{upload_id}</code>\n"
                            f"Video ID: <code>{video_id}</code>\n"
                            f"Link: https://youtu.be/{video_id}"
                        )
                    except Exception as e:
                        await repo.yt_mark_upload_failed(upload_id, str(e))
                        try:
                            await bot.send_message(
                                user_id,
                                "❌ YouTube upload xatolik.\n\n"
                                f"ID: <code>{upload_id}</code>\n"
                                f"<code>{str(e)[:350]}</code>",
                            )
                        except Exception:
                            pass
                        await _send_admin_error(f"YT UPLOAD FAILED (id={int(upload_id)})", e)
                        await _send_log(
                            "<b>YT UPLOAD FAILED</b>\n"
                            f"User: <code>{user_id}</code>\n"
                            f"ID: <code>{upload_id}</code>\n"
                            f"Error: <code>{str(e)[:350]}</code>"
                        )
            except Exception:
                await _send_admin_error("YT WORKER LOOP ERROR", Exception("Worker loop crashed"))
            await asyncio.sleep(15)

    web_task = asyncio.create_task(server.serve())
    yt_task = asyncio.create_task(_yt_worker())
    try:
        await dp.start_polling(bot)
    finally:
        server.should_exit = True
        try:
            await web_task
        except Exception:
            pass
        try:
            yt_task.cancel()
        except Exception:
            pass
