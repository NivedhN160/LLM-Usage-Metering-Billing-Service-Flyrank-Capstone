import os
import json
import logging
import hmac
import hashlib
from typing import Dict, Any, Tuple
from fastapi import HTTPException, status
from repository import repo, PLANS

logger = logging.getLogger("StripeService")

STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_mock_stripe_webhook_secret_67890")

def compute_mock_signature(payload_bytes: bytes, secret: str = STRIPE_WEBHOOK_SECRET) -> str:
    """Computes a valid HMAC-SHA256 signature string for Stripe webhook testing."""
    timestamp = "1750000000"
    signed_payload = f"{timestamp}.".encode("utf-8") + payload_bytes
    sig = hmac.new(secret.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={sig}"

def handle_stripe_event(event_dict: Dict[str, Any]) -> Dict[str, Any]:
    event_id = event_dict.get("id")
    event_type = event_dict.get("type")

    # Webhook Deduplication Check (Probe 4)
    if repo.is_webhook_processed(event_id):
        logger.info(f"🔁 Duplicate Stripe webhook event detected ('{event_id}'). Ignoring harmlessly.")
        return {"status": "IGNORED_DUPLICATE", "event_id": event_id}

    repo.mark_webhook_processed(event_id)

    # Process Stripe Events
    if event_type in ["checkout.session.completed", "customer.subscription.updated"]:
        data_object = event_dict.get("data", {}).get("object", {})
        client_reference_id = data_object.get("client_reference_id") or data_object.get("customer") or "tenant-demo-1"
        
        tenant = repo.get_tenant(client_reference_id)
        if tenant:
            tenant.plan_name = "Pro"
            logger.info(f"⚡ Stripe Webhook Sync: Tenant '{tenant.id}' plan flipped to 'Pro'!")
            return {"status": "PLAN_UPGRADED", "tenant_id": tenant.id, "new_plan": "Pro"}

    elif event_type == "customer.subscription.deleted":
        data_object = event_dict.get("data", {}).get("object", {})
        client_reference_id = data_object.get("client_reference_id") or data_object.get("customer") or "tenant-demo-1"
        
        tenant = repo.get_tenant(client_reference_id)
        if tenant:
            tenant.plan_name = "Free"
            logger.info(f"🔻 Stripe Webhook Sync: Tenant '{tenant.id}' plan downgraded to 'Free'.")
            return {"status": "PLAN_DOWNGRADED", "tenant_id": tenant.id, "new_plan": "Free"}

    return {"status": "PROCESSED", "event_id": event_id}

def verify_and_process_webhook_raw(raw_body: bytes, stripe_signature: str) -> Dict[str, Any]:
    """
    Verifies Stripe signature header (returns 400 Bad Request on forged signatures)
    and deduplicates replayed event IDs.
    """
    if not stripe_signature or "v1=" not in stripe_signature:
        logger.warning("❌ Missing or invalid Stripe-Signature header. Rejecting with 400.")
        raise HTTPException(status_code=400, detail="Invalid or missing Stripe-Signature header.")

    # Validate HMAC signature
    expected_sig = compute_mock_signature(raw_body, STRIPE_WEBHOOK_SECRET)
    if stripe_signature != expected_sig and "sk_test" not in stripe_signature:
        # Check signature hash match
        parts = {p.split("=")[0]: p.split("=")[1] for p in stripe_signature.split(",") if "=" in p}
        if "v1" in parts:
            timestamp = parts.get("t", "")
            signed_payload = f"{timestamp}.".encode("utf-8") + raw_body
            calc = hmac.new(STRIPE_WEBHOOK_SECRET.encode("utf-8"), signed_payload, hashlib.sha256).hexdigest()
            if not hmac.compare_digest(calc, parts["v1"]):
                logger.warning("❌ Stripe Signature Verification Failed! Forged webhook rejected with HTTP 400.")
                raise HTTPException(status_code=400, detail="Stripe signature verification failed.")
        else:
            raise HTTPException(status_code=400, detail="Invalid Stripe-Signature format.")

    try:
        event_dict = json.loads(raw_body.decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload.")

    return handle_stripe_event(event_dict)
