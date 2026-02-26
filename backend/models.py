"""Payment models and data structures"""
from datetime import datetime
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field
import uuid


class PaymentStatus(str, Enum):
    """Payment status states"""
    PENDING = "pending"
    APPROVED = "approved"
    DECLINED = "declined"
    EXPIRED = "expired"
    PROCESSING = "processing"


class PaymentMethod(str, Enum):
    """Supported payment methods"""
    PSE = "PSE"
    PIX = "PIX"
    OXXO = "OXXO"
    CARD = "CARD"


class CustomerData(BaseModel):
    """Customer information"""
    email: str
    name: str
    document: str


class PaymentRequest(BaseModel):
    """Request to create a payment"""
    amount: str = Field(..., description="Payment amount in cents")
    currency: str = Field(..., description="ISO currency code")
    payment_method: PaymentMethod
    bank: Optional[str] = None
    customer: CustomerData
    redirect_url: str
    idempotency_key: str = Field(default_factory=lambda: str(uuid.uuid4()))


class Payment(BaseModel):
    """Payment entity"""
    payment_id: str = Field(default_factory=lambda: f"pay_{uuid.uuid4().hex[:16]}")
    status: PaymentStatus = PaymentStatus.PENDING
    amount: str
    currency: str
    payment_method: PaymentMethod
    bank: Optional[str] = None
    customer: CustomerData
    redirect_url: str
    idempotency_key: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    webhook_count: int = 0  # Track duplicate webhooks

    class Config:
        use_enum_values = True


class WebhookPayload(BaseModel):
    """Webhook notification from payment provider"""
    payment_id: str
    status: PaymentStatus
    timestamp: str
    signature: Optional[str] = None
    reason: Optional[str] = None  # For declined/failed payments


class PaymentResponse(BaseModel):
    """Response after creating payment"""
    payment_id: str
    status: PaymentStatus
    redirect_url: Optional[str] = None
    amount: str
    currency: str
    created_at: datetime
