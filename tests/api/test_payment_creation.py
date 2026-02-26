"""
Test suite for payment creation (synchronous API tests)
Backend Engineer 1 - 25 minutes
"""
import pytest
from tests.fixtures.payment_factory import PaymentFactory


@pytest.mark.asyncio
class TestPaymentCreation:
    """Test payment creation happy path and validation"""

    async def test_create_pse_payment_happy_path(
        self, api_client, unique_idempotency_key
    ):
        """
        Test 1: Verify PSE payment initializes correctly

        Critical path test for payment creation.
        """
        # Arrange
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )

        # Act
        response = await api_client.post("/payments", json=payment_data)

        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["status"] == "pending"
        assert data["redirect_url"] is not None
        assert "payment_id" in data
        assert data["amount"] == payment_data["amount"]
        assert data["currency"] == payment_data["currency"]

    async def test_payment_creation_idempotency(self, api_client):
        """
        Test 2: Verify duplicate requests return same payment

        CRITICAL: Prevents double charges when customers retry.
        """
        # Arrange
        idempotency_key = "idempotent-test-key-123"
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=idempotency_key
        )

        # Act: Create payment twice with same key
        response1 = await api_client.post("/payments", json=payment_data)
        response2 = await api_client.post("/payments", json=payment_data)

        # Assert: Same payment returned
        assert response1.status_code == 201
        assert response2.status_code == 200  # Not 201 (not created)

        payment1 = response1.json()
        payment2 = response2.json()

        assert payment1["payment_id"] == payment2["payment_id"]
        assert payment1["status"] == payment2["status"]

    async def test_invalid_payment_method_rejected(self, api_client):
        """
        Test 3: Verify invalid payment methods return 400

        Input validation test.
        """
        # Arrange
        invalid_data = PaymentFactory.create_payment_request(
            payment_method="INVALID_METHOD"
        )

        # Act
        response = await api_client.post("/payments", json=invalid_data)

        # Assert
        assert response.status_code == 422  # Validation error
        error_data = response.json()
        assert "detail" in error_data

    async def test_get_payment_status(self, api_client, unique_idempotency_key):
        """
        Test 4: Verify payment status can be retrieved

        Basic API test for GET endpoint.
        """
        # Arrange: Create a payment first
        payment_data = PaymentFactory.create_pse_payment(
            idempotency_key=unique_idempotency_key
        )
        create_response = await api_client.post("/payments", json=payment_data)
        payment_id = create_response.json()["payment_id"]

        # Act: Get payment status
        response = await api_client.get(f"/payments/{payment_id}")

        # Assert
        assert response.status_code == 200
        payment = response.json()
        assert payment["payment_id"] == payment_id
        assert payment["status"] == "pending"

    async def test_get_nonexistent_payment_returns_404(self, api_client):
        """
        Test 5: Verify 404 for nonexistent payment

        Error handling test.
        """
        # Act
        response = await api_client.get("/payments/nonexistent_id_12345")

        # Assert
        assert response.status_code == 404
