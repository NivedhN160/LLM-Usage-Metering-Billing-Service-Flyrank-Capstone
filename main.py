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

from fastapi.responses import JSONResponse, HTMLResponse

# ---------------------------------------------------------
# Health Check & Live Interactive Billing Console
# ---------------------------------------------------------
@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "LLM Usage Metering & Billing Service",
        "tenants_count": len(repo.tenants),
        "events_count": len(repo.usage_events)
    }

@app.get("/", response_class=HTMLResponse)
@app.get("/dashboard", response_class=HTMLResponse)
def live_dashboard():
    return """
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>FlyRank LLM Usage Metering & Billing Service — Live Console</title>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&family=Plus+Jakarta+Sans:wght@700&display=swap" rel="stylesheet">
  <style>
    body { font-family: 'Inter', sans-serif; background: #0F172A; color: #F8FAFC; margin: 0; padding: 24px; }
    .container { max-width: 1100px; margin: 0 auto; }
    .header { display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 16px; margin-bottom: 24px; }
    .title { font-family: 'Plus Jakarta Sans', sans-serif; font-size: 24px; color: #38BDF8; margin: 0; }
    .badge { background: #0369A1; color: #E0F2FE; padding: 4px 10px; border-radius: 999px; font-size: 12px; font-weight: bold; }
    .stat-row { display: flex; gap: 16px; margin-bottom: 24px; }
    .stat-box { flex: 1; background: #1E293B; padding: 14px; border-radius: 8px; border: 1px solid #334155; text-align: center; }
    .stat-val { font-size: 26px; font-weight: 700; color: #38BDF8; }
    .stat-lbl { font-size: 12px; color: #94A3B8; text-transform: uppercase; margin-top: 4px; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 24px; }
    .card { background: #1E293B; border: 1px solid #334155; border-radius: 12px; padding: 20px; }
    .card h3 { margin-top: 0; color: #F1F5F9; font-size: 18px; border-bottom: 1px solid #334155; padding-bottom: 10px; }
    input, button, select { width: 100%; box-sizing: border-box; background: #0F172A; border: 1px solid #475569; color: #FFF; padding: 10px; border-radius: 6px; margin-bottom: 10px; font-family: inherit; }
    button { background: #0284C7; border: none; font-weight: bold; cursor: pointer; }
    button:hover { background: #0369A1; }
    .log-box { background: #020617; border: 1px solid #1E293B; border-radius: 6px; padding: 12px; font-family: monospace; font-size: 12px; color: #34D399; height: 180px; overflow-y: auto; white-space: pre-wrap; }
    .progress-bar { background: #334155; border-radius: 999px; height: 10px; overflow: hidden; margin-top: 6px; }
    .progress-fill { background: #38BDF8; height: 100%; width: 25%; transition: width 0.3s; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <div>
        <h1 class="title">⚡ FlyRank LLM Usage Metering & Billing Engine</h1>
        <p style="color: #94A3B8; margin: 4px 0 0 0; font-size: 14px;">Idempotent Token Usage Aggregator, Micro-Cent Pricing & Stripe Invoicing</p>
      </div>
      <span class="badge">PROD RUNTIME (PORT 8000)</span>
    </div>

    <div class="stat-row">
      <div class="stat-box"><div class="stat-val" id="tenant-plan">PRO</div><div class="stat-lbl">Active Tier</div></div>
      <div class="stat-box"><div class="stat-val" id="tenant-tokens">2,500</div><div class="stat-lbl">Tokens Consumed</div></div>
      <div class="stat-box"><div class="stat-val" id="tenant-cost" style="color:#34D399;">$0.0125</div><div class="stat-lbl">Accrued Invoice Cost</div></div>
      <div class="stat-box"><div class="stat-val" style="color:#38BDF8;">100% IDEMPOTENT</div><div class="stat-lbl">Replay Protection</div></div>
    </div>

    <div class="grid">
      <div class="card">
        <h3>🧪 Simulate LLM Completion & Metering Event</h3>
        <form id="meter-form" onsubmit="sendMeterEvent(event)">
          <input type="text" id="prompt-input" placeholder="Prompt (e.g. Analyze financial risk)" value="Analyze multi-agent architecture and calculate cost">
          <div style="display:flex; gap:10px;">
            <input type="number" id="in-tokens" placeholder="Input Tokens" value="1500">
            <input type="number" id="out-tokens" placeholder="Output Tokens" value="800">
          </div>
          <button type="submit">Send Metered Request with Deduplication Key ➔</button>
        </form>
        <div style="margin-top: 14px;">
          <div style="font-size: 12px; color: #94A3B8; margin-bottom: 6px;">Real-Time Metering Response:</div>
          <div class="log-box" id="meter-logs">Ready for live metering events...</div>
        </div>
      </div>

      <div class="card">
        <h3>📊 Live Tenant Billing Rollup</h3>
        <div style="margin-bottom: 16px;">
          <div style="display:flex; justify-content:space-between; font-size:13px; color:#94A3B8;">
            <span>Token Quota Utilization:</span>
            <span id="quota-text">25% (25,000 / 100,000)</span>
          </div>
          <div class="progress-bar"><div class="progress-fill" id="quota-fill" style="width: 25%;"></div></div>
        </div>
        <div style="font-size: 13px; color: #E2E8F0; line-height: 1.8;">
          • <strong>Tenant ID:</strong> <code>tenant-demo-1</code><br>
          • <strong>Pricing Model:</strong> $0.000003/Input Token · $0.000015/Output Token<br>
          • <strong>Cached Token Discount:</strong> 50% Reduction ($0.0000015/Token)<br>
          • <strong>Stripe Customer ID:</strong> <code>cus_test_mock_12345</code>
        </div>
        <div style="margin-top: 20px;">
          <button style="background:#475569;" onclick="fetchUsageRollup()">Refresh Usage Rollup ➔</button>
        </div>
      </div>
    </div>
  </div>

  <script>
    async function fetchUsageRollup() {
      try {
        const r = await fetch('/api/v1/usage?tenant_id=tenant-demo-1');
        const d = await r.json();
        document.getElementById('tenant-plan').innerText = d.plan_name.toUpperCase();
        document.getElementById('tenant-tokens').innerText = d.total_tokens_consumed.toLocaleString();
        document.getElementById('tenant-cost').innerText = '$' + (d.total_cost_usd || 0).toFixed(4);
        const pct = Math.min(100, Math.round((d.total_tokens_consumed / (d.quota_limit || 100000)) * 100));
        document.getElementById('quota-text').innerText = `${pct}% (${d.total_tokens_consumed.toLocaleString()} / ${(d.quota_limit || 100000).toLocaleString()})`;
        document.getElementById('quota-fill').style.width = pct + '%';
      } catch(e){}
    }

    async function sendMeterEvent(e) {
      e.preventDefault();
      const logs = document.getElementById('meter-logs');
      logs.innerText = "Dispatching POST /api/v1/generate with auto-generated idempotency key...";
      try {
        const prompt = encodeURIComponent(document.getElementById('prompt-input').value);
        const r = await fetch(`/api/v1/generate?prompt=${prompt}&tenant_id=tenant-demo-1`, {
          method: 'POST',
          headers: { 'Idempotency-Key': 'key_' + Date.now() }
        });
        const res = await r.json();
        logs.innerText = JSON.stringify(res, null, 2);
        fetchUsageRollup();
      } catch(err) {
        logs.innerText = "Error: " + err.message;
      }
    }

    fetchUsageRollup();
  </script>
</body>
</html>
    """

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
