"""Signed tokens linking a Telegram user to the membership website.

The bot generates ``make_subscription_token(user_id)`` and embeds it in the
checkout URL. The website verifies it with the shared HMAC secret to learn
which user is paying — without the user logging in. Tokens carry an issue
timestamp so the site can reject stale links.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import time

from bot.config import get_settings

logger = logging.getLogger(__name__)


def _b64e(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def _secret() -> bytes:
    secret = get_settings().subscription.token_secret
    if not secret:
        raise RuntimeError("SUBSCRIPTION_TOKEN_SECRET is not configured.")
    return secret.encode("utf-8")


def _sign(payload: str) -> str:
    sig = hmac.new(_secret(), payload.encode("utf-8"), hashlib.sha256).digest()
    return _b64e(sig)


def make_subscription_token(user_id: int) -> str:
    """Return a signed ``<payload>.<signature>`` token for the user."""
    payload = _b64e(f"{user_id}:{int(time.time())}".encode("utf-8"))
    return f"{payload}.{_sign(payload)}"


def verify_subscription_token(token: str, *, max_age_seconds: int | None = None) -> int | None:
    """Return the ``user_id`` if the token is valid (and fresh), else ``None``."""
    try:
        payload, signature = token.split(".", 1)
    except ValueError:
        return None
    if not hmac.compare_digest(signature, _sign(payload)):
        return None
    try:
        user_str, issued_str = _b64d(payload).decode("utf-8").split(":", 1)
        user_id, issued = int(user_str), int(issued_str)
    except (ValueError, UnicodeDecodeError):
        return None
    if max_age_seconds is not None and (time.time() - issued) > max_age_seconds:
        return None
    return user_id
