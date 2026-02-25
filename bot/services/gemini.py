import os
from typing import Any

from openai import AsyncOpenAI

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "mistralai/mistral-small-3.1-24b-instruct:free")
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
    """
    Generate YouTube channel audit using OpenRouter AI based on real channel data.
    Uses Step 3.5 Flash model.
    """
    if not OPENROUTER_API_KEY:
        raise GeminiError("OPENROUTER_API_KEY not configured")
    
    prompt = _build_prompt(channel_data, user_goal, user_problem, lang)
    
    # Initialize OpenAI client with OpenRouter base URL
    client = AsyncOpenAI(
        base_url=BASE_URL,
        api_key=OPENROUTER_API_KEY,
        timeout=60.0,
    )
    
    # Optional headers for OpenRouter rankings
    extra_headers = {}
    if OPENROUTER_SITE_URL:
        extra_headers["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_SITE_NAME:
        extra_headers["X-Title"] = OPENROUTER_SITE_NAME
    
    try:
        response = await client.chat.completions.create(
            model=OPENROUTER_MODEL,
            messages=[
                {
                    "role": "system",
                    "content": "You are a YouTube growth expert. Provide detailed, actionable advice for growing YouTube channels. Be specific and use data provided."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            temperature=0.7,
            max_tokens=2048,
            extra_headers=extra_headers,
        )
        
        # Extract the generated text
        if not response.choices:
            raise GeminiError("No response from OpenRouter")
        
        message = response.choices[0].message
        content = message.content
        if not content:
            raise GeminiError("Empty response from OpenRouter")
        
        return content.strip()
        
    except Exception as e:
        error_msg = str(e).lower()
        if "rate limit" in error_msg or "429" in error_msg:
            raise GeminiError("OpenRouter API rate limit exceeded. Please try again in a few minutes.")
        elif "timeout" in error_msg:
            raise GeminiTimeoutError("OpenRouter request timed out") from e
        elif "401" in error_msg or "unauthorized" in error_msg:
            raise GeminiError(f"OpenRouter API key invalid: {e}")
        elif "400" in error_msg:
            raise GeminiError(f"Invalid request to OpenRouter API: {e}")
        raise GeminiError(f"OpenRouter API error: {e}")


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
