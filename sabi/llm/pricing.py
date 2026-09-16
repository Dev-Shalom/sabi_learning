"""Model prices, in USD per million tokens.

First-party Anthropic API rates. Kept in one place so the cost report and the
budget kill-switch cannot disagree about what a request cost.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Price:
    input_per_mtok: float
    output_per_mtok: float
    # Cache reads are about a tenth of the input rate, cache writes about 1.25x.
    cache_read_multiplier: float = 0.1
    cache_write_multiplier: float = 1.25


PRICES: dict[str, Price] = {
    "claude-haiku-4-5": Price(1.00, 5.00),
    "claude-sonnet-5": Price(2.00, 10.00),
    "claude-opus-5": Price(5.00, 25.00),
}

# The offline provider makes no API call. It is priced at the cheap model's
# rates purely so the instrumentation has something to exercise; every row it
# writes is flagged `cost_is_estimated`.
OFFLINE_PRICED_AS = "claude-haiku-4-5"


def price_for(model: str) -> Price:
    if model in PRICES:
        return PRICES[model]
    # An unknown model must not silently cost zero. Price it at the most
    # expensive rate we know so the budget guard errs toward stopping.
    return max(PRICES.values(), key=lambda p: p.output_per_mtok)


def cost_usd(
    model: str,
    tokens_in: int,
    tokens_out: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    p = price_for(model)
    total = (
        tokens_in * p.input_per_mtok
        + tokens_out * p.output_per_mtok
        + cache_read_tokens * p.input_per_mtok * p.cache_read_multiplier
        + cache_write_tokens * p.input_per_mtok * p.cache_write_multiplier
    ) / 1_000_000
    return round(total, 8)
