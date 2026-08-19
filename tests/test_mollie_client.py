"""Contract tests for structured Mollie HTTP failures."""

from __future__ import annotations

import httpx
import pytest

from services import mollie_client as mollie


@pytest.mark.asyncio
async def test_http_error_exposes_status_and_response_context(monkeypatch):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status_code=404,
            json={"status": 404, "detail": "Subscription not found"},
            request=request,
        )

    transport = httpx.MockTransport(handler)
    real_async_client = httpx.AsyncClient
    monkeypatch.setattr(mollie, "_api_key", lambda: "test_key")
    monkeypatch.setattr(
        mollie.httpx,
        "AsyncClient",
        lambda **kwargs: real_async_client(transport=transport, **kwargs),
    )

    with pytest.raises(mollie.MollieError) as captured:
        await mollie.get_subscription(
            customer_id="cst_test", subscription_id="sub_missing"
        )

    error = captured.value
    assert error.status_code == 404
    assert "Subscription not found" in (error.response_body or "")
    assert error.method == "GET"
    assert error.path == "/customers/cst_test/subscriptions/sub_missing"
