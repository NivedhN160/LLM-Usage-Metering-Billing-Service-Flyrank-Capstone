# Pinned Token & API Pricing Rules (Stored as integer micro-cents: 1 USD = 1,000,000 micro-cents)

MICRO_CENTS_PER_USD = 1_000_000

# Pricing per 1,000 tokens (in micro-cents)
COST_INPUT_TOKEN_MICRO_CENTS_PER_1K = 150       # $0.15 / 1M tokens = 150 micro-cents / 1k
COST_CACHED_INPUT_TOKEN_MICRO_CENTS_PER_1K = 75   # 50% discount = 75 micro-cents / 1k
COST_OUTPUT_TOKEN_MICRO_CENTS_PER_1K = 600      # $0.60 / 1M tokens = 600 micro-cents / 1k
COST_REASONING_TOKEN_MICRO_CENTS_PER_1K = 600   # Reasoning tokens count as output tokens

# Pricing per API call (in micro-cents)
COST_API_CALL_MICRO_CENTS = 100                 # $0.001 per call = 100 micro-cents

def calculate_token_cost_micro_cents(
    input_tokens: int = 0,
    cached_input_tokens: int = 0,
    output_tokens: int = 0,
    reasoning_tokens: int = 0
) -> int:
    """
    Calculates total token cost in integer micro-cents following pinned AI token pricing rules.
    - Cached input tokens receive 50% discount rate.
    - Reasoning tokens are priced identically to output tokens.
    """
    input_cost = (input_tokens / 1000.0) * COST_INPUT_TOKEN_MICRO_CENTS_PER_1K
    cached_cost = (cached_input_tokens / 1000.0) * COST_CACHED_INPUT_TOKEN_MICRO_CENTS_PER_1K
    output_cost = (output_tokens / 1000.0) * COST_OUTPUT_TOKEN_MICRO_CENTS_PER_1K
    reasoning_cost = (reasoning_tokens / 1000.0) * COST_REASONING_TOKEN_MICRO_CENTS_PER_1K

    total_micro_cents = int(round(input_cost + cached_cost + output_cost + reasoning_cost))
    return total_micro_cents

def micro_cents_to_usd(micro_cents: int) -> float:
    """Converts integer micro-cents to standard USD float representation."""
    return round(micro_cents / float(MICRO_CENTS_PER_USD), 6)
