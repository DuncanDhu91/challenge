"""
Test suite for webhook processing (asynchronous tests)
Backend Engineer 2 - 25 minutes
"""
import pytest
import asyncio
from tests.fixtures.payment_factory import PaymentFactory, WebhookFactory


@pytest.mark.asyncio
@pytest.mark.webhook
class TestWebhookProcessing:
    """Test async webhook delivery and payment status updates"""

    async def test_webhook_updates_payment_to_approved(
        self, api_client, send_webhook, wait_for_status, unique_idempotency_key
    ):
        """
        Test 6: Verify webhook correctly updates payment status

        P0: Core webhook functionality.
        """
        # Arrange: Create pending payment
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )
        create_response = await api_client.post("/payments", json=payment_data)
        payment_id = create_response.json()["payment_id"]

        # Act: Send approved webhook
        webhook = WebhookFactory.create_approved_webhook(payment_id)
        webhook_response = await send_webhook(webhook)

        # Assert webhook accepted
        assert webhook_response.status_code == 200

        # Wait for async processing (smart polling, not sleep)
        updated_payment = await wait_for_status(payment_id, "approved", timeout=5)

        assert updated_payment["status"] == "approved"
        assert updated_payment["payment_id"] == payment_id

    async def test_webhook_before_customer_returns(
        self, api_client, send_webhook, wait_for_status, unique_idempotency_key
    ):
        """
        Test 7: Race condition - webhook arrives before redirect return

        P0 CRITICAL: Catches Banco Azul incident scenario.
        Customer still at bank portal, webhook arrives, then customer returns.
        """
        # Arrange: Create payment
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )
        create_response = await api_client.post("/payments", json=payment_data)
        payment_id = create_response.json()["payment_id"]

        # Act: Webhook arrives while customer at bank (they haven't returned)
        webhook = WebhookFactory.create_approved_webhook(payment_id)
        await send_webhook(webhook)

        # Wait for webhook processing
        await asyncio.sleep(1)

        # Customer returns and checks status
        status_response = await api_client.get(f"/payments/{payment_id}")

        # Assert: Status already updated (webhook arrived first)
        assert status_response.status_code == 200
        payment = status_response.json()
        assert payment["status"] == "approved"

    async def test_customer_returns_before_webhook(
        self, api_client, send_webhook, unique_idempotency_key
    ):
        """
        Test 8: Race condition - customer returns before webhook

        P0 CRITICAL: Customer sees "processing" state until webhook arrives.
        """
        # Arrange: Create payment
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )
        create_response = await api_client.post("/payments", json=payment_data)
        payment_id = create_response.json()["payment_id"]

        # Act: Customer returns immediately (webhook hasn't arrived)
        status_response = await api_client.get(f"/payments/{payment_id}")

        # Assert: Payment still pending (webhook not arrived yet)
        assert status_response.status_code == 200
        payment = status_response.json()
        assert payment["status"] == "pending"

        # Webhook arrives 2 seconds later
        await asyncio.sleep(2)
        webhook = WebhookFactory.create_approved_webhook(payment_id)
        await send_webhook(webhook)

        # Assert: Status eventually updates
        await asyncio.sleep(1)
        final_response = await api_client.get(f"/payments/{payment_id}")
        final_payment = final_response.json()
        assert final_payment["status"] == "approved"

    async def test_duplicate_webhook_idempotency(
        self, api_client, send_webhook, unique_idempotency_key
    ):
        """
        Test 9: Same webhook delivered multiple times (idempotency)

        P0 CRITICAL: Prevents double processing, duplicate charges.
        """
        # Arrange: Create payment
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )
        create_response = await api_client.post("/payments", json=payment_data)
        payment_id = create_response.json()["payment_id"]

        webhook = WebhookFactory.create_approved_webhook(payment_id)

        # Act: Send same webhook 3 times (simulates retries)
        response1 = await send_webhook(webhook)
        response2 = await send_webhook(webhook)
        response3 = await send_webhook(webhook)

        # Assert: All webhook deliveries accepted
        assert response1.status_code == 200
        assert response2.status_code == 200
        assert response3.status_code == 200

        # Assert: Second and third are marked as idempotent
        assert response2.json().get("idempotent") is True
        assert response3.json().get("idempotent") is True

        # Assert: Payment processed only once
        payment_response = await api_client.get(f"/payments/{payment_id}")
        payment = payment_response.json()
        assert payment["status"] == "approved"
        assert payment["webhook_count"] == 1  # Not 3!

    async def test_out_of_order_webhooks(
        self, api_client, send_webhook, unique_idempotency_key
    ):
        """
        Test 10: Expired webhook arrives after approved webhook

        P1: Timestamp-based ordering prevents incorrect status updates.
        """
        # Arrange: Create payment
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )
        create_response = await api_client.post("/payments", json=payment_data)
        payment_id = create_response.json()["payment_id"]

        # Act: Send approved webhook (timestamp: now)
        approved_webhook = WebhookFactory.create_approved_webhook(payment_id)
        await send_webhook(approved_webhook)
        await asyncio.sleep(1)

        # Send expired webhook with OLDER timestamp
        expired_webhook = WebhookFactory.create_old_webhook(
            payment_id, age_seconds=60, status="expired"
        )
        expired_response = await send_webhook(expired_webhook)

        # Assert: Expired webhook rejected/ignored (out of order)
        assert expired_response.json().get("out_of_order") is True

        # Assert: Status remains approved (newer webhook wins)
        payment_response = await api_client.get(f"/payments/{payment_id}")
        payment = payment_response.json()
        assert payment["status"] == "approved"

    async def test_declined_payment_webhook(
        self, api_client, send_webhook, wait_for_status, unique_idempotency_key
    ):
        """
        Test 11: Bank declines payment

        P1: Failure scenario handling.
        """
        # Arrange: Create payment
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )
        create_response = await api_client.post("/payments", json=payment_data)
        payment_id = create_response.json()["payment_id"]

        # Act: Send declined webhook
        webhook = WebhookFactory.create_declined_webhook(payment_id)
        await send_webhook(webhook)

        # Assert: Status updated to declined
        updated_payment = await wait_for_status(payment_id, "declined", timeout=5)
        assert updated_payment["status"] == "declined"
        assert updated_payment["reason"] == "insufficient_funds"
