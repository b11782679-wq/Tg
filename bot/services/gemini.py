import os
from typing import Any

import httpx

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.0-flash-exp:free")
BASE_URL = "https://openrouter.ai/api/v1"
# Optional: Add your site URL and name for OpenRouter rankings
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Telegram YouTube Bot")


class GeminiError(Exception):
    pass


class GeminiTimeoutError(GeminiError):
    pass


async def generate_audit(
    channel_data: dict[str, Any],
    user_goal: str = "",
    user_problem: str = "",
    lang: str = "uz",
) -> str:
    """Generate YouTube channel audit using OpenRouter AI based on real channel data."""
    if not OPENROUTER_API_KEY:
        raise GeminiError("OPENROUTER_API_KEY not configured")
    
    prompt = _build_prompt(channel_data, user_goal, user_problem, lang)
    
    url = f"{BASE_URL}/chat/completions"
    
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
    }
    
    # Optional headers for OpenRouter rankings
    if OPENROUTER_SITE_URL:
        headers["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_SITE_NAME:
        headers["X-Title"] = OPENROUTER_SITE_NAME
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": [
            {
                "role": "system",
                "content": "You are a YouTube growth expert. Provide detailed, actionable advice for growing YouTube channels. Be specific and use data provided."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.7,
        "max_tokens": 2048,
    }
    
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                url,
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            
            # Check for API errors in response
            if "error" in data:
                error_msg = data["error"].get("message", "Unknown OpenRouter API error")
                raise GeminiError(error_msg)
            
            # Extract the generated text (OpenAI format)
            choices = data.get("choices", [])
            if not choices:
                raise GeminiError("No response from OpenRouter")
            
            message = choices[0].get("message", {})
            content = message.get("content", "")
            if not content:
                raise GeminiError("Empty response from OpenRouter")
            
            return content.strip()
            
    except httpx.TimeoutException as e:
        raise GeminiTimeoutError("OpenRouter request timed out") from e
    except httpx.HTTPStatusError as e:
        error_body = ""
        try:
            error_body = e.response.text[:500]
        except Exception:
            pass
        if e.response.status_code == 429:
            raise GeminiError("OpenRouter API rate limit exceeded. Please try again later.")
        elif e.response.status_code == 401:
            raise GeminiError(f"OpenRouter API key invalid: {error_body}")
        elif e.response.status_code == 400:
            raise GeminiError(f"Invalid request to OpenRouter API: {error_body}")
        raise GeminiError(f"OpenRouter API error {e.response.status_code}: {error_body}")


def _build_prompt(
    channel_data: dict[str, Any],
    user_goal: str,
    user_problem: str,
    lang: str,
) -> str:
    """Build the audit prompt based on language and channel data."""
    
    # Language-specific instructions
    if lang == "uz":
        lang_instructions = """Javobni O'zbek tilida yozing. Professional, ammo tushunarli bo'lsin."""
    elif lang == "ru":
        lang_instructions = """Ответ должен быть на русском языке. Профессиональный, но понятный стиль."""
    else:  # en
        lang_instructions = """Write the response in English. Professional yet approachable style."""
    
    videos_text = "\n".join([
        f"- {v['title']} (published: {v['published_at'][:10]})"
        for v in channel_data.get("recent_videos", [])
    ])
    
    prompt = f"""You are a YouTube growth expert. Analyze this YouTube channel and provide actionable recommendations.

{lang_instructions}

CHANNEL DATA:
- Name: {channel_data.get('title', 'N/A')}
- Subscribers: {channel_data.get('subscriber_count', 0):,}
- Total Videos: {channel_data.get('video_count', 0):,}
- Total Views: {channel_data.get('view_count', 0):,}
- Country: {channel_data.get('country', 'N/A')}
- Channel Created: {channel_data.get('created_at', 'N/A')[:10]}

Description: {channel_data.get('description', 'N/A')[:500]}

RECENT 10 VIDEOS:
{videos_text}

USER INPUT:
- Goal: {user_goal or 'Not specified'}
- Problems: {user_problem or 'Not specified'}

Please provide a comprehensive audit with these sections:

1. **CHANNEL OVERVIEW** - Brief summary of current state
2. **STRENGTHS** - What's working well
3. **CRITICAL ISSUES** - 3-5 biggest problems holding growth
4. **CONTENT STRATEGY** - Video ideas and content plan for next 30 days
5. **SEO OPTIMIZATION** - Title, description, tag recommendations with examples
6. **THUMBNAIL STRATEGY** - Design principles and 3 example concepts
7. **UPLOAD SCHEDULE** - Optimal frequency and timing
8. **SHORTS vs LONG-FORM** - Strategy for both formats
9. **IMMEDIATE ACTIONS** - 5 things to do THIS WEEK
10. **30-DAY GROWTH PLAN** - Week-by-week roadmap

Be specific, use data from the channel, and give practical examples. Don't be generic."""
    return prompt
