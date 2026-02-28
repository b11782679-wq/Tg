from __future__ import annotations

import json
import datetime
from zoneinfo import ZoneInfo

from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


class YouTubeUploadError(Exception):
    pass


def to_utc_sqlite_datetime(local_dt_str: str, timezone_str: str) -> str:
    """Convert 'YYYY-MM-DD HH:MM' in given timezone to UTC 'YYYY-MM-DD HH:MM:SS'."""
    s = (local_dt_str or "").strip()
    tzs = (timezone_str or "").strip()
    if not s or not tzs:
        raise YouTubeUploadError("Missing datetime/timezone")

    try:
        local_dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M")
    except Exception:
        raise YouTubeUploadError("Invalid datetime format. Use YYYY-MM-DD HH:MM")

    try:
        tz = ZoneInfo(tzs)
    except Exception:
        raise YouTubeUploadError("Invalid timezone. Example: Asia/Tashkent")

    local_dt = local_dt.replace(tzinfo=tz)
    utc_dt = local_dt.astimezone(datetime.timezone.utc)
    return utc_dt.strftime("%Y-%m-%d %H:%M:%S")


def to_rfc3339_utc(sqlite_utc_dt: str) -> str:
    """Convert UTC sqlite datetime 'YYYY-MM-DD HH:MM:SS' -> RFC3339 '...Z'."""
    s = (sqlite_utc_dt or "").strip()
    if not s:
        raise YouTubeUploadError("Missing scheduled_at")
    try:
        dt = datetime.datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=datetime.timezone.utc)
    except Exception:
        raise YouTubeUploadError("Invalid scheduled_at")
    return dt.isoformat().replace("+00:00", "Z")


def load_credentials(token_json: str) -> Credentials:
    raw = (token_json or "").strip()
    if not raw:
        raise YouTubeUploadError("Not connected")
    try:
        info = json.loads(raw)
    except Exception:
        raise YouTubeUploadError("Invalid token")

    creds = Credentials.from_authorized_user_info(info, scopes=SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                raise YouTubeUploadError(f"Token refresh failed: {e}")
        else:
            raise YouTubeUploadError("Token invalid or expired")
    return creds


def upload_video(
    token_json: str,
    file_path: str,
    title: str,
    description: str,
    visibility: str,
    scheduled_at_utc: str | None,
) -> tuple[str, str]:
    """Upload video. Returns (video_id, new_token_json)."""
    creds = load_credentials(token_json)

    vis = (visibility or "private").strip().lower()
    if vis not in ("public", "unlisted", "private"):
        vis = "private"

    status: dict[str, object] = {"privacyStatus": vis}
    if scheduled_at_utc:
        # YouTube scheduling requires private + publishAt
        status["privacyStatus"] = "private"
        status["publishAt"] = to_rfc3339_utc(scheduled_at_utc)

    body = {
        "snippet": {
            "title": str(title or "")[:95],
            "description": str(description or "")[:5000],
            "categoryId": "22",
        },
        "status": status,
    }

    try:
        youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)
        media = MediaFileUpload(str(file_path), resumable=True)
        req = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        resp = None
        while resp is None:
            status_up, resp = req.next_chunk()
        video_id = str((resp or {}).get("id") or "")
        if not video_id:
            raise YouTubeUploadError("Upload failed: no video id")
        return video_id, creds.to_json()
    except YouTubeUploadError:
        raise
    except Exception as e:
        raise YouTubeUploadError(str(e))
