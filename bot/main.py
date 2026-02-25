import asyncio

from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

import uvicorn
from fastapi import FastAPI

from bot.config import load_config
from bot.db.sqlite import init_db
from bot.db.repo import Repo

from bot.web.admin_app import create_admin_app

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

    dp.include_router(h_start.router)
    dp.include_router(h_products.router)
    dp.include_router(h_youtuber.router)
    dp.include_router(h_language.router)
    dp.include_router(h_referral.router)
    dp.include_router(h_stats.router)
    dp.include_router(h_profile.router)
    dp.include_router(h_topup.router)
    dp.include_router(h_admin.router)

    app = FastAPI()
    admin_router = create_admin_app(cfg, repo)
    app.include_router(admin_router, prefix="/admin")

    server = uvicorn.Server(
        uvicorn.Config(
            app,
            host=cfg.admin_panel_host,
            port=cfg.admin_panel_port,
            log_level="warning",
        )
    )

    web_task = asyncio.create_task(server.serve())
    try:
        await dp.start_polling(bot)
    finally:
        server.should_exit = True
        try:
            await web_task
        except Exception:
            pass
