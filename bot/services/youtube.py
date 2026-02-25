import os
from typing import Any

import httpx

YOUTUBE_API_KEY = os.getenv("YOUTUBE_DATA_API_KEY", "")
BASE_URL = "https://www.googleapis.com/youtube/v3"


class YouTubeError(Exception):
    pass


class ChannelNotFoundError(YouTubeError):
    pass


class QuotaExceededError(YouTubeError):
    pass


async def fetch_channel_data(channel_url: str) -> dict[str, Any]:
    """
    Fetch channel details and recent videos from YouTube Data API.
    channel_url can be: @handle, channel/ID, or youtube.com/c/name, etc.
    Returns dict with channel info and videos list.
    """
    if not YOUTUBE_API_KEY:
        raise YouTubeError("YOUTUBE_DATA_API_KEY not configured")

    # Extract channel handle or ID from various URL formats
    channel_id, handle = _extract_identifier(channel_url)

    async with httpx.AsyncClient(timeout=30.0) as client:
        # If we have a handle, we need to find the channel ID first
        if handle and not channel_id:
            search_resp = await client.get(
                f"{BASE_URL}/search",
                params={
                    "part": "snippet",
                    "q": handle,
                    "type": "channel",
                    "maxResults": 1,
                    "key": YOUTUBE_API_KEY,
                },
            )
            _check_error(search_resp)
            search_data = search_resp.json()
            items = search_data.get("items", [])
            if not items:
                raise ChannelNotFoundError(f"Channel not found for: {channel_url}")
            channel_id = items[0]["snippet"]["channelId"]

        # Now fetch channel details
        channel_resp = await client.get(
            f"{BASE_URL}/channels",
            params={
                "part": "snippet,statistics,brandingSettings",
                "id": channel_id,
                "key": YOUTUBE_API_KEY,
            },
        )
        _check_error(channel_resp)
        channel_data = channel_resp.json()
        items = channel_data.get("items", [])
        if not items:
            raise ChannelNotFoundError(f"Channel not found: {channel_id}")

        channel_info = items[0]
        snippet = channel_info.get("snippet", {})
        stats = channel_info.get("statistics", {})
        branding = channel_info.get("brandingSettings", {})
        channel = branding.get("channel", {})

        # Fetch recent videos (last 10)
        videos_resp = await client.get(
            f"{BASE_URL}/search",
            params={
                "part": "snippet",
                "channelId": channel_id,
                "order": "date",
                "type": "video",
                "maxResults": 10,
                "key": YOUTUBE_API_KEY,
            },
        )
        _check_error(videos_resp)
        videos_data = videos_resp.json()
        videos = []
        for item in videos_data.get("items", []):
            video_snippet = item.get("snippet", {})
            videos.append({
                "title": video_snippet.get("title", ""),
                "published_at": video_snippet.get("publishedAt", ""),
                "description": video_snippet.get("description", "")[:200],
            })

        return {
            "channel_id": channel_id,
            "title": snippet.get("title", ""),
            "description": snippet.get("description", ""),
            "custom_url": channel.get("customUrl", ""),
            "subscriber_count": int(stats.get("subscriberCount", 0) or 0),
            "video_count": int(stats.get("videoCount", 0) or 0),
            "view_count": int(stats.get("viewCount", 0) or 0),
            "country": snippet.get("country", "N/A"),
            "created_at": snippet.get("publishedAt", ""),
            "recent_videos": videos,
        }


def _extract_identifier(url: str) -> tuple[str | None, str | None]:
    """Extract channel ID or handle from various YouTube URL formats."""
    url = url.strip()
    
    # Direct channel ID
    if url.startswith("UC") and len(url) == 24:
        return url, None
    
    # Handle @username format in URL
    if "@" in url:
        parts = url.split("@")
        if len(parts) > 1:
            handle = parts[1].split("/")[0].split("?")[0]
            return None, f"@{handle}"
    
    # channel/ID format
    if "channel/" in url:
        parts = url.split("channel/")
        if len(parts) > 1:
            channel_id = parts[1].split("/")[0].split("?")[0]
            return channel_id, None
    
    # c/ or user/ format - treat as handle
    for prefix in ["c/", "user/"]:
        if prefix in url:
            parts = url.split(prefix)
            if len(parts) > 1:
                name = parts[1].split("/")[0].split("?")[0]
                return None, name
    
    # Plain text handle @username
    if url.startswith("@"):
        return None, url
    
    # Plain text - treat as handle/search term
    return None, url


def _check_error(response: httpx.Response) -> None:
    """Check for API errors and raise appropriate exceptions."""
    if response.status_code == 403:
        data = response.json()
        error = data.get("error", {})
        if "quota" in str(error).lower():
            raise QuotaExceededError("YouTube API quota exceeded")
        raise YouTubeError(f"YouTube API access denied: {error}")
    
    if response.status_code == 404:
        raise ChannelNotFoundError("Channel not found")
    
    response.raise_for_status()
    
    data = response.json()
    if "error" in data:
        error_msg = data["error"].get("message", "Unknown YouTube API error")
        raise YouTubeError(error_msg)
