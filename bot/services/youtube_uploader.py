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
    made_for_kids: int = 0,
    tags: str = "",
    category: str = "",
    language: str = "",
    recording_date: str | None = None,
    video_location: str = "",
    licence: str = "Standard YouTube licence",
    allow_embedding: int = 1,
    shorts_remixing: str = "allow_video_audio",
    comments: str = "on",
    age_restricted: int = 0,
    paid_promotion: int = 0,
    altered_content: int = 0,
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

    # Made for Kids
    status["madeForKids"] = bool(made_for_kids)
    
    # Age restriction (advanced)
    if age_restricted:
        status["contentRating"] = {"ytRating": "ytAgeRestricted"}
    
    # Paid promotion
    if paid_promotion:
        status["paidProductPlacementDetails"] = {"hasPaidProductPlacement": True}
    
    # Comments settings
    comments_lower = (comments or "on").lower()
    if comments_lower == "off":
        status["commentModerationStatus"] = "commentsDisabled"
    elif comments_lower == "moderated":
        status["commentModerationStatus"] = "heldForReview"
    else:
        status["commentModerationStatus"] = "allowAllComments"
    
    # Allow embedding
    status["embeddable"] = bool(allow_embedding)
    
    # Shorts remixing
    if shorts_remixing == "allow_video_audio":
        status["shortsRemixStatus"] = "allowVideoAndAudioRemixing"
    elif shorts_remixing == "allow_audio_only":
        status["shortsRemixStatus"] = "allowAudioRemixing"
    else:
        status["shortsRemixStatus"] = "disallowed"

    snippet: dict[str, object] = {
        "title": str(title or "")[:95],
        "description": str(description or "")[:5000],
    }
    
    # Category mapping
    category_map = {
        "film_animation": "1",
        "autos_vehicles": "2",
        "music": "10",
        "pets_animals": "15",
        "sports": "17",
        "short_movies": "18",
        "travel_events": "19",
        "gaming": "20",
        "videoblogging": "21",
        "people_blogs": "22",
        "comedy": "23",
        "entertainment": "24",
        "news_politics": "25",
        "howto_style": "26",
        "education": "27",
        "science_tech": "28",
        "nonprofits_activism": "29",
    }
    cat_id = category_map.get((category or "").lower(), "22")
    snippet["categoryId"] = cat_id
    
    # Tags (max 500 characters total, max 500 tags)
    if tags:
        tag_list = [t.strip() for t in tags.split(",") if t.strip()][:500]
        snippet["tags"] = tag_list
    
    # Language
    if language:
        snippet["defaultLanguage"] = language
        snippet["defaultAudioLanguage"] = language
    
    # Recording date
    if recording_date:
        snippet["recordingDate"] = recording_date
    
    # Video location
    if video_location:
        snippet["locationDescription"] = video_location
    
    # Licence
    if licence.lower() == "creative commons":
        status["license"] = "creativeCommon"
    else:
        status["license"] = "youtube"
    
    # Altered content disclosure
    if altered_content:
        snippet["mediaRecordingDetails"] = {"isContentAltered": True}

    body = {
        "snippet": snippet,
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
