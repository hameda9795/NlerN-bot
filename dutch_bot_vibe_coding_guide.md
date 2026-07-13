# راهنمای کامل Vibe Coding: ربات تلگرام آموزش زبان هلندی (Dutch Learning Bot)

> **پروژه:** ربات تلگرام پیشرفته یادگیری زبان هلندی برای فارسی‌زبانان  
> **روش:** Vibe Coding (کدنویسی با AI)  
> **تاریخ:** ۲۰۲۵-۰۶-۰۹  
> **تعداد مراحل:** ۲۵ تسک کوچک و قابل اجرا  
> **تخمین زمان:** ۱۰-۱۲ هفته (۲-۳ ساعت در روز)

---

## 📋 فهرست مطالب

1. [مقدمه و اصول Vibe Coding](#1-مقدمه-و-اصول-vibe-coding)
2. [ساختار پروژه و فایل‌های Context](#2-ساختار-پروژه-و-فایلهای-context)
3. [فاز ۱: Foundation (تسک ۱-۷)](#3-فاز-۱-foundation)
4. [فاز ۲: Core Learning (تسک ۸-۱۳)](#4-فاز-۲-core-learning)
5. [فاز ۳: AI Features (تسک ۱۴-۱۹)](#5-فاز-۳-ai-features)
6. [فاز ۴: Engagement (تسک ۲۰-۲۳)](#6-فاز-۴-engagement)
7. [فاز ۵: Polish & Deploy (تسک ۲۴-۲۵)](#7-فاز-۵-polish--deploy)
8. [چک‌لیست‌های امنیتی](#8-چکلیستهای-امنیتی)
9. [نکات طلایی Vibe Coding](#9-نکات-طلایی-vibe-coding)

---

## ۱. مقدمه و اصول Vibe Coding

### Vibe Coding چیست؟

**Vibe Coding** به سبکی از توسعه نرم‌افزار گفته می‌شود که در آن به جای نوشتن مستقیم کد، نیازها را به زبان طبیعی به AI Coding Assistant (مثل Cursor، Claude Code، Windsurf) توصیف می‌کنید و AI بخش عمده کدنویسی را انجام می‌دهد.

### ابزارهای پیشنهادی

| ابزار | بهترین برای | قیمت |
|-------|-------------|------|
| **Cursor** | Iteration سریع روزمره | $20/month |
| **Claude Code** | Refactoring‌های معماری‌محور | $20/month |
| **Windsurf** | پروژه‌های بزرگ با Memory | $20/month |

> **توصیه:** برای این پروژه **Cursor** انتخاب ایده‌آلی است.

### چرخه کاری Vibe Coding

```
PLAN.md → AGENTS.md → Prompt → Implement → Test → Commit → Next Task
```

**قوانین طلایی:**
1. **هر Prompt فقط یک Step** — AI پیشنهاد می‌دهد چند فیچر همزمان بسازید، قبول نکنید
2. **بعد از هر Step موفق، Git Commit** بزنید
3. **هر خط کد AI-generated را بخوانید و بفهمید**
4. **Security-First** — AI به طور Natural به Security فکر نمی‌کند
5. **Session جدید** بعد از Refactoring بزرگ

---

## ۲. ساختار پروژه و فایل‌های Context

### فایل‌های Context (قبل از شروع بسازید)

#### `AGENTS.md` — در Root پروژه

```markdown
# AGENTS.md — Dutch Learning Bot

## General
- Python 3.11+, always use async/await
- Dependencies in pyproject.toml only
- Prefer existing libraries over custom code
- Use keyword arguments for function calls
- Type hints mandatory
- Docstrings for all public functions

## Architecture
- handlers/ — Telegram handlers only (no business logic)
- services/ — Business logic and AI integration
- database/ — Models, migrations, queries
- config/ — Settings with Pydantic
- utils/ — Shared helpers
- keyboards/ — Telegram UI keyboards

## Security
- Never hardcode secrets
- Validate all user inputs
- Use parameterized queries
- No sensitive data in logs
- Privacy Mode enabled

## Testing
- pytest for all new modules
- Test edge cases (empty input, invalid user)

## Language
- Bot interface: Persian (Farsi) + Dutch
- Code comments: English
- Docstrings: English
```

#### `PLAN.md` — نقشه راه

```markdown
# PLAN.md — Dutch Learning Bot

## Phase 1: Foundation (Week 1-2)
- Project setup, aiogram 3.x, database, user management

## Phase 2: Core Learning (Week 3-4)
- CEFR curriculum, FSRS, quizzes

## Phase 3: AI Features (Week 5-6)
- Tiered AI routing, cultural bridge, pronunciation

## Phase 4: Engagement (Week 7-8)
- Gamification, study groups, notifications

## Phase 5: Polish & Deploy (Week 9-10)
- Progress tracking, exam prep, deploy
```

#### `PATTERNS.md` — الگوهای کد

```markdown
# PATTERNS.md

## Handler Pattern
```python
from aiogram import Router, F
from aiogram.types import Message
from aiogram.filters import Command

router = Router(name="module_name")

@router.message(Command("command"))
async def command_handler(message: Message) -> None:
    # 1. Validate input
    # 2. Call service layer
    # 3. Send response
```

## Service Pattern
```python
async def business_logic(user_id: int, data: str) -> Result:
    # 1. Fetch from DB
    # 2. Process
    # 3. Save to DB
    # 4. Return result
```

## Error Handling
```python
try:
    result = await some_async_operation()
except SpecificException as e:
    logger.error(f"Context: {e}")
    await message.answer("پیام خطای فارسی")
```
```

### ساختار فولدرهای پروژه

```
dutch-learning-bot/
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── README.md
├── AGENTS.md
├── PLAN.md
├── PATTERNS.md
│
├── bot/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   └── loader.py
│
├── handlers/
│   ├── __init__.py
│   ├── common.py          # /start, /help
│   ├── curriculum.py      # درس‌ها و کوییز
│   ├── fsrs_review.py     # مرور کارت‌ها
│   ├── ai_chat.py         # چت با AI
│   ├── pronunciation.py   # تلفظ
│   ├── gamification.py    # امتیاز و streak
│   ├── study_groups.py    # گروه‌های مطالعه
│   ├── notifications.py   # نوتیفیکیشن
│   ├── progress.py        # پیشرفت
│   └── settings.py        # تنظیمات
│
├── services/
│   ├── __init__.py
│   ├── user_service.py
│   ├── curriculum_service.py
│   ├── fsrs_service.py
│   ├── ai_router.py       # Tiered AI routing
│   ├── pronunciation_service.py
│   ├── gamification_service.py
│   ├── notification_service.py
│   └── progress_service.py
│
├── database/
│   ├── __init__.py
│   ├── connection.py
│   ├── models.py
│   ├── migrations/
│   └── repositories/
│
├── keyboards/
│   ├── __init__.py
│   ├── main_menu.py
│   ├── review_keyboard.py
│   └── inline_keyboards.py
│
├── middlewares/
│   ├── __init__.py
│   ├── logging_middleware.py
│   ├── rate_limit.py
│   └── user_middleware.py
│
├── utils/
│   ├── __init__.py
│   ├── text.py
│   ├── validators.py
│   └── exceptions.py
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_handlers/
│   ├── test_services/
│   └── test_fsrs/
│
└── scripts/
    ├── seed_database.py
    └── backup_db.py
```

---

## ۳. فاز ۱: Foundation

### تسک ۱.۱: Setup پروژه Python

**پرامپت:**

```
You are a senior Python backend engineer. We are building a Dutch language learning Telegram bot for Persian speakers using vibe coding.

**Context:**
- Project name: dutch-learning-bot
- Python 3.11+
- Framework: aiogram 3.x (async)
- Database: SQLite with aiosqlite for MVP, migrate to PostgreSQL later
- AI Integration: OpenAI API with tiered routing
- Target users: Persian speakers learning Dutch (CEFR A1-B2)

**Task:**
Create the initial project structure with:
1. pyproject.toml with all dependencies:
   - aiogram>=3.20.0
   - pydantic>=2.0, pydantic-settings
   - sqlalchemy[asyncio]>=2.0
   - aiosqlite
   - py-fsrs>=6.0
   - openai>=1.0
   - httpx
   - apscheduler
   - pytest, pytest-asyncio
2. .env.example with all required environment variables
3. .gitignore for Python projects
4. README.md with project description and setup instructions
5. Create empty folder structure: bot/, handlers/, services/, database/, keyboards/, middlewares/, utils/, tests/, scripts/

**Constraints:**
- Use modern Python packaging (pyproject.toml, not requirements.txt)
- Include proper dependency version pinning
- .env.example should include: BOT_TOKEN, OPENAI_API_KEY, DATABASE_URL, ADMIN_USER_ID
- Do NOT write any application code yet — just project scaffolding

**Output:**
Return the complete content of each file.
```

---

### تسک ۱.۲: پیاده‌سازی config.py با Pydantic Settings

**پرامپت:**

```
You are a senior Python backend engineer specializing in async Telegram bots.

**Context:**
- Project: dutch-learning-bot
- Tech: aiogram 3.x, Python 3.11, Pydantic Settings
- File to create: bot/config.py

**Task:**
Implement a comprehensive configuration module using Pydantic Settings that:
1. Loads all settings from .env file
2. Includes these settings groups:
   - BotConfig: BOT_TOKEN, ADMIN_IDS (list of ints)
   - DatabaseConfig: DATABASE_URL, POOL_SIZE
   - AIConfig: OPENAI_API_KEY, OPENAI_MODEL_DEFAULT, OPENAI_MAX_TOKENS, AI_COST_LIMIT_PER_USER_PER_DAY
   - FSRSConfig: DESIRED_RETENTION (default 0.9), MAX_DAILY_REVIEWS
   - NotificationConfig: NOTIFICATION_ENABLED_HOURS_START, NOTIFICATION_ENABLED_HOURS_END
3. Uses Pydantic v2 syntax
4. Includes validation (e.g., BOT_TOKEN must start with a number followed by colon)
5. Has a singleton get_settings() function with @lru_cache
6. Includes a Settings class that combines all groups

**Constraints:**
- Use pydantic-settings with SettingsConfigDict
- All fields must have type hints
- Include Field descriptions
- Add a simple test at the bottom (if __name__ == "__main__")
- Follow AGENTS.md patterns

**Output:**
Return the complete bot/config.py file.
```

---

### تسک ۱.۳: ساختار فولدرها و main.py

**پرامپت:**

```
You are a senior Python backend engineer specializing in aiogram 3.x.

**Context:**
- Project: dutch-learning-bot
- Existing files: bot/config.py (Pydantic settings)
- Tech: aiogram 3.x, Python 3.11, async

**Task:**
Create bot/main.py that:
1. Initializes the Bot and Dispatcher
2. Sets up logging (structured logging with loguru or standard logging)
3. Includes a startup hook that:
   - Logs bot info (name, username)
   - Initializes database connection
4. Includes a shutdown hook that:
   - Closes database connection
   - Logs shutdown
5. Uses polling mode (dp.start_polling)
6. Includes basic error handling for unhandled exceptions
7. Has a main() async function with proper asyncio.run()

**Constraints:**
- Use aiogram 3.x syntax (not 2.x)
- Import config from bot.config
- Logging should include both file and console handlers
- Include a comment explaining why polling is chosen over webhook for MVP
- Do NOT add routers yet — just the core setup

**Output:**
Return the complete bot/main.py file.
```

---

### تسک ۱.۴: Database Connection و Models

**پرامپت:**

```
You are a senior Python backend engineer. We are building a Dutch learning Telegram bot.

**Context:**
- Project: dutch-learning-bot
- Database: SQLite with SQLAlchemy 2.x async
- Files to create: database/connection.py, database/models.py

**Task:**
1. database/connection.py:
   - Create async engine using create_async_engine
   - Create AsyncSessionLocal with async_sessionmaker
   - Create a get_db_session() async context manager
   - Include init_db() function that creates all tables

2. database/models.py with these SQLAlchemy 2.x models:
   - User: id (PK), telegram_id (unique), username, first_name, last_name, language_code, created_at, last_active_at, current_cefr_level, daily_streak, longest_streak, xp_points, subscription_tier
   - Word: id (PK), dutch_word, persian_translation, article (de/het), example_sentence_dutch, example_sentence_persian, cefr_level, category, audio_url (optional)
   - UserWord: id (PK), user_id (FK), word_id (FK), is_learned, learned_at, review_count, mistake_count
   - FSRSCard: id (PK), user_id (FK), word_id (FK), card_state, due_date, stability, difficulty, elapsed_days, scheduled_days, reps, lapses, last_review_date
   - ReviewLog: id (PK), card_id (FK), rating (1-4), review_datetime, scheduled_days, elapsed_days
   - Lesson: id (PK), title_dutch, title_persian, cefr_level, order_index, content_json, is_published
   - UserProgress: id (PK), user_id (FK), lesson_id (FK), completed_at, score
   - GamificationEvent: id (PK), user_id (FK), event_type, xp_earned, description, created_at
   - NotificationSchedule: id (PK), user_id (FK), notification_type, scheduled_time, is_enabled, timezone

**Constraints:**
- Use SQLAlchemy 2.x declarative base with Mapped[] and mapped_column
- All relationships must have proper ForeignKey and relationship()
- Include __tablename__ for each model
- Add indexes on frequently queried columns (telegram_id, user_id, due_date)
- Use DateTime(timezone=True) for all datetime fields
- Do NOT create migration files yet

**Output:**
Return both complete files.
```

---

### تسک ۱.۵: User Middleware و Auto-registration

**پرامپت:**

```
You are a senior Python backend engineer building a Telegram bot with aiogram 3.x.

**Context:**
- Project: dutch-learning-bot
- Existing: database/models.py with User model, database/connection.py
- Files to create: middlewares/user_middleware.py

**Task:**
Create a user middleware that:
1. Runs on every incoming update (message, callback, inline query)
2. Checks if the user exists in the database by telegram_id
3. If not exists, creates a new User record with:
   - telegram_id, username, first_name, last_name, language_code
   - current_cefr_level = "A0"
   - subscription_tier = "free"
   - created_at = now
4. If exists, updates last_active_at = now
5. Stores the user object in FSM context (data["user"]) so handlers can access it
6. Handles errors gracefully (logs error, doesn't break the update flow)

**Constraints:**
- Use aiogram 3.x BaseMiddleware
- Must be async
- Use database session from get_db_session()
- Include proper error handling with try/except
- Do NOT send messages to user from middleware (just register/update)
- Add type hints

**Output:**
Return the complete middlewares/user_middleware.py file.
```

---

### تسک ۱.۶: /start و /help Handlers + Main Menu Keyboard

**پرامپت:**

```
You are a senior Python backend engineer building a Telegram bot for Persian speakers learning Dutch.

**Context:**
- Project: dutch-learning-bot
- Existing: bot/main.py, middlewares/user_middleware.py
- Files to create: handlers/common.py, keyboards/main_menu.py

**Task:**
1. keyboards/main_menu.py:
   - Create a ReplyKeyboardMarkup with main menu buttons in Persian:
     - "📚 درس‌های امروز" (Lessons)
     - "🔄 مرور واژگان" (Review)
     - "🤖 چت با AI" (AI Chat)
     - "📊 پیشرفت من" (Progress)
     - "⚙️ تنظیمات" (Settings)
   - Include a helper function get_main_menu_keyboard() that returns the keyboard
   - Resize keyboard and make it persistent

2. handlers/common.py:
   - /start handler:
     - Send a welcome message in Persian with Dutch greeting
     - Include bot description and what it can do
     - Attach main menu keyboard
     - Message should be warm and encouraging
   - /help handler:
     - List all available commands with descriptions in Persian
     - Include tips for best learning experience
   - /cancel handler:
     - Clear any active FSM state
     - Return to main menu

**Constraints:**
- Use aiogram 3.x Router and handlers
- All text must be in Persian (Farsi)
- Include Dutch words where relevant for immersion
- Use the keyboard from keyboards/main_menu.py
- Add type hints and docstrings
- Register router in bot/loader.py (create this file too)

**Output:**
Return all three files: handlers/common.py, keyboards/main_menu.py, bot/loader.py
```

---

### تسک ۱.۷: Seed Database با داده‌های اولیه

**پرامپت:**

```
You are a senior Python backend engineer. We are building a Dutch learning bot.

**Context:**
- Project: dutch-learning-bot
- Existing: database/models.py with Word and Lesson models
- File to create: scripts/seed_database.py

**Task:**
Create a seed script that populates the database with:
1. 50 essential Dutch words for A0-A1 level with:
   - dutch_word, persian_translation, article (de/het where applicable)
   - example_sentence_dutch, example_sentence_persian
   - cefr_level (A0 or A1), category (greetings, numbers, colors, family, food, etc.)
2. 5 sample lessons for A0 level:
   - title_dutch, title_persian, cefr_level="A0", order_index
   - content_json with lesson structure (vocabulary list, grammar note, practice exercises)
3. The script should:
   - Connect to database
   - Check if data already exists (idempotent)
   - Insert data if not exists
   - Print summary of inserted records

**Constraints:**
- Use SQLAlchemy 2.x async session
- All Persian translations must be accurate
- Include common Dutch words that Persian speakers need first
- Words must include article (de/het) — this is critical for Dutch
- content_json should be valid JSON structure
- Include a main() function with asyncio.run()

**Output:**
Return the complete scripts/seed_database.py file.
```

---

## ۴. فاز ۲: Core Learning

### تسک ۲.۱: CEFR Curriculum Display

**پرامپت:**

```
You are a senior Python backend engineer building a Dutch learning Telegram bot.

**Context:**
- Project: dutch-learning-bot
- Existing: database/models.py (Lesson model), handlers/common.py
- Files to create/modify: handlers/curriculum.py, services/curriculum_service.py

**Task:**
1. services/curriculum_service.py:
   - get_available_lessons(user_id: int, cefr_level: str) -> list[Lesson]
   - get_lesson_detail(lesson_id: int) -> Lesson with content
   - mark_lesson_completed(user_id: int, lesson_id: int, score: float) -> None
   - get_user_current_level(user_id: int) -> str

2. handlers/curriculum.py:
   - /lessons command: Show available lessons for user's current CEFR level
     - Use InlineKeyboard with lesson titles
     - Show progress (completed/total) for each lesson
   - Callback for lesson selection: Display lesson content
     - Title in both Dutch and Persian
     - Vocabulary section with words and translations
     - Grammar note
     - "Complete Lesson" button
   - After completion: Show congratulations, award XP, suggest next lesson

**Constraints:**
- Use aiogram 3.x FSM for lesson flow
- All UI text in Persian
- Include Dutch text for immersion
- Use InlineKeyboardMarkup for navigation
- Add type hints and error handling
- Follow service layer pattern (handlers call services)

**Output:**
Return both complete files.
```

---

### تسک ۲.۲: Quiz System

**پرامپت:**

```
You are a senior Python backend engineer building a Dutch learning Telegram bot.

**Context:**
- Project: dutch-learning-bot
- Existing: handlers/curriculum.py, services/curriculum_service.py
- Files to create: handlers/quiz.py, services/quiz_service.py

**Task:**
1. services/quiz_service.py:
   - generate_quiz(user_id: int, cefr_level: str, quiz_type: str) -> Quiz
     - quiz_type: "multiple_choice", "fill_blank", "translation"
   - Quiz dataclass with: question, options, correct_answer, explanation_dutch, explanation_persian
   - validate_answer(quiz_id: int, user_answer: str) -> bool
   - get_quiz_stats(user_id: int) -> dict

2. handlers/quiz.py:
   - /quiz command: Ask user to choose quiz type (InlineKeyboard)
   - FSM for quiz flow:
     - State 1: Show question with options (InlineKeyboard with A, B, C, D)
     - State 2: Show result (correct/incorrect) with explanation
     - State 3: Ask "Next question?" or "Back to menu"
   - Track score during session
   - At end: Show final score and award XP

**Constraints:**
- Use aiogram 3.x FSM (StatesGroup)
- Questions must be in Dutch with Persian context
- For multiple choice: 4 options, 1 correct
- Include explanation for wrong answers (educational)
- All UI in Persian
- Add type hints

**Output:**
Return both complete files.
```

---

### تسک ۲.۳: FSRS Integration — Card Creation

**پرامپت:**

```
You are a senior Python backend engineer. We are integrating FSRS (spaced repetition) into a Dutch learning bot.

**Context:**
- Project: dutch-learning-bot
- Library: py-fsrs (Free Spaced Repetition Scheduler)
- Existing: database/models.py (FSRSCard, ReviewLog, Word models)
- Files to create: services/fsrs_service.py

**Task:**
Create services/fsrs_service.py that:
1. create_card(user_id: int, word_id: int) -> FSRSCard:
   - Initialize a new FSRS card using py-fsrs Scheduler
   - Save to database with state=Learning, due=now
   - Return the created card

2. get_due_cards(user_id: int, limit: int = 20) -> list[FSRSCard]:
   - Query cards where due_date <= now() AND user_id = user_id
   - Order by due_date ASC
   - Limit to specified number (default 20)
   - Join with Word to get word details

3. review_card(card_id: int, rating: int) -> FSRSCard:
   - rating: 1=Again, 2=Hard, 3=Good, 4=Easy
   - Load card from DB
   - Use py-fsrs Scheduler to calculate new state
   - Update card: state, due_date, stability, difficulty, etc.
   - Create ReviewLog entry
   - Return updated card

4. get_card_stats(user_id: int) -> dict:
   - Total cards, due today, learning, review, relearning counts

**Constraints:**
- Use py-fsrs library (from fsrs import Scheduler, Card, Rating)
- All database operations async with SQLAlchemy 2.x
- Include proper error handling
- Add type hints and docstrings
- Include a simple test function

**Output:**
Return the complete services/fsrs_service.py file.
```

---

### تسک ۲.۴: Daily Review Flow با Rating Buttons

**پرامپت:**

```
You are a senior Python backend engineer building a Dutch learning Telegram bot.

**Context:**
- Project: dutch-learning-bot
- Existing: services/fsrs_service.py, keyboards/main_menu.py
- Files to create: handlers/fsrs_review.py, keyboards/review_keyboard.py

**Task:**
1. keyboards/review_keyboard.py:
   - Create rating keyboard for FSRS review:
     - 4 buttons: "🔴 دوباره (Again)", "🟠 سخت (Hard)", "🟢 خوب (Good)", "🔵 آسان (Easy)"
   - Each button has callback_data with format: "review:{card_id}:{rating}"
   - Include "⏸️ بعداً" (Skip) and "🏠 منو" (Menu) buttons

2. handlers/fsrs_review.py:
   - /review command:
     - Check if user has due cards
     - If no cards: "امروز کارت مروری نداری! 🎉" with suggestion to learn new words
     - If cards: Show first card
   - Card display:
     - Dutch word (with article de/het if applicable)
     - "معنی را به خاطر بیاورید..." (Persian)
     - "Show Answer" button
   - After showing answer:
     - Persian translation
     - Example sentence in Dutch
     - Rating keyboard
   - Handle rating callback:
     - Update card with FSRS
     - Show next card or completion message
   - Completion:
     - "تبریک! {count} کارت مرور شد."
     - Show streak info
     - Award XP

**Constraints:**
- Use aiogram 3.x FSM for review flow (showing question → showing answer)
- All UI text in Persian
- Include Dutch pronunciation hints where relevant
- Use service layer (call fsrs_service)
- Handle edge case: user has no cards at all (first time)

**Output:**
Return both complete files.
```

---

### تسک ۲.۵: Word of the Day + Proactive Notifications

**پرامپت:**

```
You are a senior Python backend engineer building a Dutch learning Telegram bot.

**Context:**
- Project: dutch-learning-bot
- Existing: database/models.py, services/fsrs_service.py
- Files to create: services/notification_service.py, handlers/notifications.py
- Library: APScheduler for scheduling

**Task:**
1. services/notification_service.py:
   - get_word_of_the_day() -> Word:
     - Select a random word from user's current CEFR level
     - Track which words have been sent (avoid repeats)
   - schedule_daily_notifications(bot: Bot):
     - Schedule "Word of the Day" at 8:00 AM user timezone
     - Schedule "Review Reminder" at 8:00 PM if user has due cards
     - Use APScheduler AsyncScheduler
   - send_word_of_the_day(bot: Bot, user_id: int) -> None:
     - Send word with translation, example, and "Add to My Cards" button
   - send_review_reminder(bot: Bot, user_id: int) -> None:
     - Send reminder with count of due cards and "Start Review" button

2. handlers/notifications.py:
   - /settings command for notification preferences:
     - Enable/disable Word of the Day
     - Enable/disable Review Reminders
     - Set timezone
   - Callback handlers for "Add to My Cards" and "Start Review"

**Constraints:**
- Use APScheduler 3.x with AsyncIOScheduler
- Respect user timezone (store in NotificationSchedule)
- All messages in Persian with Dutch words
- Include "Disable Notifications" option in every message
- Handle users in different timezones
- Add type hints

**Output:**
Return both complete files.
```

---

## ۵. فاز ۳: AI Features

### تسک ۳.۱: Tiered AI Router (Cost Optimization)

**پرامپت:**

```
You are a senior Python backend engineer. We are building an AI-powered Dutch learning bot and need to optimize API costs.

**Context:**
- Project: dutch-learning-bot
- AI Providers: OpenAI (GPT-4o-mini, GPT-4o)
- Goal: 95% cost reduction through intelligent routing
- File to create: services/ai_router.py

**Task:**
Create services/ai_router.py that implements a 3-tier routing system:

1. Tier 0 — Python/Rule-based (Cost: $0):
   - FAQ lookup: Common questions about Dutch grammar, articles, etc.
   - Dictionary lookup: Simple word translations
   - Command parsing: Bot commands
   - Implementation: Keyword matching + pre-written responses

2. Tier 1 — Cheap Model (GPT-4o-mini, Cost: ~$0.0001/call):
   - Simple translations
   - Grammar checks
   - Short explanations
   - Classification tasks

3. Tier 2 — Expensive Model (GPT-4o, Cost: ~$0.003/call):
   - Complex cultural explanations
   - Essay review
   - Deep personalization
   - Pronunciation analysis

Implementation:
- classify_query(user_message: str) -> QueryType:
  - Use GPT-4o-mini with structured output (JSON mode)
  - Classify into: FAQ, DICTIONARY, SIMPLE_TRANSLATION, COMPLEX_EXPLANATION, DEEP_PERSONALIZATION
  - Include confidence score

- route_and_respond(user_id: int, message: str, context: dict) -> str:
  - Classify the query
  - Route to appropriate handler
  - Track cost per user (daily limit)
  - Return response

- Pre-written FAQ responses (Persian) for:
  - "de/het چه فرقی دارن؟"
  - "ترتیب کلمات در هلندی چطوره؟"
  - "فعل‌های جداشدنی چی هستن؟"
  - "تلفظ g/ch چطوره؟"

**Constraints:**
- Use Pydantic BaseModel for structured output
- Include cost tracking (per user, per day)
- All pre-written responses in Persian
- Include fallback to Tier 2 if classification confidence < 0.7
- Add type hints and docstrings
- Include a simple test

**Output:**
Return the complete services/ai_router.py file.
```

---

### تسک ۳.۲: AI Chat Handler (Cultural Bridge)

**پرامپت:**

```
You are a senior Python backend engineer building a Dutch learning Telegram bot.

**Context:**
- Project: dutch-learning-bot
- Existing: services/ai_router.py
- Files to create: handlers/ai_chat.py

**Task:**
Create handlers/ai_chat.py that:
1. /chat command: Start AI conversation mode
   - Send welcome message explaining what user can ask
   - Examples: "معنی 'gezellig' چیه؟", "تفاوت 'zijn' و 'hebben'", "چطور در رستوران سفارش بدم؟"
   - Set FSM state to ChatMode

2. In ChatMode state:
   - Receive any text message
   - Call ai_router.route_and_respond()
   - Send AI response back to user
   - Include "🔄 ادامه چت" and "🏠 منو" buttons
   - Track conversation history (last 10 messages) for context

3. Cultural Bridge feature:
   - If user asks about cultural differences (Persian vs Dutch):
     - AI explains with specific examples
     - Include scenarios (restaurant, workplace, greetings, etc.)
   - Special handling for "taarof" vs Dutch directness

4. Grammar Correction:
   - If user writes a Dutch sentence:
     - AI checks grammar
     - Returns corrected version with explanation in Persian

**Constraints:**
- Use aiogram 3.x FSM
- All UI in Persian
- Conversation history stored in FSM state (or Redis if available)
- Include "Clear History" option
- Handle long responses (Telegram 4096 char limit)
- Add type hints

**Output:**
Return the complete handlers/ai_chat.py file.
```

---

### تسک ۳.۳: Pronunciation — Whisper STT + TTS

**پرامپت:**

```
You are a senior Python backend engineer. We are building pronunciation practice for a Dutch learning bot.

**Context:**
- Project: dutch-learning-bot
- APIs: OpenAI Whisper (STT), OpenAI TTS
- Files to create: handlers/pronunciation.py, services/pronunciation_service.py

**Task:**
1. services/pronunciation_service.py:
   - generate_target_audio(text: str) -> bytes:
     - Use OpenAI TTS with model "tts-1"
     - Voice: "alloy" or "nova"
     - Return audio bytes
   - transcribe_user_audio(audio_file_path: str, language: str = "nl") -> str:
     - Use OpenAI Whisper
     - Return transcribed text
   - compare_pronunciation(target: str, user_spoken: str) -> dict:
     - Use difflib or Levenshtein distance
     - Return: accuracy_score (0-100), differences list, feedback_message (Persian)

2. handlers/pronunciation.py:
   - /pronounce command:
     - Show list of challenging Dutch sounds for Persian speakers:
       - "g/ch" (حلقومی)
       - "ui" (دفتونگ)
       - "sch" (ترکیب s+حلقومی)
       - "ij/ei" (دفتونگ)
     - Or user can type any Dutch word
   - FSM flow:
     - State 1: Show target word + "🎧 گوش کنید" button (plays TTS)
     - State 2: "🎤 ضبط کنید" — wait for voice message
     - State 3: Process voice with Whisper
     - State 4: Show comparison result with feedback
       - If correct: "عالی! تلفظت دقیق بود 🎉"
       - If wrong: "نزدیک بود! سعی کن 'g' را عمیق‌تر در گلو تولید کنی"
   - Include "🔁 تمرین دوباره" and "➡️ کلمه بعدی" buttons

**Constraints:**
- Use aiogram 3.x FSM
- Handle voice messages (message.voice)
- Download voice file to temp, process, delete
- All feedback in Persian with phonetic hints
- Include example words for each difficult sound
- Add type hints and error handling

**Output:**
Return both complete files.
```

---

## ۶. فاز ۴: Engagement

### تسک ۴.۱: Gamification — XP, Levels, Streaks

**پرامپت:**

```
You are a senior Python backend engineer. We are building gamification for a Dutch learning bot.

**Context:**
- Project: dutch-learning-bot
- Existing: database/models.py (GamificationEvent, User models)
- Files to create: services/gamification_service.py, handlers/gamification.py

**Task:**
1. services/gamification_service.py:
   - award_xp(user_id: int, event_type: str, base_xp: int) -> int:
     - event_types: "lesson_complete", "review_card", "quiz_correct", "streak_maintained", "pronunciation_good"
     - Apply multipliers: streak_bonus, daily_bonus, level_bonus
     - Save to GamificationEvent
     - Return total XP awarded
   - calculate_level(xp: int) -> int:
     - Level formula: level = floor(sqrt(xp / 100))
     - Max level: 50
   - check_streak(user_id: int) -> dict:
     - Check if user reviewed yesterday
     - If yes: increment streak
     - If no: reset streak (but allow "streak recovery" within 24h)
     - Return: current_streak, longest_streak, is_at_risk
   - get_leaderboard(limit: int = 10) -> list[dict]:
     - Top users by XP
     - Include user's rank

2. handlers/gamification.py:
   - /profile command:
     - Show user stats: Level, XP, Streak, Cards Learned, Lessons Completed
     - Progress bar to next level
     - Recent achievements
   - /leaderboard command:
     - Show top 10 users
     - Highlight current user's position
   - XP notification:
     - After any activity, show "+{xp} XP" with animation text
   - Streak at risk:
     - If user hasn't studied today and streak > 3:
       - Send reminder: "استریک {n} روزه‌ات در خطره! 🔥"

**Constraints:**
- Use aiogram 3.x
- All UI in Persian
- Include Dutch phrases as rewards (unlock at levels)
- Streak recovery: allow 1 "freeze" per week for free users
- Add type hints

**Output:**
Return both complete files.
```

---

### تسک ۴.۲: Study Groups (Dutch Circles)

**پرامپت:**

```
You are a senior Python backend engineer. We are building study groups for a Dutch learning bot.

**Context:**
- Project: dutch-learning-bot
- Feature: Dutch Circles — groups of 3-5 Persian speakers at similar CEFR level
- Files to create: handlers/study_groups.py, services/study_group_service.py

**Task:**
1. services/study_group_service.py:
   - create_group(creator_id: int, name: str, cefr_level: str, max_members: int = 5) -> Group
   - join_group(user_id: int, group_id: int) -> bool
   - leave_group(user_id: int, group_id: int) -> bool
   - get_group_members(group_id: int) -> list[User]
   - match_user_to_group(user_id: int) -> Group | None:
     - Find groups at user's CEFR level with open spots
     - Prefer groups with similar study times
   - get_group_challenges(group_id: int) -> list[Challenge]

2. handlers/study_groups.py:
   - /groups command:
     - Show user's current groups
     - "Create Group" and "Join Group" buttons
   - Create Group flow (FSM):
     - Name → CEFR Level → Max Members → Confirm
   - Join Group:
     - Show available groups at user's level
     - Group info: name, members count, activity level
   - Group Chat features:
     - Weekly challenge: "این هفته ۵ موضوع KNM را با هم تمام کنید"
     - Group quiz: collaborative quiz with shared score
     - Story writing: each member adds one Dutch sentence
   - Group notifications:
     - Notify when new member joins
     - Daily challenge reminder

**Constraints:**
- Use aiogram 3.x FSM
- Groups are Telegram-based (use invite links or group chat integration)
- All UI in Persian
- Max 5 members per group (research shows this is optimal)
- Include group activity score
- Add type hints

**Output:**
Return both complete files.
```

---

### تسک ۴.۳: Progress Tracking & Exam Prep

**پرامپت:**

```
You are a senior Python backend engineer. We are building progress tracking for a Dutch learning bot.

**Context:**
- Project: dutch-learning-bot
- Exams: Inburgering (A2), NT2 Programma I (B1), NT2 Programma II (B2)
- Files to create: handlers/progress.py, services/progress_service.py

**Task:**
1. services/progress_service.py:
   - get_user_stats(user_id: int) -> UserStats:
     - total_words_learned, total_lessons_completed
     - current_streak, longest_streak
     - accuracy_rate (quiz), review_consistency
     - cefr_progress: {A0: 100%, A1: 60%, A2: 0%, ...}
   - calculate_exam_readiness(user_id: int, exam_type: str) -> dict:
     - exam_type: "inburgering", "nt2_i", "nt2_ii"
     - Return: readiness_score (0-100%), weak_areas, recommended_study_hours
   - get_weekly_report(user_id: int) -> dict:
     - Study time, cards reviewed, lessons completed, XP earned
     - Comparison to previous week

2. handlers/progress.py:
   - /progress command:
     - Visual progress dashboard (text-based with emojis)
     - CEFR level progress bars
     - Stats summary
   - /exam command:
     - Show exam options: Inburgering, NT2 I, NT2 II
     - For selected exam:
       - Readiness score
       - Weak areas (e.g., "de/het accuracy: 45%")
       - Study plan recommendation
       - Mock exam button
   - Mock Exam flow (FSM):
     - 10 questions simulating real exam
     - Timer (optional)
     - Immediate feedback
     - Final score with pass/fail
   - Weekly report:
     - Sent every Sunday at 8 PM
     - Summary of week's activity
     - Encouragement message

**Constraints:**
- Use aiogram 3.x
- All UI in Persian
- Include Dutch exam terminology with explanations
- Mock exam questions should simulate real Inburgering format
- Progress bars using emoji blocks (▓▓▓░░)
- Add type hints

**Output:**
Return both complete files.
```

---

## ۷. فاز ۵: Polish & Deploy

### تسک ۵.۱: Admin Panel & Error Monitoring

**پرامپت:**

```
You are a senior Python backend engineer. We are adding admin features to a Dutch learning bot.

**Context:**
- Project: dutch-learning-bot
- Existing: All previous handlers and services
- Files to create: handlers/admin.py, middlewares/admin_middleware.py

**Task:**
1. middlewares/admin_middleware.py:
   - Check if user is in ADMIN_IDS list from config
   - If yes, set data["is_admin"] = True
   - Otherwise False

2. handlers/admin.py:
   - /admin command (only for admins):
     - Show admin menu with InlineKeyboard:
       - "📊 آمار کاربران" (User Stats)
       - "📈 رشد روزانه" (Daily Growth)
       - "📝 مدیریت درس‌ها" (Manage Lessons)
       - "⚙️ تنظیمات ربات" (Bot Settings)
   - User Stats:
     - Total users, active today, active this week
     - New users today
     - Top 10 by XP
   - Daily Growth:
     - Chart-like text representation of user growth
     - Active users per day (last 7 days)
   - Manage Lessons:
     - Add new lesson (FSM flow)
     - Edit existing lesson
     - Publish/unpublish
   - Broadcast message:
     - Send message to all users
     - Confirmation before sending
   - Error monitoring integration:
     - Log all unhandled exceptions
     - Send critical errors to admin

**Constraints:**
- Use aiogram 3.x
- All admin UI in Persian
- Include confirmation for destructive actions
- Rate limit admin commands
- Add type hints

**Output:**
Return both complete files.
```

---

### تسک ۵.۲: Deploy به Railway

**پرامپت:**

```
You are a DevOps engineer. We are deploying a Python Telegram bot.

**Context:**
- Project: dutch-learning-bot
- Platform: Railway (railway.app)
- Runtime: Python 3.11

**Task:**
Create deployment files:
1. Dockerfile:
   - Python 3.11 slim image
   - Install dependencies from pyproject.toml
   - Set working directory
   - Run bot/main.py

2. railway.json (if needed) or Procfile:
   - Define start command

3. docker-compose.yml (for local testing):
   - Bot service
   - Optional: PostgreSQL service for local development

4. Update bot/main.py:
   - Add webhook support (optional, for Railway)
   - Keep polling as default
   - Add health check endpoint (if using webhook)

5. Create .github/workflows/deploy.yml:
   - GitHub Actions workflow
   - Trigger on push to main
   - Deploy to Railway using Railway CLI

**Constraints:**
- Use multi-stage Docker build for smaller image
- Include .dockerignore
- Environment variables from Railway dashboard
- Health check for Railway
- Add type hints where applicable

**Output:**
Return all deployment files.
```

---

## ۸. چک‌لیست‌های امنیتی

### قبل از هر Deploy

- [ ] API Keys فقط در .env — هیچ‌کدام در کد نیست
- [ ] .env در .gitignore
- [ ] Input validation روی همه پیام‌های کاربر
- [ ] Parameterized queries (SQL Injection protection)
- [ ] Rate limiting روی AI API calls
- [ ] Error messages اطلاعات حساس نمایش نمی‌دهند
- [ ] Privacy Mode در Telegram BotFather فعال است
- [ ] bandit scan اجرا شده
- [ ] No hardcoded admin IDs (only in .env)

### Security Review Prompt

```
Act as a security expert. Review the following code for vulnerabilities:
{paste code}

Check for:
1. SQL Injection
2. Hardcoded secrets
3. Input validation issues
4. Error handling leaks
5. Rate limiting gaps
6. Authentication bypass

Report findings with severity (Critical/High/Medium/Low) and fix suggestions.
```

---

## ۹. نکات طلایی Vibe Coding

### DO's ✅
- **یک Step در هر Prompt** — AI پیشنهاد چند فیچر همزمان می‌دهد، قبول نکن
- **Git Commit بعد از هر Step** — تاریخچه تمیز
- **Review هر خط کد** — بفهم چی شده
- **Test قبل از Commit** — حداقل run کن ببین error نده
- **Session جدید بعد از Refactoring** — Context pollution را پاک کن
- **AGENTS.md را Update کن** — اگر Pattern جدیدی پیدا کردی

### DON'Ts ❌
- **چند فیچر در یک Prompt** — Debug غیرممکن می‌شه
- **Accept کد بدون Review** — AI گاهی اشتباه می‌کنه
- **Skip Error Handling** — AI اغلب فراموش می‌کنه
- **Hardcode Secrets** — هرگز!
- **Spaghetti Code** — Modular بساز از روز اول
- **Over-rely on AI** — Decision معماری با خودت

### Template Prompt برای هر تسک

```
## Context
Project: Dutch Learning Bot for Persian Speakers
Current Step: {X} of {Y}
Tech Stack: aiogram 3.x, Python 3.11, SQLite, SQLAlchemy 2 async, py-fsrs
Existing Files: {list relevant files}
Patterns: {reference PATTERNS.md}

## Task
Implement ONLY: {specific single feature}

## Constraints
- Do NOT implement any other feature
- Use async/await everywhere
- Follow existing code patterns
- Add type hints
- Include error handling
- Write a simple test if possible
- All UI text in Persian (Farsi)
- Include Dutch words where relevant for immersion

## Output
Return the complete code for the file(s) needed.
```

---

## 📎 پیوست: فایل‌های تکمیلی

### `.cursorrules` (برای Cursor IDE)

```
# Dutch Learning Bot — Cursor Rules

## Code Style
- Python 3.11+, always async/await
- Type hints mandatory
- Docstrings for all public functions
- Prefer keyword arguments
- Max line length: 100

## Architecture
- handlers/ — Telegram I/O only
- services/ — Business logic
- database/ — Data access
- No business logic in handlers
- No DB queries in handlers

## Language
- Code comments: English
- User-facing text: Persian (Farsi)
- Dutch words in user text for immersion

## Security
- Never hardcode secrets
- Validate all inputs
- Parameterized queries only
- No sensitive data in logs
```

---

*این راهنما بر اساس تحقیق عمیق از ۱۸۰+ منبع و بهترین شیوه‌های Vibe Coding تهیه شده است.*

*موفق باشید! 🚀*
