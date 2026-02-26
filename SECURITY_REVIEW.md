# Security Review & Risk Analysis

**Reviewer**: Devil's Advocate (Security Architect)
**Date**: 2024-01-15
**Project**: Banco Azul E2E Test Suite
**Review Time**: 10 minutes

---

## 🔴 CRITICAL RISKS IDENTIFIED

### Risk 1: Race Conditions - CRITICAL 🔴

**Scenario**: Webhook arrives before/after customer redirect return

**Attack Vector**: Not directly exploitable, but creates customer confusion that attackers can leverage (social engineering, fake payment confirmations).

**Impact**:
- Customer sees "payment pending" after paying → retries → double charge
- Customer abandons cart thinking payment failed → inventory locked
- Support tickets expose payment details over phone

**Mitigation Status**: ✅ **FIXED**
- Test #7: Webhook before redirect
- Test #8: Redirect before webhook
- Frontend shows "processing" state during delay

**Code Fix**:
```python
# Webhook processor uses timestamp ordering
if webhook_time < payment.updated_at:
    return {"message": "Webhook ignored (older)", "out_of_order": True}
```

**Remaining Risk**: LOW (mitigated)

---

### Risk 2: Idempotency Violations - CRITICAL 🔴

**Scenario**: Duplicate webhooks cause double charges

**Attack Vector**: Malicious actor replays valid webhook to approve payment multiple times.

**Impact**:
- Customer charged twice for same purchase
- Financial loss for merchant/customer
- Chargeback fees
- Regulatory compliance issues (PCI-DSS)

**Mitigation Status**: ✅ **FIXED**
- Test #2: Payment creation idempotency
- Test #9: Duplicate webhook idempotency
- API maintains idempotency cache

**Code Fix**:
```python
# Payment creation
if idempotency_key in cache:
    return existing_payment  # Don't create duplicate

# Webhook processing
if payment.status == webhook.status and payment.webhook_count > 0:
    return {"idempotent": True}  # Already processed
```

**Remaining Risk**: MEDIUM
- ⚠️ Idempotency cache is in-memory (lost on restart)
- ⚠️ No expiration (grows unbounded)

**Recommended Fix**:
```python
# Use database with TTL
idempotency_keys = {
    key: (payment_id, expires_at)
}
# Expire after 24 hours
```

---

### Risk 3: Out-of-Order Webhook Delivery - HIGH 🟡

**Scenario**: "expired" webhook arrives after "approved" webhook

**Attack Vector**: Malicious provider sends delayed "declined" webhook to cancel approved payment after fulfillment.

**Impact**:
- Approved payments incorrectly marked as failed
- Order already shipped but payment reverted
- Merchant loses goods + money

**Mitigation Status**: ✅ **FIXED**
- Test #10: Out-of-order webhook handling
- Timestamp-based ordering (newer wins)

**Code Fix**:
```python
webhook_time = datetime.fromisoformat(webhook.timestamp)

if webhook_time < payment.updated_at:
    # Ignore older webhooks
    return {"out_of_order": True}
```

**Remaining Risk**: LOW (mitigated)

---

### Risk 4: Webhook Signature Validation - HIGH 🟡

**Scenario**: Malicious webhook spoofing

**Attack Vector**: Attacker sends fake "approved" webhook without actual payment.

**Impact**:
- Unauthorized order fulfillment
- Fraud
- Financial loss

**Mitigation Status**: ⏸️ **NOT IMPLEMENTED** (P2 - deferred due to time)

**Recommended Fix**:
```python
import hmac
import hashlib

def validate_webhook_signature(payload: dict, signature: str) -> bool:
    expected = hmac.new(
        key=WEBHOOK_SECRET.encode(),
        msg=json.dumps(payload, sort_keys=True).encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    if not hmac.compare_digest(expected, signature):
        raise HTTPException(403, "Invalid webhook signature")

    return True

# In webhook endpoint
@app.post("/webhooks")
async def receive_webhook(webhook: WebhookPayload):
    validate_webhook_signature(webhook.dict(), webhook.signature)
    # ... process webhook
```

**Remaining Risk**: HIGH (not implemented)
**Priority**: Implement before production

---

### Risk 5: Webhook Endpoint DOS - MEDIUM 🟢

**Scenario**: Attacker floods webhook endpoint with requests

**Attack Vector**: Send thousands of fake webhooks to exhaust server resources.

**Impact**:
- Legitimate webhooks delayed/dropped
- Server crash
- Payment inconsistencies

**Mitigation Status**: ⏸️ **NOT IMPLEMENTED**

**Recommended Fix**:
```python
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

@app.post("/webhooks")
@limiter.limit("100/minute")  # Per IP rate limit
async def receive_webhook(webhook: WebhookPayload):
    # ... process
```

**Remaining Risk**: MEDIUM
**Priority**: Implement before scaling

---

## 🟡 HIGH PRIORITY RISKS

### Risk 6: SQL Injection (if using database)

**Status**: ⏸️ NOT APPLICABLE (in-memory storage)

**For Production**:
```python
# ❌ Bad
query = f"SELECT * FROM payments WHERE id = '{payment_id}'"

# ✅ Good
query = "SELECT * FROM payments WHERE id = ?"
cursor.execute(query, (payment_id,))
```

---

### Risk 7: Sensitive Data Exposure

**Concern**: Payment details logged or exposed in error messages

**Current State**:
- ✅ No credit card numbers stored
- ⚠️ Customer emails/documents in logs

**Recommended Fix**:
```python
# Mask sensitive data in logs
logger.info(f"Payment created: {payment_id}, email: {mask_email(email)}")

def mask_email(email):
    user, domain = email.split('@')
    return f"{user[:2]}***@{domain}"
```

---

## 🟢 MEDIUM PRIORITY RISKS

### Risk 8: CORS Misconfiguration

**Current State**:
```python
allow_origins=["*"]  # ⚠️ Too permissive
```

**Recommended Fix**:
```python
allow_origins=[
    "https://yourdomain.com",
    "https://vercel-preview-*.vercel.app"
]
```

---

### Risk 9: No Request Timeout

**Concern**: Slow webhook processing blocks other requests

**Recommended Fix**:
```python
@app.post("/webhooks")
async def receive_webhook(webhook: WebhookPayload):
    async with timeout(5.0):  # 5-second timeout
        # ... process webhook
```

---

## 📊 Risk Summary Matrix

| Risk | Severity | Likelihood | Status | Priority |
|------|----------|------------|--------|----------|
| Race conditions | Critical | High | ✅ Fixed | P0 |
| Idempotency violations | Critical | High | ✅ Fixed | P0 |
| Out-of-order webhooks | High | Medium | ✅ Fixed | P1 |
| Webhook signature validation | Critical | Low | ⏸️ Deferred | P2 |
| DOS attack | Medium | Medium | ⏸️ Deferred | P3 |
| SQL injection | High | N/A | N/A | N/A |
| Sensitive data exposure | Medium | Low | ⚠️ Partial | P3 |
| CORS misconfiguration | Medium | Low | ⚠️ Present | P3 |
| No timeouts | Low | Medium | ⏸️ Deferred | P4 |

---

## ✅ SECURITY FIXES APPLIED

### 1. Timestamp-Based Ordering
```python
if webhook_time < payment.updated_at:
    # Reject older webhooks
```

**Prevents**: Out-of-order webhook attacks

### 2. Idempotency Keys
```python
if idempotency_key in cache:
    return existing_payment
```

**Prevents**: Duplicate payments, double charges

### 3. Webhook Count Tracking
```python
payment.webhook_count += 1
if payment.webhook_count > 1:
    # Log potential replay attack
```

**Detects**: Duplicate webhook delivery attempts

---

## 🚨 PRODUCTION BLOCKERS

**MUST IMPLEMENT before production**:

1. ❌ **Webhook signature validation** (Risk #4)
   - CRITICAL: Prevents fraud
   - Implementation time: ~30 minutes
   - Test coverage: 1 additional test

2. ❌ **Rate limiting** (Risk #5)
   - HIGH: Prevents DOS
   - Implementation time: ~15 minutes
   - Test coverage: 1 load test

3. ❌ **Persistent idempotency cache** (Risk #2 mitigation)
   - HIGH: Survives restarts
   - Implementation time: ~20 minutes
   - Use database with TTL

4. ❌ **CORS whitelist** (Risk #8)
   - MEDIUM: Hardens API
   - Implementation time: ~5 minutes

---

## 📋 SECURITY TESTING GAPS

**Not covered in current suite**:

1. **Signature tampering**: Modify webhook signature
2. **Replay attacks**: Send old valid webhooks
3. **Timing attacks**: Infer payment status from response time
4. **Rate limit bypass**: Test header manipulation
5. **SQL injection**: If database added
6. **XSS in customer data**: If data reflected in UI

**Recommended**: Add security test suite (estimated 2-3 hours)

---

## 🎯 SECURITY CHECKLIST FOR PRODUCTION

### Before Launch

- [ ] Implement webhook signature validation
- [ ] Add rate limiting (100 req/min per IP)
- [ ] Use persistent idempotency cache (database)
- [ ] Whitelist CORS origins
- [ ] Add request timeouts (5s for webhooks)
- [ ] Mask sensitive data in logs
- [ ] Enable HTTPS only
- [ ] Set up monitoring/alerts for:
  - [ ] Failed signature validations
  - [ ] High duplicate webhook rate
  - [ ] Out-of-order webhook frequency
- [ ] Conduct penetration testing
- [ ] Review PCI-DSS compliance (if storing card data)

---

## 💡 QUICK WINS (< 30 min each)

1. **Add webhook signature validation** (25 min)
   - Highest security impact
   - Prevents fraud

2. **Implement rate limiting** (15 min)
   - Prevents DOS
   - Easy with slowapi library

3. **Fix CORS** (5 min)
   - One-line config change
   - Hardens API immediately

---

## 🔍 MONITORING RECOMMENDATIONS

**Set up alerts for**:

```python
# Alert: High duplicate webhook rate
if payment.webhook_count > 3:
    alert("Possible replay attack", payment_id)

# Alert: Signature validation failures
if signature_invalid:
    alert("Potential fraud attempt", ip_address)

# Alert: Out-of-order webhooks
if webhook_time < payment.updated_at:
    alert("Out-of-order webhook", payment_id)
```

---

## 📝 CONCLUSION

**Current Security Posture**: MODERATE

**Strengths**:
- ✅ Race conditions handled
- ✅ Idempotency implemented
- ✅ Out-of-order webhooks rejected
- ✅ Test coverage for critical paths

**Weaknesses**:
- ⚠️ No webhook signature validation (CRITICAL GAP)
- ⚠️ No rate limiting
- ⚠️ In-memory idempotency cache (not persistent)
- ⚠️ Permissive CORS

**Recommendation**: Implement 4 production blockers (estimated 70 minutes) before launch.

**Overall Risk**: MEDIUM (acceptable for MVP, NOT for production)

---

**Review Version**: 1.0
**Reviewed By**: Devil's Advocate
**Status**: Findings documented, mitigations prioritized
