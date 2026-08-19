"""Minimal async Mollie API client (httpx).

Only the calls the membership site needs: create a customer, start a first
(mandate-creating) iDEAL payment, read a payment, and create a recurring
subscription. Amounts are EUR. Errors raise :class:`MollieError`.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from bot.config import get_settings

logger = logging.getLogger(__name__)

_API_BASE = "https://api.mollie.com/v2"
_TIMEOUT = 20.0


class MollieError(Exception):
    """Raised when a Mollie API call fails."""

    def __init__(
        self,
        message: str,
        *,
        status_code: int | None = None,
        response_body: str | None = None,
        method: str | None = None,
        path: str | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body
        self.method = method
        self.path = path


def _api_key() -> str:
    key = get_settings().subscription.mollie_api_key.strip()
    if not key:
        raise MollieError("MOLLIE_API_KEY is not configured.")
    return key


def _amount(value_eur: float) -> dict[str, str]:
    return {"currency": "EUR", "value": f"{value_eur:.2f}"}


async def _request(method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    headers = {"Authorization": f"Bearer {_api_key()}"}
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
            resp = await client.request(
                method, f"{_API_BASE}{path}", json=payload, headers=headers
            )
    except httpx.HTTPError as exc:
        raise MollieError(
            f"{method} {path} failed before receiving a response: {exc}",
            method=method,
            path=path,
        ) from exc
    if resp.status_code >= 400:
        body = resp.text[:1000]
        raise MollieError(
            f"{method} {path} -> {resp.status_code}: {body[:300]}",
            status_code=resp.status_code,
            response_body=body,
            method=method,
            path=path,
        )
    if not resp.text:
        return {}
    return resp.json()


async def create_customer(*, name: str, email: str) -> dict[str, Any]:
    """Create a Mollie customer (needed for recurring/SEPA mandates)."""
    return await _request("POST", "/customers", {"name": name, "email": email})


async def create_first_payment(
    *,
    customer_id: str,
    amount_eur: float,
    description: str,
    redirect_url: str,
    webhook_url: str,
    metadata: dict[str, Any],
) -> dict[str, Any]:
    """Start a first iDEAL payment that establishes a SEPA mandate on success."""
    return await _request(
        "POST",
        "/payments",
        {
            "amount": _amount(amount_eur),
            "description": description,
            "redirectUrl": redirect_url,
            "webhookUrl": webhook_url,
            "method": "ideal",
            "customerId": customer_id,
            "sequenceType": "first",
            "metadata": metadata,
        },
    )


async def get_payment(payment_id: str) -> dict[str, Any]:
    """Fetch the authoritative payment object (never trust the webhook body)."""
    return await _request("GET", f"/payments/{payment_id}")


async def create_subscription(
    *,
    customer_id: str,
    amount_eur: float,
    description: str,
    webhook_url: str,
    start_date: str,
) -> dict[str, Any]:
    """Create a monthly recurring subscription charged via the SEPA mandate."""
    return await _request(
        "POST",
        f"/customers/{customer_id}/subscriptions",
        {
            "amount": _amount(amount_eur),
            "interval": "1 month",
            "description": description,
            "webhookUrl": webhook_url,
            "startDate": start_date,
        },
    )


async def get_subscription(*, customer_id: str, subscription_id: str) -> dict[str, Any]:
    """Fetch one Mollie subscription for recovery/status checks."""
    return await _request(
        "GET", f"/customers/{customer_id}/subscriptions/{subscription_id}"
    )


async def cancel_subscription(*, customer_id: str, subscription_id: str) -> None:
    """Cancel a recurring subscription (stops future charges immediately)."""
    await _request("DELETE", f"/customers/{customer_id}/subscriptions/{subscription_id}")
