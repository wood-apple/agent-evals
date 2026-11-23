from __future__ import annotations

import logging
from functools import cache

import litellm

log = logging.getLogger(__name__)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    input_price, output_price = price_per_token(model)
    return input_tokens * input_price + output_tokens * output_price


@cache
def price_per_token(model: str) -> tuple[float, float]:
    try:
        input_cost, output_cost = litellm.cost_per_token(
            model=model, prompt_tokens=1, completion_tokens=1
        )
    except Exception:  # noqa: BLE001 - litellm raises a bare Exception for unmapped models
        log.warning("no price known for %s; counting its cost as 0", model)
        return 0.0, 0.0
    return input_cost, output_cost
