# 📄 EVIDENCE.md — Definition of Done Verification Log

**Capstone Project:** LLM Usage Metering & Billing Service  
**Track:** Backend AI Engineering Capstone  
**Author:** Nivedh  
**Repository:** [https://github.com/NivedhN160/LLM-Usage-Metering-Billing-Service-Flyrank-Capstone](https://github.com/NivedhN160/LLM-Usage-Metering-Billing-Service-Flyrank-Capstone)  

---

## 📌 Verification Checklist & Evidence Transcripts

### 1. Exactly-Once Metering & No Double Counting Guarantee
* [x] **Requirement:** Retried billable request with same idempotency key creates exactly 1 usage event; second request mirrors the first.
* [x] **Evidence (Pytest Probe 1):**
  ```text
  test_suite.py::test_probe_1_idempotent_no_double_count PASSED
  Request 1: HTTP 200 | status: "RECORDED" | is_duplicate: False
  Request 2 (same idempotency_key): HTTP 200 | status: "SUCCESS_IDEMPOTENT_DUPLICATE" | is_duplicate: True
  Database Verification: Exactly 1 usage event row preserved.
  ```

### 2. Quota Boundary Enforcement & Honest Error Semantics
* [x] **Requirement:** Boundary request allowed; request exceeding limit rejected with HTTP 429 / 402, clear message, and `Retry-After: 3600` header.
* [x] **Evidence (Pytest Probe 2):**
  ```text
  test_suite.py::test_probe_2_quota_boundary_enforcement PASSED
  Request at exact limit (1,000 API calls): HTTP 200 OK (Allowed).
  Request 1,001 (exceeding limit): HTTP 429 Too Many Requests | Header: Retry-After: 3600 | Detail: "Usage quota exceeded: ... plan limit of 1000."
  ```

### 3. Stripe Test Mode Checkout & Plan Synchronization
* [x] **Requirement:** Completing Stripe Checkout webhook flips tenant plan from Free → Pro; GET /usage reflects new limits.
* [x] **Evidence (Pytest Probe 3):**
  ```text
  test_suite.py::test_probe_3_stripe_test_checkout_upgrade PASSED
  Event: checkout.session.completed -> Tenant 'tenant-demo-1' flipped Free -> Pro.
  GET /api/v1/usage -> api_call_limit: 100,000 | token_limit: 10,000,000.
  ```

### 4. Forged & Replayed Webhook Handling
* [x] **Requirement:** Forged signature returns HTTP 400 Bad Request; replayed webhook event ID is processed once and ignored on duplicate.
* [x] **Evidence (Pytest Probe 4):**
  ```text
  test_suite.py::test_probe_4_forged_and_replayed_webhook_handling PASSED
  Forged Signature: HTTP 400 Bad Request ("Stripe signature verification failed.")
  Valid Signature: HTTP 200 OK ("PLAN_UPGRADED")
  Replayed Signature: HTTP 200 OK ("IGNORED_DUPLICATE")
  ```

### 5. Pinned AI-Token Pricing Rules & Money Math
* [x] **Requirement:** Pinned pricing rules calculate cached input tokens (discounted) and reasoning tokens (output rate) in integer micro-cents.
* [x] **Evidence (Pytest Probe 5):**
  ```text
  test_suite.py::test_probe_5_pinned_token_pricing_rules PASSED
  Input Tokens (10k @ $0.15/1M): 1,500 micro-cents
  Cached Input Tokens (10k @ $0.075/1M 50% discount): 750 micro-cents
  Output Tokens (10k @ $0.60/1M): 6,000 micro-cents
  Reasoning Tokens (10k @ $0.60/1M output rate): 6,000 micro-cents
  Total Micro-Cents: 14,250 ($0.01425 USD) | Pinned test GREEN.
  ```
