# 💳 LLM Usage Metering & Billing Service

> A production-grade backend billing and metering service designed for SaaS and AI applications. Provides **no-double-count idempotency guarantees**, strict quota boundary enforcement (`HTTP 429` / `402`), exact integer money math (micro-cents), and signature-verified Stripe test-mode webhook synchronization.

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Framework](https://img.shields.io/badge/framework-FastAPI%20%7C%20Pydantic-orange.svg)](https://fastapi.tiangolo.com/)
[![Billing Accuracy](https://img.shields.io/badge/Money%20Math-Micro--Cents%20Exact-brightgreen.svg)](README.md)

---

## 🏗️ Architecture Diagram & System Flow

```text
Client Application ──► Billable API Request (e.g. POST /api/v1/generate)
                          │  Headers: Idempotency-Key: key_12345
                          ▼
            Idempotency Deduplication Check
            ├─► Duplicate Key Found? ──► Return original response (No double counting!)
            └─► New Request ──► MeterService.process()
                                   │
                    ┌──────────────┴──────────────┐
                    ▼                             ▼
           Quota Boundary Check          Integer Micro-Cent Pricing
           ├─ At limit? ──► Allow        ├─ Input Tokens: $0.15 / 1M
           └─ Exceeded? ──► HTTP 429/402 ├─ Cached Input (50% discount): $0.075 / 1M
              (Retry-After: 3600)        ├─ Output Tokens: $0.60 / 1M
                                         └─ Reasoning Tokens: $0.60 / 1M (Output rate)

Stripe Test Mode (Checkout) ──► Event Created
                                     │
                                     ▼
        POST /api/v1/webhooks/stripe (Signed Webhook)
        ├─► Signature Invalid? ──► HTTP 400 Bad Request
        ├─► Event ID Processed? ──► Ignore Duplicate
        └─► Valid Event ───────► Flip Tenant Plan: Free ──► Pro
```

---

## 💰 Money Math & Pinned Token Pricing Rules

All monetary values are calculated and stored as **integer micro-cents** (`1 USD = 1,000,000 micro-cents`) to ensure zero floating-point rounding errors across monthly usage rollups.

| Token / Metric Type | Standard Rate | Rate in Micro-Cents | Special Rule |
| :--- | :--- | :--- | :--- |
| **Input Tokens** | `$0.15` / 1M tokens | `150` micro-cents / 1k | Standard rate |
| **Cached Input Tokens** | `$0.075` / 1M tokens | `75` micro-cents / 1k | **50% Discount** for cached context |
| **Output Tokens** | `$0.60` / 1M tokens | `600` micro-cents / 1k | Standard output rate |
| **Reasoning Tokens** | `$0.60` / 1M tokens | `600` micro-cents / 1k | **Billed at Output Token Rate** |
| **API Calls** | `$0.001` / call | `100` micro-cents / call | Per-request call fee |

---

## 🛠️ Required Submission Pack Files (§ 11)

| Required File | Purpose & Contents |
| :--- | :--- |
| **`README.md`** | System architecture, setup/seed/run/test commands, money math rules, and limitations note. |
| **`capstone.yaml`** | Evaluator manifest specifying `run: python main.py`, `seed: python seed_demo_data.py`, `test: pytest test_suite.py -v`, `base_url: http://localhost:8000`, and probe endpoints. |
| **`EVIDENCE.md`** | Verification transcripts and Pytest probe evidence for every Definition-of-Done checkbox. |
| **`BUILDLOG.md`** | AI usage log detailing prompt assistance, refactoring decisions, and bug fixes. |
| **`.env.example`** | Safe environment variable template with non-sensitive defaults. |

---

## 💻 Reproducible Setup & Run Instructions

### Step 1: Clone & Navigate to Repository
```bash
git clone https://github.com/NivedhN160/LLM-Usage-Metering-Billing-Service-Flyrank-Capstone.git
cd LLM-Usage-Metering-Billing-Service-Flyrank-Capstone
```

### Step 2: Create & Activate Virtual Environment
```bash
# Windows PowerShell:
python -m venv venv
.\venv\Scripts\Activate.ps1

# macOS/Linux:
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Seed Demo Data
```bash
python seed_demo_data.py
```

### Step 5: Start the API Server
```bash
python main.py
```
*API Server boots on `http://localhost:8000`. Interactive Swagger UI available at `http://localhost:8000/docs`.*

---

## 🧪 Automated Acceptance Probe Test Suite

Run the automated acceptance suite verifying all 5 evaluator probes (§ 12):
```bash
pytest test_suite.py -v
```

*Verification Results:*
```text
test_suite.py::test_probe_1_idempotent_no_double_count PASSED            [ 20%]
test_suite.py::test_probe_2_quota_boundary_enforcement PASSED            [ 40%]
test_suite.py::test_probe_3_stripe_test_checkout_upgrade PASSED          [ 60%]
test_suite.py::test_probe_4_forged_and_replayed_webhook_handling PASSED  [ 80%]
test_suite.py::test_probe_5_pinned_token_pricing_rules PASSED            [100%]

======================= 5 passed in 0.86s =======================
```

---

## ⚠️ Honest Limitations Note

1. **In-Memory Idempotency Map:** Idempotency keys are cached in memory. For multi-node distributed clusters, idempotency keys should be stored in Redis with atomic `SETNX` commands.
2. **Stripe Test Mode:** Payments use Stripe test mode. Live credit card processing requires turning on live keys in a production environment.

---

## 📄 License

Built by **Nivedh** for the **FlyRank AI Internship — Backend AI Engineering Track Capstone**.  
Licensed under the [MIT License](LICENSE).
