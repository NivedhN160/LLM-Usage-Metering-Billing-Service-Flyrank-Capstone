import json
import pytest
from fastapi.testclient import TestClient
from main import app
from repository import repo, PLANS
from seed_demo_data import seed
from pricing import calculate_token_cost_micro_cents, micro_cents_to_usd
from stripe_service import compute_mock_signature

client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_seed():
    repo.tenants.clear()
    repo.usage_events.clear()
    repo.idempotency_map.clear()
    repo.processed_webhook_events.clear()
    seed()

def test_probe_1_idempotent_no_double_count():
    """PROBE 1 — Send request twice with one idempotency key -> exactly 1 usage event recorded."""
    payload = {
        "tenant_id": "tenant-demo-1",
        "idempotency_key": "idempotent_test_key_999",
        "usage_type": "AI_TOKENS",
        "input_tokens": 1000,
        "cached_input_tokens": 0,
        "output_tokens": 500,
        "reasoning_tokens": 0,
        "api_calls": 1
    }

    # First request
    resp1 = client.post("/api/v1/meter", json=payload)
    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["is_duplicate"] is False
    assert data1["status"] == "RECORDED"

    events_count_after_first = len(repo.usage_events)

    # Second request with identical key
    resp2 = client.post("/api/v1/meter", json=payload)
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["is_duplicate"] is True
    assert data2["status"] == "SUCCESS_IDEMPOTENT_DUPLICATE"
    assert data2["usage_event_id"] == data1["usage_event_id"]

    # Verify no double counting in database
    assert len(repo.usage_events) == events_count_after_first

def test_probe_2_quota_boundary_enforcement():
    """PROBE 2 — Drive tenant to quota limit -> request at limit allowed; request over limit returns 429/402."""
    tenant = repo.get_tenant("tenant-demo-1")
    plan = PLANS[tenant.plan_name]

    # Drive API calls right to boundary (limit = 1000)
    current_calls = sum(e.api_calls for e in repo.get_tenant_events(tenant.id))
    needed_to_reach_limit = plan.monthly_api_limit - current_calls

    payload_boundary = {
        "tenant_id": tenant.id,
        "idempotency_key": "boundary_key_100",
        "usage_type": "API_CALL",
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "api_calls": needed_to_reach_limit
    }
    resp_boundary = client.post("/api/v1/meter", json=payload_boundary)
    assert resp_boundary.status_code == 200 # Allowed at exact limit

    # Next request exceeds limit -> 429
    payload_exceed = {
        "tenant_id": tenant.id,
        "idempotency_key": "exceed_key_101",
        "usage_type": "API_CALL",
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "api_calls": 1
    }
    resp_exceed = client.post("/api/v1/meter", json=payload_exceed)
    assert resp_exceed.status_code == 429
    assert "usage quota exceeded" in resp_exceed.json()["detail"].lower()
    assert "retry-after" in resp_exceed.headers

def test_probe_3_stripe_test_checkout_upgrade():
    """PROBE 3 — Complete Stripe test Checkout webhook -> tenant flips Free to Pro; usage shows new limits."""
    tenant = repo.get_tenant("tenant-demo-1")
    assert tenant.plan_name == "Free"

    webhook_payload = {
        "id": "evt_test_checkout_100",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "client_reference_id": tenant.id,
                "customer": "cus_test_123"
            }
        }
    }
    raw_bytes = json.dumps(webhook_payload).encode("utf-8")
    sig = compute_mock_signature(raw_bytes)

    resp = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_bytes,
        headers={"Stripe-Signature": sig, "Content-Type": "application/json"}
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "PLAN_UPGRADED"

    # Verify tenant plan flipped to Pro
    updated_tenant = repo.get_tenant(tenant.id)
    assert updated_tenant.plan_name == "Pro"

    # Verify rollup API shows Pro limits (100,000 API calls)
    rollup_resp = client.get(f"/api/v1/usage?tenant_id={tenant.id}")
    assert rollup_resp.status_code == 200
    assert rollup_resp.json()["api_call_limit"] == 100000

def test_probe_4_forged_and_replayed_webhook_handling():
    """PROBE 4 — Forged webhook -> 400 Bad Request; Replay webhook twice -> processed once."""
    webhook_payload = {
        "id": "evt_test_replay_200",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "client_reference_id": "tenant-demo-1"
            }
        }
    }
    raw_bytes = json.dumps(webhook_payload).encode("utf-8")

    # 1. Forged Signature -> HTTP 400
    resp_forged = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_bytes,
        headers={"Stripe-Signature": "t=1750000000,v1=forged_bad_signature_hash", "Content-Type": "application/json"}
    )
    assert resp_forged.status_code == 400

    # 2. Valid Signature -> Processed
    valid_sig = compute_mock_signature(raw_bytes)
    resp_valid = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_bytes,
        headers={"Stripe-Signature": valid_sig, "Content-Type": "application/json"}
    )
    assert resp_valid.status_code == 200
    assert resp_valid.json()["status"] == "PLAN_UPGRADED"

    # 3. Replay exact webhook twice -> Ignored as Duplicate
    resp_replay = client.post(
        "/api/v1/webhooks/stripe",
        content=raw_bytes,
        headers={"Stripe-Signature": valid_sig, "Content-Type": "application/json"}
    )
    assert resp_replay.status_code == 200
    assert resp_replay.json()["status"] == "IGNORED_DUPLICATE"

def test_probe_5_pinned_token_pricing_rules():
    """PROBE 5 — Run pinned pricing tests -> cached-input & reasoning tokens produce exact expected micro-cents."""
    # Test 10,000 input tokens = 1500 micro-cents ($0.0015)
    # Test 10,000 cached input tokens (50% discount) = 750 micro-cents ($0.00075)
    # Test 10,000 output tokens = 6000 micro-cents ($0.006)
    # Test 10,000 reasoning tokens (same as output) = 6000 micro-cents ($0.006)
    
    cost = calculate_token_cost_micro_cents(
        input_tokens=10000,
        cached_input_tokens=10000,
        output_tokens=10000,
        reasoning_tokens=10000
    )
    expected_micro_cents = 1500 + 750 + 6000 + 6000 # 14250 micro-cents
    assert cost == expected_micro_cents
    assert micro_cents_to_usd(cost) == 0.01425
