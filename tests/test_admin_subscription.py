"""Fail-safe behavior for admin-triggered Mollie cancellation."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from services import admin_service
from services import mollie_client as mollie


def _subscription() -> SimpleNamespace:
    return SimpleNamespace(
        mollie_customer_id="cst_test",
        mollie_subscription_id="sub_test",
    )


@pytest.mark.asyncio
async def test_admin_cancel_confirms_remote_then_updates_local(monkeypatch):
    monkeypatch.setattr(
        admin_service.subs,
        "get_subscription",
        AsyncMock(return_value=_subscription()),
    )
    monkeypatch.setattr(
        admin_service.mollie,
        "get_subscription",
        AsyncMock(return_value={"status": "active"}),
    )
    remote_cancel = AsyncMock()
    local_cancel = AsyncMock()
    monkeypatch.setattr(admin_service.mollie, "cancel_subscription", remote_cancel)
    monkeypatch.setattr(admin_service.subs, "cancel", local_cancel)

    await admin_service.cancel_subscription(user_id=7)

    remote_cancel.assert_awaited_once_with(
        customer_id="cst_test", subscription_id="sub_test"
    )
    local_cancel.assert_awaited_once_with(user_id=7)


@pytest.mark.asyncio
async def test_admin_cancel_treats_remote_404_as_already_absent(monkeypatch):
    monkeypatch.setattr(
        admin_service.subs,
        "get_subscription",
        AsyncMock(return_value=_subscription()),
    )
    monkeypatch.setattr(
        admin_service.mollie,
        "get_subscription",
        AsyncMock(
            side_effect=mollie.MollieError("not found", status_code=404)
        ),
    )
    local_cancel = AsyncMock()
    monkeypatch.setattr(admin_service.subs, "cancel", local_cancel)

    await admin_service.cancel_subscription(user_id=7)

    local_cancel.assert_awaited_once_with(user_id=7)


@pytest.mark.asyncio
async def test_admin_cancel_preserves_local_state_on_mollie_failure(monkeypatch):
    monkeypatch.setattr(
        admin_service.subs,
        "get_subscription",
        AsyncMock(return_value=_subscription()),
    )
    error = mollie.MollieError("server error", status_code=503)
    monkeypatch.setattr(
        admin_service.mollie,
        "get_subscription",
        AsyncMock(side_effect=error),
    )
    local_cancel = AsyncMock()
    monkeypatch.setattr(admin_service.subs, "cancel", local_cancel)

    with pytest.raises(mollie.MollieError) as captured:
        await admin_service.cancel_subscription(user_id=7)

    assert captured.value.status_code == 503
    local_cancel.assert_not_awaited()
