"""Payment data factory for test data generation"""
import uuid
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from faker import Faker

fake = Faker(['es_CO', 'es_MX', 'pt_BR'])


class PaymentFactory:
    """Factory for generating test payment data"""

    @staticmethod
    def create_payment_request(
        amount: str = "50000",
        currency: str = "COP",
        payment_method: str = "PSE",
        bank: str = "banco_azul",
        idempotency_key: Optional[str] = None,
        **overrides
    ) -> Dict[str, Any]:
        """Generate a valid payment request"""

        defaults = {
            "amount": amount,
            "currency": currency,
            "payment_method": payment_method,
            "bank": bank,
            "customer": {
                "email": fake.email(),
                "name": fake.name(),
                "document": fake.numerify(text="##########")
            },
            "redirect_url": "http://localhost:3000/return",
            "idempotency_key": idempotency_key or str(uuid.uuid4())
        }

        return {**defaults, **overrides}

    @staticmethod
    def create_pse_payment(**overrides) -> Dict[str, Any]:
        """Generate PSE-specific payment"""
        return PaymentFactory.create_payment_request(
            payment_method="PSE",
            currency="COP",
            bank="banco_azul",
            **overrides
        )

    @staticmethod
    def create_pix_payment(**overrides) -> Dict[str, Any]:
        """Generate PIX-specific payment"""
        return PaymentFactory.create_payment_request(
            payment_method="PIX",
            currency="BRL",
            bank=None,  # PIX doesn't require bank selection
            **overrides
        )

    @staticmethod
    def create_oxxo_payment(**overrides) -> Dict[str, Any]:
        """Generate OXXO-specific payment"""
        return PaymentFactory.create_payment_request(
            payment_method="OXXO",
            currency="MXN",
            bank=None,
            **overrides
        )


class WebhookFactory:
    """Factory for generating test webhook payloads"""

    @staticmethod
    def create_webhook(
        payment_id: str,
        status: str = "approved",
        timestamp: Optional[str] = None,
        signature: str = "mock_signature",
        **overrides
    ) -> Dict[str, Any]:
        """Generate a valid webhook payload"""

        defaults = {
            "payment_id": payment_id,
            "status": status,
            "timestamp": timestamp or datetime.utcnow().isoformat() + "Z",
            "signature": signature
        }

        return {**defaults, **overrides}

    @staticmethod
    def create_approved_webhook(payment_id: str, **overrides) -> Dict[str, Any]:
        """Generate approved webhook"""
        return WebhookFactory.create_webhook(
            payment_id=payment_id,
            status="approved",
            **overrides
        )

    @staticmethod
    def create_declined_webhook(payment_id: str, **overrides) -> Dict[str, Any]:
        """Generate declined webhook"""
        return WebhookFactory.create_webhook(
            payment_id=payment_id,
            status="declined",
            reason="insufficient_funds",
            **overrides
        )

    @staticmethod
    def create_expired_webhook(payment_id: str, **overrides) -> Dict[str, Any]:
        """Generate expired webhook"""
        return WebhookFactory.create_webhook(
            payment_id=payment_id,
            status="expired",
            **overrides
        )

    @staticmethod
    def create_delayed_webhook(
        payment_id: str,
        delay_seconds: int = 5,
        **overrides
    ) -> Dict[str, Any]:
        """Generate webhook with future timestamp"""
        future_time = datetime.utcnow() + timedelta(seconds=delay_seconds)
        return WebhookFactory.create_webhook(
            payment_id=payment_id,
            timestamp=future_time.isoformat() + "Z",
            **overrides
        )

    @staticmethod
    def create_old_webhook(
        payment_id: str,
        age_seconds: int = 60,
        **overrides
    ) -> Dict[str, Any]:
        """Generate webhook with past timestamp"""
        past_time = datetime.utcnow() - timedelta(seconds=age_seconds)
        return WebhookFactory.create_webhook(
            payment_id=payment_id,
            timestamp=past_time.isoformat() + "Z",
            **overrides
        )
