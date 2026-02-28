import asyncio
import os

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

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
    dp.include_router(h_topup.router)
    dp.include_router(h_admin.router)
    dp.include_router(h_youtube_auto.router)

    app = FastAPI()
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
                due = await repo.yt_claim_due_uploads(limit=3)
                for r in due:
                    upload_id = int(r["id"])
                    user_id = int(r["user_id"])
                    file_path = str(r["file_path"] or "")
                    title = str(r["title"] or "")
                    description = str(r["description"] or "")
                    visibility = str(r["visibility"] or "private")
                    scheduled_at = str(r["scheduled_at"] or "").strip() or None

                    try:
                        token_json = await repo.yt_get_token(user_id)
                        if not token_json:
                            raise RuntimeError("Not connected")
                        if not file_path or (not os.path.exists(file_path)):
                            raise RuntimeError("File not found")

                        video_id, new_token_json = await asyncio.to_thread(
                            upload_video,
                            token_json,
                            file_path,
                            title,
                            description,
                            visibility,
                            scheduled_at,
                        )
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
            except Exception:
                pass
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
