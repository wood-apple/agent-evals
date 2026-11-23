import pytest

from evals.pricing import cost_usd


def test_small_requests_use_the_base_tier():
    assert cost_usd("anthropic/claude-haiku-5-5", 1000, 1000) == pytest.approx(
        1000 * 1e-7 + 1000 * 5e-7
    )


def test_long_context_requests_use_the_higher_tier():
    assert cost_usd("anthropic/claude-haiku-5-5", 200_000, 0) == pytest.approx(
        200_000 * 5e-7
    )


def test_unknown_models_cost_nothing():
    assert cost_usd("nobody/knows-this-model", 1000, 1000) == 0.0
