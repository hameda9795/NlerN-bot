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
async def business_logic(*, user_id: int, data: str) -> Result:
    # 1. Fetch from DB
    # 2. Process
    # 3. Save to DB
    # 4. Return result
```

## Error Handling
```python
try:
    result = await some_async_operation()
except SpecificException as exc:
    logger.error("Context: %s", exc)
    await message.answer("پیام خطای فارسی")
```

## DB Session Pattern
```python
async with get_db_session() as session:
    result = await session.execute(select(Model).where(...))
    obj = result.scalar_one_or_none()
```
