import os
from typing import Any
import asyncio
import logging

from openai import AsyncOpenAI

# Import ollama if available
try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

logger = logging.getLogger(__name__)

# AI Provider configuration
AI_PROVIDER = os.getenv("AI_PROVIDER", "openrouter").lower()  # "openrouter" or "ollama"

# OpenRouter API configuration
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
OPENROUTER_SITE_URL = os.getenv("OPENROUTER_SITE_URL", "")
OPENROUTER_SITE_NAME = os.getenv("OPENROUTER_SITE_NAME", "Telegram YouTube Bot")

# Ollama API configuration
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen3.5:27b")
OLLAMA_API_KEY = os.getenv("OLLAMA_API_KEY", "")

# List of free models to try in order (fallback system) for OpenRouter
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
    Generate YouTube channel audit using AI based on real channel data.
    Supports both OpenRouter and Ollama providers.
    """
    prompt = _build_prompt(channel_data, user_goal, user_problem, lang)
    
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
    
    # Use Ollama if configured
    if AI_PROVIDER == "ollama" and OLLAMA_AVAILABLE:
        return await _generate_with_ollama(messages)
    
    # Otherwise use OpenRouter
    return await _generate_with_openrouter(messages)


async def _generate_with_ollama(messages: list[dict[str, str]]) -> str:
    """Generate audit using Ollama API (local or cloud)."""
    try:
        # Set OLLAMA_HOST environment variable if provided
        os.environ["OLLAMA_HOST"] = OLLAMA_HOST
        
        # Cloud API uses headers for authentication
        if OLLAMA_API_KEY:
            logger.info("Using Ollama cloud API with authentication")
            import httpx
            
            # Ollama cloud base is https://ollama.com (API served under /api)
            # Allow OLLAMA_HOST to be either:
            # - https://ollama.com
            # - https://ollama.com/api
            base = (OLLAMA_HOST or "https://ollama.com").rstrip("/")
            if base.endswith("/api"):
                url = f"{base}/chat"
            else:
                url = f"{base}/api/chat"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {OLLAMA_API_KEY}"
            }
            data = {
                "model": OLLAMA_MODEL,
                "messages": messages,
                "stream": False
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                try:
                    response = await client.post(url, json=data, headers=headers)
                    response.raise_for_status()
                except httpx.HTTPStatusError as e:
                    # Include server response to make debugging (401/404) possible
                    body = ""
                    try:
                        body = e.response.text
                    except Exception:
                        body = ""
                    raise GeminiError(
                        f"Ollama cloud HTTP {e.response.status_code} for url '{url}': {body}"
                    ) from e
                result = response.json()
                
                content = result.get('message', {}).get('content', '')
                if not content:
                    raise GeminiError("Ollama returned empty content")
                logger.info(f"Successfully used Ollama cloud model: {OLLAMA_MODEL}")
                return content.strip()
        else:
            # Local Ollama server - use default client
            logger.info("Using local Ollama server")
            response = ollama.chat(
                model=OLLAMA_MODEL,
                messages=messages,
            )
            
            if not response or not response.message:
                raise GeminiError("Ollama returned empty response")
            
            content = response.message.content
            if not content:
                raise GeminiError("Ollama returned empty content")
            
            logger.info(f"Successfully used Ollama local model: {OLLAMA_MODEL}")
            return content.strip()
            
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise GeminiError(f"Ollama API error: {e}")


async def _generate_with_openrouter(messages: list[dict[str, str]]) -> str:
    """Generate audit using OpenRouter API with fallback models."""
    if not OPENROUTER_API_KEY:
        raise GeminiError("OPENROUTER_API_KEY not configured")
    
    # Initialize OpenAI client with OpenRouter base URL
    client = AsyncOpenAI(
        base_url=OPENROUTER_BASE_URL,
        api_key=OPENROUTER_API_KEY,
        timeout=60.0,
    )
    
    # Optional headers for OpenRouter rankings
    extra_headers = {}
    if OPENROUTER_SITE_URL:
        extra_headers["HTTP-Referer"] = OPENROUTER_SITE_URL
    if OPENROUTER_SITE_NAME:
        extra_headers["X-Title"] = OPENROUTER_SITE_NAME
    
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
    
    # Language-specific instructions with EXACT style example
    if lang == "uz":
        lang_instructions = """FAQAT va FAQAT O'zbek tilida javob yozing. Boshqa tillar (rus, ingliz) aralashtirmang!

TAVSIYA ETILGAN STIL (MISOL):

🔥 1. ENG KATTA MUAMMO – [KONKRET SON] [MUAMMO NOMI]

Bu yerda muammo:
- [1-muammo]
- [2-muammo]
- [3-muammo]

⚠️ YouTube 2026 algoritmi [N] narsaga qaraydi:
1. [Ko'rsatkich 1]
2. [Ko'rsatkich 2]
3. [Ko'rsatkich 3]

Senda hali bu ko'rsatkichlar shakllanmagan.

🚀 2. KANALNI "[HOLAT]"DAN "[MAQSAD]"GA O'TKAZISH

Hozir kanal [umumiy/tor/tartibsiz].

❌ Bu [sabab].
✔️ Sen [harakat] qilishing kerak.

Masalan:
- [Misol 1]
- [Misol 2]
- [Misol 3]

👉 Tavsiya: "[Konkret tavsiya]"

🎯 3. [BO'LIM NOMI]

Professional formulasi:
[Aniq formula]

Masalan:
❌ "[Yomon misol]"
✔️ "[Yaxshi misol]"

Qoidalari:
1. [Qoida 1]
2. [Qoida 2]
3. [Qoida 3]

🎯 Maqsad: [Konkret raqamli maqsad]

📊 FORMATLASH QOIDALARI:
- Sarlavhalar: 🔥, 🚀, 🎯, 📈, 💰, 🧠, ⚠️, ✅, ❌ emoji bilan boshlanadi
- Muhim sonlar va faktlar: **Qalin** qiling
- ❌ va ✔️ belgilari xato/to'g'ri narsalarni ko'rsatadi
- Ro'yxatlar: Raqamli (1, 2, 3) yoki bullet (-) bilan
- Har bir bo'limda konkret raqamli maqsadlar ko'rsatiladi (CTR 8%+, 1000 subscriber, etc.)
- Til: Professional, lekin tushunarli. "O'zingizga xos", "odamlar", "siz" kabi murojaatlar.
- Eng oxirida: REALISTIK NATIJA bo'lishi shart (30 kun, 90 kun)

YouTube atamalarini o'zbek tilida:
- Subscribers = Obunachilar
- Views = Ko'rishlar
- CTR = Bosish foizi
- Retention = Videoni ko'rish davomiyligi
- Watch Time = Umumiy ko'rish vaqti
- Thumbnail = Video rasmi
- SEO = Qidiruv optimizatsiyasi"""
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

YOU MUST FOLLOW THIS EXACT STRUCTURE WITH EMOJI HEADERS:

🔥 1. ENG KATTA MUAMMO – [KONKRET SON] [MUAMMO NOMI]
Bu yerda muammo:
- [1-muammo]
- [2-muammo]
- [3-muammo]

⚠️ YouTube 2026 algoritmi 3 narsaga qaraydi:
1. CTR (bosish foizi)
2. Watch Time (qancha minut ko'rildi)
3. Retention % (necha % gacha yetdi)

Senda hali bu ko'rsatkichlar shakllanmagan.

🚀 2. KANALNI "BEGINNER"DAN "GROWTH MODE"GA O'TKAZISH
2.1 Kanal Pozitsiyalash (Niche Positioning)

Hozir kanal [umumiy/tor/tartibsiz].

❌ Bu [sabab].
✔️ Sen torlashtirishing kerak.

Masalan:
- [Misol 1]
- [Misol 2]
- [Misol 3]

👉 Tavsiya: "[Konkret tavsiya]"

🎯 3. THUMBNAILNI PRO DARAJAGA OLIB CHIQISH

Professional Thumbnail formulasi:
1 ta obyekt + 2-3 so'z + kuchli kontrast

Masalan:
❌ "[Yomon misol]"
✔️ "[Yaxshi misol]"

Thumbnail qoidalari:
1. 3 ta rangdan ko'p ishlatma
2. Orqa fon blur
3. Yuz ifodasi (agar bor bo'lsa)
4. 1 ta katta obyekt

🎯 Maqsad: CTR 8%+

🧠 4. VIDEO STRUKTURASI (Retention uchun)

0-5 sekund: Hook (eng hayajonli joyni boshida ko'rsat)
5-20 sekund: Tez intro (max 7 sekund)
O'rta qism: Har 30-40 sekundda yangi voqea/muammo/kulgili moment
Oxiri: Cliffhanger

📈 5. SEO NI PROFESSIONAL QILISH

Title formulasi: [Kuchli so'z] + [Asosiy keyword] + [Qiziqish]
Description: Birinchi 2 qatorda keyword bo'lishi shart

📊 6. SHORTS STRATEGIYASINI KUCHAYTIRISH

Strategiya: Har bir long video → 3 ta Shorts
Shorts hook: "[Misollar]"

💰 7. 30 KUNLIK AGRESSIV REJA (PRO VERSION)

1-hafta:
- 2 ta long video
- 5 ta Shorts
- Thumbnail A/B test

2-hafta:
- 2 ta challenge video
- 5 ta Shorts
- 1 kollab

3-hafta:
- [Reja]

4-hafta:
- [Reja]

🧲 8. LOYAL COMMUNITY YARATISH

"Craze Crew" g'oyasi:
- Har video boshida: "Craze Crew, bugun biz..."
- Comment pin qil

📉 9. ENG KATTA XATO – SABR QILMASLIK

Hozir [N] obunachi – bu normal.
Senga kerak: kamida 25–30 ta video.

🏆 10. AGAR MEN SENING O'RNINGDA BO'LSAM…

Men shunday qilardim:
1. [Harakat 1]
2. [Harakat 2]
3. [Harakat 3]
4. [Harakat 4]
5. [Harakat 5]

📊 REALISTIK NATIJA (Agar to'g'ri qilinsa)

30 kunda:
[N] → [N+progress] obunachi
1 video [N]k+ ko'rish chiqishi mumkin

90 kunda:
[N] subscriber real"""
    return prompt
