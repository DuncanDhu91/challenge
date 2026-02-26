"""Pytest configuration and shared fixtures"""
import asyncio
import pytest
import httpx
from typing import AsyncGenerator, Generator
import time

# Test configuration
API_URL = "http://localhost:8000"
WEBHOOK_URL = f"{API_URL}/webhooks"


@pytest.fixture(scope="session")
def event_loop():
    """Create event loop for async tests"""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def api_client() -> AsyncGenerator[httpx.AsyncClient, None]:
    """HTTP client for API requests"""
    async with httpx.AsyncClient(base_url=API_URL, timeout=10.0) as client:
        yield client


@pytest.fixture(autouse=True)
async def cleanup_payments(api_client):
    """Clean up all payments before each test"""
    # Run test
    yield

    # Cleanup after test
    try:
        await api_client.delete("/payments")
    except Exception:
        pass  # Ignore cleanup errors


async def wait_for_payment_status(
    client: httpx.AsyncClient,
    payment_id: str,
    expected_status: str,
    timeout: int = 10,
    poll_interval: float = 0.5
) -> dict:
    """
    Poll payment status until it matches expected or timeout.

    This prevents flaky tests by replacing arbitrary sleeps with
    smart polling that returns as soon as the condition is met.
    """
    start_time = time.time()

    while time.time() - start_time < timeout:
        response = await client.get(f"/payments/{payment_id}")

        if response.status_code == 200:
            payment = response.json()
            if payment["status"] == expected_status:
                return payment

        await asyncio.sleep(poll_interval)

    # Timeout reached
    final_response = await client.get(f"/payments/{payment_id}")
    payment = final_response.json() if final_response.status_code == 200 else {}

    raise TimeoutError(
        f"Payment {payment_id} did not reach status '{expected_status}' "
        f"within {timeout}s. Current status: {payment.get('status', 'unknown')}"
    )


@pytest.fixture
def wait_for_status(api_client):
    """Fixture that provides the wait_for_payment_status helper"""
    async def _wait(payment_id: str, expected_status: str, timeout: int = 10):
        return await wait_for_payment_status(
            api_client, payment_id, expected_status, timeout
        )
    return _wait


@pytest.fixture
async def send_webhook(api_client):
    """Helper to send webhook to API"""
    async def _send(webhook_payload: dict):
        response = await api_client.post("/webhooks", json=webhook_payload)
        return response
    return _send


@pytest.fixture
def unique_idempotency_key():
    """Generate unique idempotency key for each test"""
    import uuid
    return str(uuid.uuid4())
