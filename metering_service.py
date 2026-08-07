import logging
from typing import Tuple, Dict, Any
from fastapi import HTTPException
from models import Tenant, MeterRequest, MeterResponse, UsageEventRecord, UsageRollup
from repository import repo, PLANS
from pricing import (
    calculate_token_cost_micro_cents,
    micro_cents_to_usd,
    COST_API_CALL_MICRO_CENTS
)

logger = logging.getLogger("MeteringService")

def process_meter_request(req: MeterRequest) -> Tuple[MeterResponse, bool]:
    """
    Idempotently records a usage event. 
    If same request + same idempotency_key is sent again, returns stored original result without double counting.
    """
    # 1. Idempotency Check (No Double Counting Guarantee)
    existing_event = repo.get_idempotent_event(req.idempotency_key)
    if existing_event:
        logger.info(f"🔄 Idempotent request detected for key '{req.idempotency_key}'. Returning stored event without double counting.")
        return MeterResponse(
            status="SUCCESS_IDEMPOTENT_DUPLICATE",
            tenant_id=existing_event.tenant_id,
            idempotency_key=existing_event.idempotency_key,
            is_duplicate=True,
            usage_event_id=existing_event.id,
            cost_usd=micro_cents_to_usd(existing_event.cost_micro_cents),
            cost_micro_cents=existing_event.cost_micro_cents
        ), True

    tenant = repo.get_tenant(req.tenant_id)
    if not tenant:
        tenant = Tenant(id=req.tenant_id, name="Demo Tenant", email="tenant@example.com")
        repo.save_tenant(tenant)

    plan = PLANS.get(tenant.plan_name, PLANS["Free"])

    # 2. Calculate Current Usage Rollup
    events = repo.get_tenant_events(tenant.id)
    used_api_calls = sum(e.api_calls for e in events)
    used_tokens = sum(e.input_tokens + e.cached_input_tokens + e.output_tokens + e.reasoning_tokens for e in events)

    requested_tokens = req.input_tokens + req.cached_input_tokens + req.output_tokens + req.reasoning_tokens

    # 3. Quota Boundary Check (429 / 402 Response)
    if (used_api_calls + req.api_calls) > plan.monthly_api_limit:
        logger.warning(f"⛔ Quota Exceeded! Tenant '{tenant.id}' requested {req.api_calls} API calls; limit is {plan.monthly_api_limit}.")
        raise HTTPException(
            status_code=429,
            detail=f"Usage quota exceeded: Current API call usage ({used_api_calls}) + requested ({req.api_calls}) exceeds '{plan.name}' plan limit of {plan.monthly_api_limit}. Please upgrade to Pro or retry after quota reset.",
            headers={"Retry-After": "3600"}
        )

    if (used_tokens + requested_tokens) > plan.monthly_token_limit:
        logger.warning(f"⛔ Token Limit Exceeded! Tenant '{tenant.id}' requested {requested_tokens} tokens; limit is {plan.monthly_token_limit}.")
        raise HTTPException(
            status_code=402,
            detail=f"Payment/Upgrade Required: Current token usage ({used_tokens}) + requested ({requested_tokens}) exceeds '{plan.name}' plan token limit of {plan.monthly_token_limit}. Please upgrade to Pro plan.",
            headers={"Retry-After": "3600"}
        )

    # 4. Money Math & Cost Calculation (Integer Micro-Cents)
    token_cost = calculate_token_cost_micro_cents(
        input_tokens=req.input_tokens,
        cached_input_tokens=req.cached_input_tokens,
        output_tokens=req.output_tokens,
        reasoning_tokens=req.reasoning_tokens
    )
    api_cost = req.api_calls * COST_API_CALL_MICRO_CENTS
    total_cost_micro_cents = token_cost + api_cost

    # 5. Persist Usage Event
    event = UsageEventRecord(
        tenant_id=tenant.id,
        idempotency_key=req.idempotency_key,
        usage_type=req.usage_type,
        input_tokens=req.input_tokens,
        cached_input_tokens=req.cached_input_tokens,
        output_tokens=req.output_tokens,
        reasoning_tokens=req.reasoning_tokens,
        api_calls=req.api_calls,
        cost_micro_cents=total_cost_micro_cents
    )
    repo.record_usage(event)

    return MeterResponse(
        status="RECORDED",
        tenant_id=tenant.id,
        idempotency_key=event.idempotency_key,
        is_duplicate=False,
        usage_event_id=event.id,
        cost_usd=micro_cents_to_usd(event.cost_micro_cents),
        cost_micro_cents=event.cost_micro_cents
    ), False

def get_tenant_rollup(tenant_id: str) -> UsageRollup:
    tenant = repo.get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found.")

    plan = PLANS.get(tenant.plan_name, PLANS["Free"])
    events = repo.get_tenant_events(tenant_id)

    total_api_calls = sum(e.api_calls for e in events)
    total_input = sum(e.input_tokens for e in events)
    total_cached = sum(e.cached_input_tokens for e in events)
    total_output = sum(e.output_tokens for e in events)
    total_reasoning = sum(e.reasoning_tokens for e in events)

    total_tokens = total_input + total_cached + total_output + total_reasoning
    total_cost_micro_cents = sum(e.cost_micro_cents for e in events)

    return UsageRollup(
        tenant_id=tenant.id,
        plan_name=tenant.plan_name,
        period="August 2026",
        total_api_calls_used=total_api_calls,
        api_call_limit=plan.monthly_api_limit,
        api_call_remaining=max(0, plan.monthly_api_limit - total_api_calls),
        total_tokens_used=total_tokens,
        token_limit=plan.monthly_token_limit,
        token_remaining=max(0, plan.monthly_token_limit - total_tokens),
        token_breakdown={
            "input_tokens": total_input,
            "cached_input_tokens": total_cached,
            "output_tokens": total_output,
            "reasoning_tokens": total_reasoning
        },
        total_cost_usd=micro_cents_to_usd(total_cost_micro_cents),
        total_cost_micro_cents=total_cost_micro_cents
    )
