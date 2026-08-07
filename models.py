import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, EmailStr

# ---------------------------------------------------------
# Subscription & Quota Schemas
# ---------------------------------------------------------
class SubscriptionPlan(BaseModel):
    name: str # "Free" or "Pro"
    monthly_api_limit: int # e.g. Free=1000, Pro=100000
    monthly_token_limit: int # e.g. Free=100000, Pro=10000000
    monthly_price_usd: float

class Tenant(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    email: EmailStr
    plan_name: str = "Free"
    stripe_customer_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

# ---------------------------------------------------------
# Usage Event & Metering Schemas
# ---------------------------------------------------------
class UsageEventRecord(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    tenant_id: str
    idempotency_key: str
    usage_type: str # "API_CALL" or "AI_TOKENS"
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    api_calls: int = 1
    cost_micro_cents: int = 0
    created_at: datetime = Field(default_factory=datetime.utcnow)

class MeterRequest(BaseModel):
    tenant_id: str
    idempotency_key: str
    usage_type: str # "API_CALL" or "AI_TOKENS"
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0
    api_calls: int = 1

class MeterResponse(BaseModel):
    status: str
    tenant_id: str
    idempotency_key: str
    is_duplicate: bool
    usage_event_id: str
    cost_usd: float
    cost_micro_cents: int

# ---------------------------------------------------------
# Rollup Summary Schema
# ---------------------------------------------------------
class UsageRollup(BaseModel):
    tenant_id: str
    plan_name: str
    period: str
    total_api_calls_used: int
    api_call_limit: int
    api_call_remaining: int
    total_tokens_used: int
    token_limit: int
    token_remaining: int
    token_breakdown: Dict[str, int]
    total_cost_usd: float
    total_cost_micro_cents: int
