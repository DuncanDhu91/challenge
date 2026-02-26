"""FastAPI Payment API"""
import asyncio
from datetime import datetime
from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Optional
import uvicorn

from models import (
    Payment,
    PaymentRequest,
    PaymentResponse,
    PaymentStatus,
    WebhookPayload
)

app = FastAPI(title="Banco Azul Payment API", version="1.0.0")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (use database in production)
payments: Dict[str, Payment] = {}
idempotency_cache: Dict[str, str] = {}  # idempotency_key -> payment_id


@app.get("/")
async def root():
    return {"message": "Banco Azul Payment API", "version": "1.0.0"}


@app.post("/payments", response_model=PaymentResponse, status_code=201)
async def create_payment(
    request: PaymentRequest,
    idempotency_key: Optional[str] = Header(None)
):
    """Create a new payment"""

    # Use header idempotency key if provided, otherwise from body
    key = idempotency_key or request.idempotency_key

    # Check idempotency
    if key in idempotency_cache:
        existing_payment_id = idempotency_cache[key]
        existing_payment = payments[existing_payment_id]
        return PaymentResponse(
            payment_id=existing_payment.payment_id,
            status=existing_payment.status,
            redirect_url=f"https://banco-azul.example.com/pay/{existing_payment.payment_id}",
            amount=existing_payment.amount,
            currency=existing_payment.currency,
            created_at=existing_payment.created_at
        )

    # Create new payment
    payment = Payment(
        amount=request.amount,
        currency=request.currency,
        payment_method=request.payment_method,
        bank=request.bank,
        customer=request.customer,
        redirect_url=request.redirect_url,
        idempotency_key=key
    )

    # Store payment
    payments[payment.payment_id] = payment
    idempotency_cache[key] = payment.payment_id

    # Generate redirect URL (mock bank portal)
    redirect_url = f"https://banco-azul.example.com/pay/{payment.payment_id}"

    return PaymentResponse(
        payment_id=payment.payment_id,
        status=payment.status,
        redirect_url=redirect_url,
        amount=payment.amount,
        currency=payment.currency,
        created_at=payment.created_at
    )


@app.get("/payments/{payment_id}", response_model=Payment)
async def get_payment(payment_id: str):
    """Get payment status"""
    if payment_id not in payments:
        raise HTTPException(status_code=404, detail="Payment not found")

    return payments[payment_id]


@app.post("/webhooks")
async def receive_webhook(webhook: WebhookPayload):
    """Receive webhook from payment provider"""

    payment_id = webhook.payment_id

    if payment_id not in payments:
        raise HTTPException(status_code=404, detail="Payment not found")

    payment = payments[payment_id]

    # Idempotency: Check if this exact webhook was already processed
    # In production, store webhook IDs or use timestamp + signature
    if payment.status == webhook.status and payment.webhook_count > 0:
        # Already processed this status update
        return {"message": "Webhook already processed", "idempotent": True}

    # Timestamp-based ordering: newer webhooks win
    webhook_time = datetime.fromisoformat(webhook.timestamp.replace('Z', '+00:00'))

    if webhook_time < payment.updated_at:
        # This is an older webhook, ignore it
        return {
            "message": "Webhook ignored (older than current state)",
            "out_of_order": True
        }

    # Update payment status
    payment.status = webhook.status
    payment.updated_at = webhook_time
    payment.webhook_count += 1

    payments[payment_id] = payment

    return {
        "message": "Webhook processed",
        "payment_id": payment_id,
        "new_status": payment.status
    }


@app.delete("/payments/{payment_id}")
async def delete_payment(payment_id: str):
    """Delete payment (for test cleanup)"""
    if payment_id in payments:
        payment = payments.pop(payment_id)
        # Remove from idempotency cache
        if payment.idempotency_key in idempotency_cache:
            idempotency_cache.pop(payment.idempotency_key)
        return {"message": "Payment deleted"}

    raise HTTPException(status_code=404, detail="Payment not found")


@app.delete("/payments")
async def delete_all_payments():
    """Delete all payments (for test cleanup)"""
    payments.clear()
    idempotency_cache.clear()
    return {"message": "All payments deleted"}


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "payments_count": len(payments)}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
