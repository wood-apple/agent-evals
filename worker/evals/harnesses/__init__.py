from __future__ import annotations

from evals.harness import Harness


def get_harness(name: str) -> Harness:
    if name == "baseline":
        from evals.harnesses.baseline import BaselineHarness

        return BaselineHarness()
    if name == "hermes":
        from evals.harnesses.hermes import HermesHarness

        return HermesHarness()
    raise ValueError(f"unknown harness {name!r}")
