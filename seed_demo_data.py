from repository import repo
from models import Tenant, MeterRequest
from metering_service import process_meter_request

def seed():
    print("🌱 Seeding Demo Dataset for LLM Usage Metering & Billing Service...")

    # 1. Create Free Tenant (Quota boundary testing)
    t1 = Tenant(id="tenant-demo-1", name="Acme Free Agency", email="acme@free.com", plan_name="Free")
    repo.save_tenant(t1)
    print(f"  ✓ Created Free Tenant ID: '{t1.id}' (Quota: 1,000 API calls / 100k tokens)")

    # 2. Create Pro Tenant
    t2 = Tenant(id="tenant-demo-2", name="Enterprise Pro Corp", email="enterprise@pro.com", plan_name="Pro")
    repo.save_tenant(t2)
    print(f"  ✓ Created Pro Tenant ID: '{t2.id}' (Quota: 100,000 API calls / 10,000,000 tokens)")

    # 3. Seed Sample Usage Events
    req1 = MeterRequest(
        tenant_id=t1.id,
        idempotency_key="seed_key_001",
        usage_type="AI_TOKENS",
        input_tokens=10000,
        cached_input_tokens=5000,
        output_tokens=3000,
        reasoning_tokens=1000,
        api_calls=50
    )
    process_meter_request(req1)

    req2 = MeterRequest(
        tenant_id=t2.id,
        idempotency_key="seed_key_002",
        usage_type="AI_TOKENS",
        input_tokens=50000,
        cached_input_tokens=20000,
        output_tokens=15000,
        reasoning_tokens=5000,
        api_calls=250
    )
    process_meter_request(req2)

    print(f"  ✓ Recorded {len(repo.usage_events)} Sample Usage Events with Exact Money Math.")
    print("\n✅ SEED COMPLETE! You can run pytest test_suite.py -v or boot python main.py")

if __name__ == "__main__":
    seed()
