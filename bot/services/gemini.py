import os
from typing import Any
import asyncio
import logging

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
BASE_URL = "https://openrouter.ai/api/v1"
# Optional: Add your site URL and name for OpenRouter rankings
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Telegram YouTube Bot")

# List of free models to try in order (fallback system)
# These are verified working free models on OpenRouter
FREE_MODELS = [
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "qwen/qwen3-235b-a22b-thinking-2507",
    "mistralai/mistral-7b-instruct:free",
    "huggingfaceh4/zephyr-7b-beta:free",
    "gryphe/mythomax-l2-13b:free",
]


class GeminiError(Exception):
    pass


class GeminiTimeoutError(GeminiError):
    pass


async def _try_model(client: AsyncOpenAI, model: str, messages: list, extra_headers: dict) -> str:
    """Try a single model and return the response content."""
    logger.info(f"Trying model: {model}")
    response = await client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=0.7,
        max_tokens=2048,
        extra_headers=extra_headers,
    )
    
    if not response.choices:
        logger.warning(f"No response from model: {model}")
        raise GeminiError(f"No response from model {model}")
    
    message = response.choices[0].message
    content = message.content
    if not content:
        logger.warning(f"Empty response from model: {model}")
        raise GeminiError(f"Empty response from model {model}")
    
    logger.info(f"Successfully used model: {model}")
    return content.strip()


async def generate_audit(
    channel_data: dict[str, Any],
    user_goal: str = "",
    user_problem: str = "",
    lang: str = "uz",
) -> str:
    """
    Generate YouTube channel audit using OpenRouter AI based on real channel data.
    Tries multiple free models in case of rate limits.
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
    
    messages = [
        {
            "role": "system",
            "content": "You are a YouTube growth expert. Provide detailed, actionable advice for growing YouTube channels. Be specific and use data provided."
        },
        {
            "role": "user",
            "content": prompt
        }
    ]
    
    # Try each model in sequence
    last_error = None
    for i, model in enumerate(FREE_MODELS):
        try:
            # Add small delay between retries (except first)
            if i > 0:
                await asyncio.sleep(1)
            
            return await _try_model(client, model, messages, extra_headers)
            
        except Exception as e:
            error_msg = str(e).lower()
            last_error = e
            logger.warning(f"Model {model} failed: {e}")
            
            # If it's a rate limit, try next model
            if "rate limit" in error_msg or "429" in error_msg:
                logger.info(f"Model {model} rate limited, trying next...")
                continue
            
            # For 404 errors, log and continue to next model
            if "404" in error_msg or "no endpoints found" in error_msg:
                logger.warning(f"Model {model} not found (404), trying next...")
                continue
            
            # For other errors, stop trying
            if "timeout" in error_msg:
                raise GeminiTimeoutError("OpenRouter request timed out") from e
            elif "401" in error_msg or "unauthorized" in error_msg:
                raise GeminiError(f"OpenRouter API key invalid: {e}")
            elif "400" in error_msg:
                raise GeminiError(f"Invalid request to OpenRouter API: {e}")
            raise GeminiError(f"OpenRouter API error: {e}")
    
    # All models exhausted
    raise GeminiError("Barcha bepul modellar band. Iltimos, 5 daqiqa kutib qayta urinib ko'ring.")


def _build_prompt(
    channel_data: dict[str, Any],
    user_goal: str,
    user_problem: str,
    lang: str,
) -> str:
    """Build the audit prompt based on language and channel data."""
    
    # Language-specific instructions - STRICT language enforcement
    if lang == "uz":
        lang_instructions = """FAQAT va FAQAT O'zbek tilida javob yozing. Boshqa tillar (rus, ingliz) aralashtirmang!
Tushunarli, sodda va professional uslubda yozing.
YouTube atamalarini o'zbek tilida: "obunachi" (subscriber), "video", "ko'rish" (view), "muallif" (creator).
Jadvallar o'rniga oddiy ro'yxatlar va tavsiyalar yozing."""
    elif lang == "ru":
        lang_instructions = """Отвечай ТОЛЬКО на русском языке. Не смешивай с другими языками!
Профессиональный, но понятный стиль. Простые списки вместо сложных таблиц."""
    else:  # en
        lang_instructions = """Write ONLY in English. Do not mix other languages!
Professional yet simple style. Use clear bullet points, avoid complex tables."""
    
    videos_text = "\n".join([
        f"- {v['title']} (published: {v['published_at'][:10]})"
        for v in channel_data.get("recent_videos", [])
    ])
    
    prompt = f"""You are a YouTube expert. Analyze this channel and give practical advice.

IMPORTANT RULES:
{lang_instructions}

- Write in ONE language only, do not mix languages
- Use simple bullet points and clear sections
- Avoid markdown tables - use plain lists instead
- Be specific with channel data provided
- Give actionable recommendations, not generic advice

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

Structure your response as follows:

1. **CHANNEL OVERVIEW** - Brief summary of current state
2. **STRENGTHS** - List 3-4 things working well  
3. **CRITICAL ISSUES** - List 3-5 problems holding growth
4. **CONTENT STRATEGY** - Video ideas for next 30 days
5. **SEO OPTIMIZATION** - Title, description, tag tips with examples
6. **THUMBNAIL STRATEGY** - Design tips and 3 example concepts
7. **UPLOAD SCHEDULE** - Best frequency and timing
8. **SHORTS vs LONG-FORM** - Strategy for both formats
9. **IMMEDIATE ACTIONS** - 5 things to do THIS WEEK
10. **30-DAY GROWTH PLAN** - Week-by-week roadmap

Use simple formatting. Write clearly."""
    return prompt
