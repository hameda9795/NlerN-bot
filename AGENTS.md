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
- bot/ — Core setup (config, loader, main)
- utils/ — Shared helpers
- keyboards/ — Telegram UI keyboards
- middlewares/ — aiogram middlewares

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
