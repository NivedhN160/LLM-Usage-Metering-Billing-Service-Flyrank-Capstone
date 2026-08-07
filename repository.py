import logging
from typing import Dict, List, Optional
from models import Tenant, SubscriptionPlan, UsageEventRecord

logger = logging.getLogger("BillingRepository")

PLANS: Dict[str, SubscriptionPlan] = {
    "Free": SubscriptionPlan(name="Free", monthly_api_limit=1000, monthly_token_limit=100000, monthly_price_usd=0.0),
    "Pro": SubscriptionPlan(name="Pro", monthly_api_limit=100000, monthly_token_limit=10000000, monthly_price_usd=29.0)
}

class Repository:
    """Decoupled Data Store for Tenants, Usage Events, Idempotency Keys, and Webhook Event IDs."""
    def __init__(self):
        self.tenants: Dict[str, Tenant] = {}
        self.usage_events: List[UsageEventRecord] = []
        self.idempotency_map: Dict[str, UsageEventRecord] = {}
        self.processed_webhook_events: set = set()

    def save_tenant(self, tenant: Tenant):
        self.tenants[tenant.id] = tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        return self.tenants.get(tenant_id)

    def get_idempotent_event(self, idempotency_key: str) -> Optional[UsageEventRecord]:
        return self.idempotency_map.get(idempotency_key)

    def record_usage(self, event: UsageEventRecord):
        self.usage_events.append(event)
        self.idempotency_map[event.idempotency_key] = event

    def get_tenant_events(self, tenant_id: str) -> List[UsageEventRecord]:
        return [e for e in self.usage_events if e.tenant_id == tenant_id]

    def is_webhook_processed(self, event_id: str) -> bool:
        return event_id in self.processed_webhook_events

    def mark_webhook_processed(self, event_id: str):
        self.processed_webhook_events.add(event_id)

repo = Repository()
