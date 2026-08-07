# 📝 BUILDLOG.md — AI Co-Pilot & Architectural Build Log

**Capstone Project:** LLM Usage Metering & Billing Service  
**Track:** Backend AI Engineering Capstone  
**Author:** Nivedh  

---

## 📌 Build Journey & AI Collaboration Notes

### 1. Where AI Assisted
* **Idempotency Strategy Design:** AI generated the header parsing logic for `Idempotency-Key` and draft deduplication maps.
* **Stripe Webhook Signature Verification:** AI assisted in writing the `hmac.compare_digest` verification loop for signed Stripe webhook payloads.
* **Pytest Acceptance Probe Suite:** AI helped draft test fixtures verifying boundary conditions (`429` / `402`).

### 2. Where AI Was Incorrect / Required Human Refinement
* **Floating-Point Money Precision Bug:** The AI initially used float numbers for token prices (`0.00000015 * tokens`), causing floating-point rounding errors on small token amounts. I refactored the entire pricing module (`pricing.py`) to calculate money in integer micro-cents (`1 USD = 1,000,000 micro-cents`) with exact micro-cent conversion.
* **Reasoning Token Billing Rule:** The AI originally omitted reasoning tokens from output pricing. I explicitly encoded the rule: *"Reasoning tokens count as output tokens at $0.60 / 1M rate."*

### 3. Key Architectural Decisions
* **Exact-Integer Money Representation:** All monetary values stored as integer micro-cents to prevent rounding inaccuracies during monthly rollups.
* **Signature-Verified Webhook Handler:** Strict validation ensuring forged Stripe signatures are rejected with HTTP 400 Bad Request.
