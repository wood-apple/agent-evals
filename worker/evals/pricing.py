from __future__ import annotations

import logging
from functools import cache

import litellm

log = logging.getLogger(__name__)


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    try:
        input_cost, output_cost = litellm.cost_per_token(
            model=model, prompt_tokens=input_tokens, completion_tokens=output_tokens
        )
    except Exception:  # noqa: BLE001 - litellm raises a bare Exception for unmapped models
        warn_unpriced(model)
        return 0.0
    return input_cost + output_cost


@cache
def warn_unpriced(model: str) -> None:
    log.warning("no price known for %s; counting its cost as 0", model)
