import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass
class Config:
    bot_token: str
    admin_id: int
    db_path: str
    admin_panel_host: str
    admin_panel_port: int
    admin_public_url: str
    admin_panel_user: str
    admin_panel_pass: str
    log_channel: str
    youtube_oauth_client_id: str
    youtube_oauth_client_secret: str
    youtube_oauth_redirect_url: str

def load_config() -> Config:
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN topilmadi. .env ga BOT_TOKEN=... qo‘ying.")
    admin_id = int(os.getenv("ADMIN_ID", "0"))
    if admin_id == 0:
        raise RuntimeError("ADMIN_ID topilmadi. .env ga ADMIN_ID=... qo‘ying.")
    db_path = os.getenv("DB_PATH", "bot_data.sqlite3")

    admin_panel_host = os.getenv("ADMIN_PANEL_HOST", "0.0.0.0")
    port_env = (os.getenv("PORT") or "").strip()
    admin_panel_port = int(port_env) if port_env else int(os.getenv("ADMIN_PANEL_PORT", "8080"))
    admin_public_url = (os.getenv("ADMIN_PUBLIC_URL") or "").strip().rstrip("/")
    admin_panel_user = os.getenv("ADMIN_PANEL_USER", "admin")
    admin_panel_pass = os.getenv("ADMIN_PANEL_PASS", "admin")

    log_channel = (os.getenv("LOG_CHANNEL") or "@brainrot_videos").strip()
    if not log_channel:
        log_channel = "@brainrot_videos"

    youtube_oauth_client_id = (os.getenv("YOUTUBE_OAUTH_CLIENT_ID") or "").strip()
    youtube_oauth_client_secret = (os.getenv("YOUTUBE_OAUTH_CLIENT_SECRET") or "").strip()
    youtube_oauth_redirect_url = (os.getenv("YOUTUBE_OAUTH_REDIRECT_URL") or "").strip()

    return Config(
        bot_token=token,
        admin_id=admin_id,
        db_path=db_path,
        admin_panel_host=admin_panel_host,
        admin_panel_port=admin_panel_port,
        admin_public_url=admin_public_url,
        admin_panel_user=admin_panel_user,
        admin_panel_pass=admin_panel_pass,
        log_channel=log_channel,
        youtube_oauth_client_id=youtube_oauth_client_id,
        youtube_oauth_client_secret=youtube_oauth_client_secret,
        youtube_oauth_redirect_url=youtube_oauth_redirect_url,
    )
