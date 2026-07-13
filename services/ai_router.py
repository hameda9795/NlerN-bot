"""AI chat routing: a Persian<->Dutch translation assistant.

Every message is sent straight to the chat model with a strict system
prompt: translate, never answer the content of a question. A per-user daily
cost cap (accounted via AIUsage) still guards against runaway spend.
"""

from __future__ import annotations

import html
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import select

from bot.config import get_settings
from database.connection import get_db_session
from database.models import AIUsage
from services.openai_client import estimate_chat_cost, get_chat_client

logger = logging.getLogger(__name__)

_settings = get_settings()

SYSTEM_PROMPT = (
    "تو یک دستیار ترجمه و آموزش زبان هلندی برای فارسی‌زبان‌ها هستی.\n\n"
    "هدف اصلی:\n"
    "کاربر فارسی یا هلندی می‌نویسد. تو باید فقط کمک کنی معنی و ترجمه را بفهمد، "
    "نه اینکه به سؤال‌های محتوایی جواب بدهی.\n\n"
    "سبک هلندی موردنظر:\n"
    "هلندی باید کوتاه، ساده، طبیعی و قابل فهم باشد؛ شبیه صحبت روزمره مردم، نه "
    "خیلی کتابی و رسمی.\n"
    "جمله‌ها باید مناسب سطح A2/B1 باشند.\n"
    "از جمله‌های خیلی طولانی استفاده نکن.\n"
    "در صورت امکان جمله را کوتاه کن.\n"
    "سبک باید این‌طوری باشد:\n"
    "* کوتاه\n"
    "* طبیعی\n"
    "* قابل استفاده در زندگی واقعی\n"
    "* نه خیلی خیابانی\n"
    "* نه خیلی رسمی\n"
    "* قابل فهم برای nativeها\n\n"
    "قانون خیلی مهم:\n"
    "اگر ورودی کاربر یک سؤال باشد، تو نباید به سؤال جواب بدهی. فقط باید آن را "
    "ترجمه کنی.\n\n"
    "مثال:\n"
    "ورودی: چرا هلندی خوب است؟\n"
    "خروجی درست: Waarom is Nederlands goed?\n"
    "خروجی غلط: چون یادگیری هلندی برای زندگی در هلند مهم است.\n\n"
    "وظایف تو:\n\n"
    "1. اگر کاربر جمله فارسی داد:\n"
    "ابتدا معنی جمله را برای خودت ساده کن، بعد آن را به هلندی کوتاه و طبیعی "
    "ترجمه کن.\n"
    "ساده‌سازی فارسی را فقط برای فهم بهتر انجام بده؛ لازم نیست همیشه نشان بدهی.\n"
    "خروجی:\n"
    "هلندی کوتاه:\n"
    "...\n\n"
    "مثال:\n"
    "ورودی: آره، خیلی فرق داره. هلندیِ کتابی معمولاً مرتب، کامل و آهسته است.\n"
    "خروجی:\n"
    "هلندی کوتاه:\n"
    "Ja, echt veel verschil. In boeken is 't Nederlands meestal netjes, "
    "compleet en rustig.\n\n"
    "2. اگر جمله فارسی خیلی رسمی، طولانی یا سخت بود:\n"
    "آن را به یک هلندی راحت‌تر و طبیعی‌تر تبدیل کن، نه ترجمه کلمه‌به‌کلمه.\n\n"
    "مثال:\n"
    "ورودی: من می‌خواهم بدانم که آیا امکان دارد امروز کمی دیرتر بیایم؟\n"
    "خروجی:\n"
    "هلندی کوتاه:\n"
    "Kan ik vandaag iets later komen?\n\n"
    "3. اگر کاربر یک کلمه فارسی داد:\n"
    "کلمه را به هلندی ترجمه کن.\n"
    "اگر چند ترجمه ممکن دارد، همه معنی‌های مهم را کوتاه توضیح بده.\n"
    "برای هر معنی، ۲ مثال ساده هلندی با ترجمه فارسی بده.\n\n"
    "فرمت:\n"
    "کلمه هلندی:\n"
    "...\n\n"
    "معنی:\n"
    "...\n\n"
    "مثال‌ها:\n\n"
    "1. ...\n"
    "   معنی فارسی: ...\n\n"
    "2. ...\n"
    "   معنی فارسی: ...\n\n"
    "مثال:\n"
    "ورودی: یادآوری\n"
    "خروجی:\n"
    "کلمه هلندی:\n"
    "herinnering\n\n"
    "معنی:\n"
    "یادآوری / چیزی که باعث می‌شود چیزی را فراموش نکنی.\n\n"
    "مثال‌ها:\n\n"
    "1. Ik heb een herinnering op mijn telefoon.\n"
    "   معنی فارسی: من یک یادآوری روی گوشی‌ام دارم.\n\n"
    "2. Bedankt voor de herinnering.\n"
    "   معنی فارسی: ممنون بابت یادآوری.\n\n"
    "3. اگر کاربر یک کلمه هلندی داد:\n"
    "آن را به فارسی ترجمه کن.\n"
    "اگر چند معنی دارد، معنی‌ها را جدا کن.\n"
    "برای هر معنی ۲ مثال ساده هلندی با ترجمه فارسی بده.\n\n"
    "فرمت:\n"
    "معنی فارسی:\n"
    "...\n\n"
    "مثال‌ها:\n\n"
    "1. ...\n"
    "   معنی فارسی: ...\n\n"
    "2. ...\n"
    "   معنی فارسی: ...\n\n"
    "مثال:\n"
    "ورودی: afspraak\n"
    "خروجی:\n"
    "معنی فارسی:\n\n"
    "1. قرار ملاقات\n"
    "2. توافق / قرار\n\n"
    "مثال‌ها:\n\n"
    "1. Ik heb morgen een afspraak bij de huisarts.\n"
    "   معنی فارسی: من فردا پیش دکتر وقت دارم.\n\n"
    "2. We hebben een afspraak gemaakt.\n"
    "   معنی فارسی: ما با هم قرار / توافق کردیم.\n\n"
    "3. اگر یک کلمه چند معنی دارد:\n"
    "باید بگویی این کلمه چند معنی مهم دارد.\n"
    "برای هر معنی مثال جدا بزن.\n\n"
    "مثال:\n"
    "ورودی: bank\n"
    "خروجی:\n"
    "این کلمه چند معنی دارد:\n\n"
    "1. bank = بانک\n"
    "   Voorbeeld:\n"
    "   Ik ga naar de bank.\n"
    "   معنی فارسی: من به بانک می‌روم.\n\n"
    "2. bank = مبل\n"
    "   Voorbeeld:\n"
    "   Ik zit op de bank.\n"
    "   معنی فارسی: من روی مبل نشسته‌ام.\n\n"
    "3. اگر کاربر جمله هلندی داد:\n"
    "آن را به فارسی ساده ترجمه کن.\n"
    "اگر جمله خیلی native یا شکسته بود، معنی طبیعی آن را توضیح بده.\n"
    "خروجی کوتاه باشد.\n\n"
    "مثال:\n"
    "ورودی: Komt goed.\n"
    "خروجی:\n"
    "معنی فارسی:\n"
    "درست میشه / اوکی میشه.\n\n"
    "توضیح کوتاه:\n"
    "این جمله در هلندی روزمره خیلی استفاده می‌شود، یعنی نگران نباش، حل می‌شود.\n\n"
    "7. اگر کاربر فقط بخواهد ترجمه:\n"
    "فقط ترجمه بده و توضیح اضافه نده.\n\n"
    "8. اگر معلوم نبود ورودی کلمه است یا جمله:\n"
    "بهترین حدس را بزن.\n"
    "اگر یک یا دو کلمه بود، مثل کلمه رفتار کن.\n"
    "اگر فعل یا جمله داشت، مثل جمله ترجمه کن.\n\n"
    "9. برای هلندی کوتاه و طبیعی از این مدل‌ها استفاده کن:\n"
    "* Ik weet het niet. → Weet ik niet.\n"
    "* Ik snap het niet. → Snap ik niet.\n"
    "* Ik kom eraan. → Kom eraan.\n"
    "* Dat lukt vandaag niet. → Vandaag lukt niet.\n"
    "* Ik laat het je weten. → Ik laat het weten.\n"
    "* Dat is goed. → Is goed.\n"
    "* Geen probleem.\n"
    "* Komt goed.\n"
    "* Even kijken.\n"
    "* Geen idee.\n"
    "* Maakt niet uit.\n\n"
    "10. از این کارها پرهیز کن:\n"
    "* جواب دادن به سؤال‌های کاربر\n"
    "* توضیح طولانی\n"
    "* ترجمه خیلی کتابی\n"
    "* جمله‌های پیچیده\n"
    "* کلمات خیلی رسمی مثل: desalniettemin, derhalve, betreffende\n"
    "* ترجمه کلمه‌به‌کلمه از فارسی\n"
    "* استفاده زیاد از slang خیابانی\n\n"
    "11. اگر جمله نیاز به ادب دارد:\n"
    "برای موقعیت رسمی از u استفاده کن.\n"
    "برای موقعیت عادی از je استفاده کن.\n"
    "اگر مشخص نبود، نسخه طبیعی و عمومی با je بده.\n\n"
    "12. فرمت خروجی مخصوص تلگرامه، نه Markdown معمولی:\n"
    "خروجی باید همیشه تمیز و کوتاه باشد.\n"
    "برای پررنگ‌کردن کلمه یا جمله‌ی هلندی فقط از **دو ستاره** دور آن استفاده کن؛ "
    "از #، ==، >، جدول یا هر نشانه‌ی دیگه استفاده نکن.\n"
    "هرگز خط جداکننده مثل --- یا === ننویس؛ به‌جاش فقط یک خط خالی بین بخش‌ها "
    "بذار.\n"
    "برای فهرست از شماره (1. 2. ...) یا • در ابتدای خط استفاده کن، نه فقط *.\n"
    "فقط وقتی لازم است بخش‌بندی کن.\n\n"
    "هدف نهایی:\n"
    "کاربر بتواند فارسی را به هلندی کوتاه، ساده و قابل فهم تبدیل کند؛ طوری که "
    "در واتساپ، مغازه، دکتر، شهرداری، کار و مکالمه روزمره قابل استفاده باشد."
)


@dataclass(slots=True)
class AIResponse:
    text: str
    tier: int
    cost_usd: float = 0.0
    model: str | None = None


# --- Telegram HTML formatting -------------------------------------------
# The bot sends messages with parse_mode=HTML, but the model sometimes emits
# plain-text Markdown regardless of the prompt's formatting rules. Convert the
# subset it actually uses (bold, bullet dashes, horizontal rules) to safe
# Telegram HTML instead of leaving literal "**"/"---" in the message.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)
_BULLET_RE = re.compile(r"^[ \t]*[*-][ \t]+", re.MULTILINE)
_HR_RE = re.compile(r"^[ \t]*[-=—_]{3,}[ \t]*$", re.MULTILINE)
_BLANK_RUN_RE = re.compile(r"\n{3,}")
# If the model emits raw <b>/<i> tags directly (instead of the **markdown**
# the prompt asks for), html.escape() below turns them into visible "&lt;b&gt;"
# text. Un-escape just these two well-formed, allowed pairs afterwards so a
# model that ignores the prompt's formatting rule still renders correctly.
_ESCAPED_TAG_RE = re.compile(r"&lt;(/?[bi])&gt;")


def _to_telegram_html(text: str) -> str:
    """Convert the model's lightweight Markdown into safe Telegram HTML."""
    escaped = html.escape(text, quote=False)
    escaped = _HR_RE.sub("", escaped)
    escaped = _BOLD_RE.sub(r"<b>\1</b>", escaped)
    escaped = _BULLET_RE.sub("• ", escaped)
    escaped = _ESCAPED_TAG_RE.sub(r"<\1>", escaped)
    escaped = _BLANK_RUN_RE.sub("\n\n", escaped)
    return escaped.strip()


# --- Cost tracking ----------------------------------------------------------
def _today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


async def get_today_cost(user_id: int) -> float:
    """Return the user's AI spend so far today (USD)."""
    async with get_db_session() as session:
        cost = await session.scalar(
            select(AIUsage.cost_usd).where(
                AIUsage.user_id == user_id, AIUsage.day == _today()
            )
        )
        return float(cost or 0.0)


async def _record_cost(user_id: int, cost: float) -> None:
    """Add cost (and one call) to today's usage row, creating it if needed."""
    day = _today()
    async with get_db_session() as session:
        row = await session.scalar(
            select(AIUsage).where(AIUsage.user_id == user_id, AIUsage.day == day)
        )
        if row is None:
            row = AIUsage(user_id=user_id, day=day, cost_usd=0.0, calls=0)
            session.add(row)
        row.cost_usd = (row.cost_usd or 0.0) + cost
        row.calls = (row.calls or 0) + 1


# --- Model call ---------------------------------------------------------
async def _chat_completion(
    *, model: str, message: str, history: list[dict[str, str]]
) -> tuple[str, float]:
    """Call the chat provider's chat completion. Returns (text, estimated_cost)."""
    client = get_chat_client()
    if client is None:
        raise RuntimeError("Chat AI client not configured")

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history[-10:])
    messages.append({"role": "user", "content": message})

    resp = await client.chat.completions.create(
        model=model,
        messages=messages,
        max_tokens=_settings.ai.openai_max_tokens,
        temperature=0.5,
    )
    text = _to_telegram_html(resp.choices[0].message.content or "")
    cost = 0.0
    if resp.usage is not None:
        cost = estimate_chat_cost(
            model, resp.usage.prompt_tokens, resp.usage.completion_tokens
        )
    return text, cost


# --- Public entry point -----------------------------------------------------
async def route_and_respond(
    *, user_id: int, message: str, history: list[dict[str, str]] | None = None
) -> AIResponse:
    """Enforce the daily spend limit, then translate via the chat model."""
    history = history or []

    limit = _settings.ai.cost_limit_per_user_per_day
    if await get_today_cost(user_id) >= limit:
        return AIResponse(
            text=(
                "📉 سقف استفاده‌ی روزانه‌ات از هوش مصنوعی پر شده. "
                "فردا دوباره امتحان کن، یا فعلاً از درس‌ها و مرور واژگان استفاده کن. 🙂"
            ),
            tier=0,
        )

    model = _settings.ai.chat_provider_model

    try:
        text, cost = await _chat_completion(
            model=model, message=message, history=history
        )
        await _record_cost(user_id, cost)
        return AIResponse(text=text or "…", tier=1, cost_usd=cost, model=model)
    except Exception as exc:  # noqa: BLE001 - graceful degradation
        logger.error("AI call failed (model=%s): %s", model, exc)
        return AIResponse(
            text=(
                "🤖 الان نمی‌تونم به سرویس ترجمه وصل بشم. یه کم دیگه دوباره امتحان کن."
            ),
            tier=0,
        )
