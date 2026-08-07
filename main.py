import os
import uuid
import logging
from typing import Optional
from fastapi import FastAPI, Request, Response, Header, HTTPException, status
from fastapi.responses import JSONResponse

from models import MeterRequest, MeterResponse
from repository import repo, PLANS
from metering_service import process_meter_request, get_tenant_rollup
from stripe_service import verify_and_process_webhook_raw, compute_mock_signature

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("BillingEngineApp")

app = FastAPI(
    title="LLM Usage Metering & Billing Service",
    description="Production-grade idempotent usage metering, quota enforcement, AI token cost calculator, and Stripe webhook sync.",
    version="1.0.0"
)

# ---------------------------------------------------------
# Health Check
# ---------------------------------------------------------
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "LLM Usage Metering & Billing Service",
        "tenants_count": len(repo.tenants),
        "events_count": len(repo.usage_events)
    }

# ---------------------------------------------------------
# 1. Raw Metering API Endpoint (POST /api/v1/meter)
# ---------------------------------------------------------
@app.post("/api/v1/meter", response_model=MeterResponse)
def record_meter_event(req: MeterRequest):
    res, _ = process_meter_request(req)
    return res

# ---------------------------------------------------------
# 2. Dummy Billable API Endpoint (POST /api/v1/generate)
# ---------------------------------------------------------
@app.post("/api/v1/generate")
def generate_billable_completion(
    prompt: str,
    tenant_id: str = "tenant-demo-1",
    idempotency_key: Optional[str] = Header(None)
):
    if not idempotency_key:
        idempotency_key = f"key_gen_{uuid.uuid4().hex[:10]}"

    # Metering payload: 1 API call + simulated LLM token counts
    meter_req = MeterRequest(
        tenant_id=tenant_id,
        idempotency_key=idempotency_key,
        usage_type="AI_TOKENS",
        input_tokens=1500,
        cached_input_tokens=500,
        output_tokens=800,
        reasoning_tokens=200,
        api_calls=1
    )

    meter_res, is_dup = process_meter_request(meter_req)

    return {
        "status": "success",
        "completion": f"Simulated LLM Completion for prompt: '{prompt}'",
        "metering": meter_res.dict()
    }

# ---------------------------------------------------------
# 3. Tenant Usage & Billing Rollup (GET /api/v1/usage)
# ---------------------------------------------------------
@app.get("/api/v1/usage")
def get_usage_overview(tenant_id: str = "tenant-demo-1"):
    return get_tenant_rollup(tenant_id)

# ---------------------------------------------------------
# 4. Stripe Webhook Handler (POST /api/v1/webhooks/stripe)
# ---------------------------------------------------------
@app.post("/api/v1/webhooks/stripe")
async def handle_stripe_webhook(request: Request, stripe_signature: Optional[str] = Header(None)):
    raw_body = await request.body()
    result = verify_and_process_webhook_raw(raw_body, stripe_signature or "")
    return result

# ---------------------------------------------------------
# 5. Mock Stripe Checkout Session (POST /api/v1/checkout/session)
# ---------------------------------------------------------
@app.post("/api/v1/checkout/session")
def create_checkout_session(tenant_id: str = "tenant-demo-1", plan_name: str = "Pro"):
    tenant = repo.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    checkout_url = f"https://checkout.stripe.com/c/pay/cs_test_mocksession_{tenant.id}"
    return {
        "status": "success",
        "checkout_url": checkout_url,
        "tenant_id": tenant.id,
        "target_plan": plan_name
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
