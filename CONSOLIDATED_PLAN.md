# Plan Consolidado: Banco Azul E2E Test Suite

**Feature**: The Async Payment Chaos - E2E Tests for Async Payment Flows
**Time Budget**: 60 minutes total
**Team**: QA Automation Expert, Backend Engineers 1 & 2, Devil's Advocate

---

## Executive Summary

**Problem**: 40% of Banco Azul (PSE) webhook failures causing payment status inconsistencies, double charges, and merchant escalation.

**Root Cause**: Zero E2E test coverage for async payment methods (PSE, PIX, OXXO).

**Solution**: Build comprehensive E2E test suite covering webhook timing issues, idempotency, and async flow edge cases, backed by a deployable demo UI on Vercel.

**Deliverable**: Production-ready test framework with 7-10 critical tests in 60 minutes.

---

## 🔴 CRITICAL RISKS (Devil's Advocate Analysis)

### Risk 1: Race Conditions - CRITICAL 🔴
**Scenario**: Webhook arrives before/after redirect return
- Customer returns to merchant → payment still "pending"
- Webhook arrives 30s later → status updates but customer already left
- **Impact**: Customer confusion, abandoned carts, support tickets
- **Test Priority**: #1 (must have)

### Risk 2: Idempotency Violations - CRITICAL 🔴
**Scenario**: Duplicate webhooks cause double charges
- Same webhook delivered 2-3 times (common in network issues)
- Without idempotency: payment processed multiple times
- **Impact**: Financial loss, chargebacks, merchant churn
- **Test Priority**: #1 (must have)

### Risk 3: Out-of-Order Webhook Delivery - HIGH 🟡
**Scenario**: "expired" webhook arrives after "approved" webhook
- Payment marked approved → expired webhook arrives → status reverts
- **Impact**: Approved payments incorrectly marked as failed
- **Test Priority**: #2 (should have)

### Risk 4: Webhook Signature Validation - HIGH 🟡
**Scenario**: Malicious webhook spoofing
- Attacker sends fake "approved" webhook without payment
- **Impact**: Fraud, unauthorized order fulfillment
- **Test Priority**: #2 (should have)

### Risk 5: Timeout/Expiration Edge Cases - MEDIUM 🟢
**Scenario**: Payment expires during processing
- 15-min PSE timeout hits while customer at bank portal
- **Impact**: False negatives, customer frustration
- **Test Priority**: #3 (nice to have)

---

## 🎯 TEST STRATEGY (QA Automation Expert)

### Test Pyramid Distribution

```
        E2E (10%)
       /        \
      /  UI E2E  \     ← 2-3 tests (Playwright)
     /────────────\
    / Integration  \   ← 5-7 tests (API + Webhook)
   /    (60%)       \
  /──────────────────\
 /   Unit Tests       \ ← Deferred (out of scope)
/       (30%)          \
────────────────────────
```

**Focus**: Integration layer (API + Webhook simulation)
**Rationale**: 60-min constraint demands maximum ROI. Integration tests catch webhook issues without UI flakiness.

### Framework Selection

**Backend/API Tests**:
- **Framework**: pytest + httpx (Python)
- **Why**: Fast test development, excellent async support, familiar to most teams
- **Alternative considered**: Jest + Supertest (Node) - rejected due to webhook simulation complexity

**UI Tests** (minimal):
- **Framework**: Playwright (TypeScript)
- **Why**: Best-in-class async handling, auto-waiting, Vercel-friendly
- **Scope**: 2 smoke tests only (happy path + webhook delay scenario)

**Webhook Simulation**:
- **Approach**: Mock webhook server (FastAPI or Express)
- **Why**: Full control over timing, order, duplicates without real provider dependency

### Coverage Priorities (60-minute scope)

| Priority | Scenario | Tests | Time |
|----------|----------|-------|------|
| **P0** | Happy path + idempotency | 2 | 10 min |
| **P0** | Race condition (webhook before/after redirect) | 2 | 10 min |
| **P0** | Duplicate webhook handling | 1 | 5 min |
| **P1** | Out-of-order webhooks | 1 | 5 min |
| **P1** | Payment declined/expired | 2 | 8 min |
| **P2** | Invalid webhook signature | 1 | 5 min |
| **Deferred** | Load testing, multi-method coverage | - | - |

**Total**: 7-9 tests in ~43 minutes (leaves 17 min for setup + docs)

---

## 🧪 TEST SCENARIOS (Backend Engineers 1 & 2)

### Backend Engineer 1: Synchronous API Tests (25 min)

#### Test 1: Payment Creation - Happy Path
```python
def test_pse_payment_creation():
    """Verify PSE payment initializes correctly"""
    # Arrange
    payment_data = {
        "amount": "50000",
        "currency": "COP",
        "payment_method": "PSE",
        "bank": "banco_azul",
        "customer": {...}
    }

    # Act
    response = api.create_payment(payment_data, idempotency_key="test-123")

    # Assert
    assert response.status_code == 201
    assert response.json["status"] == "pending"
    assert response.json["redirect_url"] is not None
    assert "payment_id" in response.json
```

#### Test 2: Idempotency - Duplicate Creation
```python
def test_payment_creation_idempotency():
    """Verify duplicate requests return same payment"""
    # Arrange
    key = "idempotent-key-456"

    # Act
    payment1 = api.create_payment({...}, idempotency_key=key)
    payment2 = api.create_payment({...}, idempotency_key=key)

    # Assert
    assert payment1.json["payment_id"] == payment2.json["payment_id"]
    assert payment2.status_code == 200  # Not 201
```

#### Test 3: Payment Status Validation
```python
def test_payment_status_transitions():
    """Verify only valid status transitions allowed"""
    # Arrange
    payment = create_payment()

    # Act & Assert
    assert can_transition(payment, "pending" -> "approved")  # Valid
    assert not can_transition(payment, "approved" -> "pending")  # Invalid
    assert can_transition(payment, "pending" -> "expired")  # Valid
```

#### Test 4: Invalid Payment Method
```python
def test_invalid_payment_method_rejected():
    """Verify invalid payment methods return 400"""
    # Act
    response = api.create_payment({"payment_method": "INVALID"})

    # Assert
    assert response.status_code == 400
    assert "invalid payment method" in response.json["error"]
```

---

### Backend Engineer 2: Async/Webhook Tests (25 min)

#### Test 5: Webhook Updates Payment Status
```python
async def test_webhook_updates_payment_to_approved():
    """Verify webhook correctly updates payment status"""
    # Arrange
    payment = await create_payment(status="pending")

    # Act
    webhook_payload = {
        "payment_id": payment.id,
        "status": "approved",
        "timestamp": "2024-01-15T10:30:00Z"
    }
    await send_webhook(webhook_payload)

    # Wait for async processing
    await asyncio.sleep(2)

    # Assert
    updated = await get_payment(payment.id)
    assert updated["status"] == "approved"
```

#### Test 6: Race Condition - Webhook Before Redirect
```python
async def test_webhook_arrives_before_customer_returns():
    """Webhook arrives while customer still at bank"""
    # Arrange
    payment = await create_payment()

    # Act: Webhook arrives first
    await send_webhook({"payment_id": payment.id, "status": "approved"})
    await asyncio.sleep(1)

    # Customer returns after
    redirect_response = await customer_returns_from_bank(payment.id)

    # Assert
    assert redirect_response.status == "approved"  # Shows correct status
    assert redirect_response.message == "Payment successful"
```

#### Test 7: Race Condition - Redirect Before Webhook
```python
async def test_customer_returns_before_webhook():
    """Customer returns but webhook delayed"""
    # Arrange
    payment = await create_payment()

    # Act: Customer returns first
    redirect_response = await customer_returns_from_bank(payment.id)

    # Assert: Should show "processing" state
    assert redirect_response.status == "pending"
    assert "processing" in redirect_response.message.lower()

    # Webhook arrives 5 seconds later
    await asyncio.sleep(5)
    await send_webhook({"payment_id": payment.id, "status": "approved"})

    # Final status should be approved
    final = await get_payment(payment.id)
    assert final["status"] == "approved"
```

#### Test 8: Duplicate Webhook Idempotency
```python
async def test_duplicate_webhook_ignored():
    """Same webhook delivered multiple times"""
    # Arrange
    payment = await create_payment()
    webhook = {"payment_id": payment.id, "status": "approved"}

    # Act: Send same webhook 3 times
    await send_webhook(webhook)
    await send_webhook(webhook)
    await send_webhook(webhook)

    # Assert: Payment updated only once
    payment_data = await get_payment(payment.id)
    assert payment_data["status"] == "approved"
    assert payment_data["update_count"] == 1  # Not 3
```

#### Test 9: Out-of-Order Webhooks
```python
async def test_out_of_order_webhooks():
    """Expired webhook arrives after approved webhook"""
    # Arrange
    payment = await create_payment()

    # Act: Approved webhook arrives first
    await send_webhook({
        "payment_id": payment.id,
        "status": "approved",
        "timestamp": "2024-01-15T10:31:00Z"
    })

    # Expired webhook arrives later (older timestamp)
    await send_webhook({
        "payment_id": payment.id,
        "status": "expired",
        "timestamp": "2024-01-15T10:30:00Z"  # Older
    })

    # Assert: Status should remain "approved" (newer timestamp wins)
    final = await get_payment(payment.id)
    assert final["status"] == "approved"
```

#### Test 10: Declined Payment Webhook
```python
async def test_declined_payment_webhook():
    """Bank declines payment"""
    # Arrange
    payment = await create_payment()

    # Act
    await send_webhook({
        "payment_id": payment.id,
        "status": "declined",
        "reason": "insufficient_funds"
    })

    # Assert
    updated = await get_payment(payment.id)
    assert updated["status"] == "declined"
    assert updated["reason"] == "insufficient_funds"
```

---

## 🏗️ SYSTEM ARCHITECTURE

### Components

```
┌─────────────────────────────────────────────────────────┐
│                    TEST SYSTEM                          │
├─────────────────────────────────────────────────────────┤
│                                                         │
│  ┌─────────────┐      ┌──────────────┐               │
│  │   UI Tests  │──────│  Playwright  │               │
│  │  (2 tests)  │      │   Browser    │               │
│  └─────────────┘      └──────────────┘               │
│         │                                              │
│         ▼                                              │
│  ┌─────────────────────────────────────┐             │
│  │      Next.js Frontend (Vercel)      │             │
│  │  - Payment checkout page            │             │
│  │  - Status display                   │             │
│  │  - Webhook status indicator         │             │
│  └─────────────────────────────────────┘             │
│         │                                              │
│         ▼                                              │
│  ┌─────────────────────────────────────┐             │
│  │     Payment API (FastAPI/Express)   │             │
│  │  - POST /payments (create)          │             │
│  │  - GET /payments/:id (status)       │             │
│  │  - POST /webhooks (receiver)        │             │
│  └─────────────────────────────────────┘             │
│         │                                              │
│         ▼                                              │
│  ┌─────────────────────────────────────┐             │
│  │      Mock Webhook Server            │             │
│  │  - Simulates Banco Azul             │             │
│  │  - Controllable delays/order        │             │
│  │  - Duplicate delivery               │             │
│  └─────────────────────────────────────┘             │
│                                                         │
└─────────────────────────────────────────────────────────┘
```

### Tech Stack

**Frontend (Vercel)**:
- Next.js 14 (App Router)
- TypeScript
- Tailwind CSS
- React Query (status polling)

**Backend API**:
- FastAPI (Python) or Express (Node)
- SQLite (test database)
- Pydantic/Zod (validation)

**Tests**:
- pytest + httpx (API tests)
- Playwright (UI tests)
- pytest-asyncio (async support)

**CI/CD**:
- GitHub Actions
- Vercel auto-deploy
- Test reports: pytest-html

---

## 📋 TEST DATA STRATEGY

### Payment Factory Pattern

```python
class PaymentFactory:
    @staticmethod
    def create_pse_payment(**overrides):
        """Generate valid PSE payment data"""
        defaults = {
            "amount": "50000",
            "currency": "COP",
            "payment_method": "PSE",
            "bank": "banco_azul",
            "customer": {
                "email": "test@example.com",
                "name": "Juan Test",
                "document": "123456789"
            },
            "redirect_url": "http://localhost:3000/return"
        }
        return {**defaults, **overrides}

    @staticmethod
    def create_webhook(**overrides):
        """Generate valid webhook payload"""
        defaults = {
            "payment_id": str(uuid.uuid4()),
            "status": "approved",
            "timestamp": datetime.utcnow().isoformat(),
            "signature": "mock_signature_12345"
        }
        return {**defaults, **overrides}
```

### Test Isolation

- Each test uses unique `idempotency_key` (UUID)
- Tests create/cleanup own payment records
- No shared state between tests
- Parallel execution safe

---

## ⏱️ ASYNC HANDLING STRATEGY

### Challenge
Webhooks are asynchronous. Tests need to wait for processing without arbitrary sleeps (flaky tests).

### Solution: Smart Polling

```python
async def wait_for_payment_status(
    payment_id: str,
    expected_status: str,
    timeout: int = 10,
    poll_interval: float = 0.5
):
    """Poll payment status until expected or timeout"""
    start = time.time()

    while time.time() - start < timeout:
        payment = await get_payment(payment_id)
        if payment["status"] == expected_status:
            return payment
        await asyncio.sleep(poll_interval)

    raise TimeoutError(
        f"Payment {payment_id} did not reach {expected_status} "
        f"within {timeout}s"
    )

# Usage in test
await send_webhook({...})
payment = await wait_for_payment_status(payment_id, "approved", timeout=5)
assert payment["status"] == "approved"
```

**Benefits**:
- No arbitrary sleeps
- Fast when webhook processes quickly
- Clear timeout errors
- Configurable per test

---

## 🚀 CI/CD PIPELINE

### GitHub Actions Workflow

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v3

      - name: Setup Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install -r requirements.txt
          playwright install

      - name: Start mock services
        run: |
          python mock_webhook_server.py &
          python payment_api.py &
          sleep 5

      - name: Run API tests
        run: pytest tests/api/ -v --html=report.html

      - name: Run E2E tests
        run: pytest tests/e2e/ -v

      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v3
        with:
          name: test-report
          path: report.html

      - name: Deploy to Vercel (on main)
        if: github.ref == 'refs/heads/main'
        run: vercel --prod --token=${{ secrets.VERCEL_TOKEN }}
```

### Test Execution

```bash
# Local execution
pytest tests/ -v -s

# With coverage
pytest tests/ --cov=src --cov-report=html

# Parallel execution
pytest tests/ -n 4

# Watch mode (development)
pytest-watch tests/
```

---

## 📦 DELIVERABLES & DEFINITION OF DONE

### Repository Structure

```
banco-azul-e2e/
├── frontend/               # Next.js UI (Vercel)
│   ├── app/
│   │   ├── page.tsx       # Checkout page
│   │   ├── return/page.tsx # Return handler
│   │   └── api/
│   ├── components/
│   └── package.json
├── backend/               # Payment API
│   ├── main.py           # FastAPI app
│   ├── models.py         # Payment models
│   └── webhooks.py       # Webhook handler
├── tests/
│   ├── api/
│   │   ├── test_payment_creation.py
│   │   ├── test_idempotency.py
│   │   └── test_validation.py
│   ├── webhooks/
│   │   ├── test_webhook_processing.py
│   │   ├── test_race_conditions.py
│   │   ├── test_duplicates.py
│   │   └── test_out_of_order.py
│   ├── e2e/
│   │   ├── test_checkout_flow.py
│   │   └── test_async_status.py
│   ├── fixtures/
│   │   ├── payment_factory.py
│   │   └── webhook_factory.py
│   └── conftest.py       # pytest config
├── mock_webhook_server.py # Banco Azul simulator
├── .github/
│   └── workflows/
│       └── test.yml      # CI pipeline
├── pytest.ini
├── requirements.txt
├── README.md
└── TEST_STRATEGY.md      # This document
```

### Definition of Done Checklist

#### Code
- [ ] 7-10 tests written and passing
- [ ] All P0 scenarios covered (happy path, idempotency, race conditions)
- [ ] Payment factory implemented
- [ ] Webhook simulator functional
- [ ] API client wrapper created
- [ ] Smart polling utility implemented

#### UI
- [ ] Next.js checkout page deployed to Vercel
- [ ] Payment status display with real-time updates
- [ ] "Processing payment..." state for webhook delays
- [ ] Success/failure confirmation screens

#### Tests Pass
- [ ] All tests pass locally
- [ ] All tests pass in CI
- [ ] No flaky tests (run 3x to verify)
- [ ] Test execution < 2 minutes

#### Documentation
- [ ] README with setup instructions
- [ ] TEST_STRATEGY.md (this document)
- [ ] Inline code comments for complex logic
- [ ] Swagger/OpenAPI docs for API endpoints

#### CI/CD
- [ ] GitHub Actions workflow functional
- [ ] Test reports generated
- [ ] Vercel auto-deploy configured
- [ ] All status checks green

#### Git History
- [ ] 12-15 incremental commits
- [ ] Conventional commit messages
- [ ] Co-Authored-By tags
- [ ] All changes pushed

---

## 🎯 SUCCESS METRICS

### Test Coverage Target
- **API Endpoints**: 80% (4/5 endpoints)
- **Webhook Scenarios**: 100% (all P0 + P1)
- **Critical Paths**: 100% (payment creation → webhook → status update)

### Performance Targets
- **Test Suite Execution**: < 2 minutes
- **Individual Test**: < 10 seconds
- **CI Pipeline**: < 5 minutes end-to-end

### Quality Metrics
- **Flakiness Rate**: 0% (tests must be deterministic)
- **Bug Detection**: Catches all 5 critical risks identified
- **False Positives**: 0 (no tests fail on correct behavior)

---

## ⚠️ KNOWN LIMITATIONS & FUTURE WORK

### Out of Scope (60-minute constraint)
1. **Load testing**: Webhook processing under high concurrency
2. **Multi-payment-method**: Only PSE covered, not PIX/OXXO
3. **Real provider integration**: Using mocks, not sandbox APIs
4. **Security testing**: Full signature validation, SQL injection
5. **Performance optimization**: Database indexing, caching

### Next Iterations (Priority Order)
1. **Week 2**: Add PIX and OXXO payment method coverage
2. **Week 3**: Load test webhook endpoint (k6 or Locust)
3. **Week 4**: Real Banco Azul sandbox integration
4. **Week 5**: Contract testing (Pact) for webhook schema
5. **Month 2**: Chaos engineering (network failures, service outages)

---

## 🔐 SECURITY CONSIDERATIONS

### Webhook Signature Validation
```python
def validate_webhook_signature(payload: dict, signature: str) -> bool:
    """Verify webhook authenticity"""
    # Production: Use HMAC-SHA256 with shared secret
    expected = hmac.new(
        key=WEBHOOK_SECRET.encode(),
        msg=json.dumps(payload).encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, signature)
```

**Test**: Invalid signature should reject webhook (Test #11, deferred)

### Idempotency Key Security
- Must be UUID v4 (not sequential integers)
- Expire after 24 hours
- Store hash, not plaintext

### Rate Limiting
- Webhook endpoint: 100 req/min per provider
- Payment creation: 10 req/min per customer

---

## 📊 RISK MITIGATION MATRIX

| Risk | Likelihood | Impact | Mitigation | Test Coverage |
|------|------------|--------|------------|---------------|
| Race condition (webhook timing) | High | Critical | Smart polling, timestamp ordering | Test #6, #7 |
| Duplicate webhooks | High | Critical | Idempotency keys, deduplication | Test #8 |
| Out-of-order webhooks | Medium | High | Timestamp-based ordering | Test #9 |
| Webhook spoofing | Low | Critical | Signature validation | Deferred |
| Timeout handling | Medium | Medium | Expiration logic | Deferred |

---

## 📞 TEAM RESPONSIBILITIES

### QA Automation Expert
- ✅ Test strategy (this document)
- ✅ Framework selection
- ✅ Priority matrix
- ✅ Git workflow setup

### Backend Engineer 1
- ✅ API integration tests (#1-4)
- ✅ Payment factory
- ✅ API client wrapper
- ✅ Validation tests

### Backend Engineer 2
- ✅ Async/webhook tests (#5-10)
- ✅ Webhook simulator
- ✅ Polling utility
- ✅ Race condition tests

### Devil's Advocate
- ✅ Risk analysis (5 critical risks)
- ✅ Edge case identification
- ✅ Security review
- ✅ Mitigation strategies

---

## 🚦 EXECUTION TIMELINE (60 minutes)

```
:00-:15  QA Expert        → Strategy, framework, this document
:15-:40  Backend 1 & 2    → Tests (parallel)
         Backend 1        → API tests (#1-4)
         Backend 2        → Webhook tests (#5-10)
:40-:50  Integration      → Connect UI to API, verify end-to-end
:50-:60  Devil's Advocate → Risk review, security checks, final QA
```

---

## ✅ FINAL CHECKLIST

### Before Starting Implementation
- [ ] All agents reviewed this plan
- [ ] Framework choices approved
- [ ] Test priorities aligned
- [ ] Git repo initialized
- [ ] Vercel project created

### During Implementation
- [ ] Commit after each test
- [ ] Push at end of time window
- [ ] Keep tests simple (no over-engineering)
- [ ] Document edge case rationale

### Before Submission
- [ ] All tests pass
- [ ] CI pipeline green
- [ ] Vercel deployment live
- [ ] README complete
- [ ] Git history clean

---

**Document Version**: 1.0
**Created**: 2024-01-15
**Team**: QA Automation Expert, Backend Engineers 1 & 2, Devil's Advocate
**Status**: APPROVED - Ready for implementation

---

## 🎓 KEY TAKEAWAYS

1. **60-minute constraint demands ruthless prioritization**: Focus on P0 risks (race conditions, idempotency) over comprehensive coverage.

2. **Integration tests > E2E for this problem**: Webhook timing issues are best caught at API level, not through UI automation.

3. **Smart polling beats arbitrary sleeps**: Deterministic async handling prevents flaky tests.

4. **Idempotency is non-negotiable**: Both payment creation and webhook processing must be idempotent.

5. **Mock thoughtfully**: Webhook simulator must replicate real-world behaviors (delays, duplicates, out-of-order).

6. **Document trade-offs**: Clearly state what's deferred and why.

7. **Git commits tell the story**: Incremental commits show progress and enable easy rollback.

---

**Ready to implement. Timer starts now.** ⏱️
