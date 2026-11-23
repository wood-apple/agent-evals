from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass
from statistics import mean

from evals.experiment import TrialResult

ALPHA = 0.05


@dataclass(frozen=True)
class Pair:
    task_id: str
    trial_index: int
    a: bool
    b: bool


def paired_trials(
    trials: list[TrialResult], config_a: str, config_b: str
) -> list[Pair]:
    by_key: dict[tuple[str, int], dict[str, TrialResult]] = defaultdict(dict)
    for trial in trials:
        if trial.status != "error" and trial.config_id in (config_a, config_b):
            by_key[(trial.task_id, trial.trial_index)][trial.config_id] = trial
    return [
        Pair(task_id, index, bool(pair[config_a].passed), bool(pair[config_b].passed))
        for (task_id, index), pair in sorted(by_key.items())
        if len(pair) == 2
    ]


def per_task_deltas(pairs: list[Pair]) -> dict[str, list[float]]:
    deltas: dict[str, list[float]] = defaultdict(list)
    for pair in pairs:
        deltas[pair.task_id].append(float(pair.b) - float(pair.a))
    return dict(deltas)


def mean_delta(deltas: dict[str, list[float]]) -> float:
    return mean(mean(d) for d in deltas.values())


def bootstrap_ci(
    deltas: dict[str, list[float]], iterations: int = 10_000, seed: int = 0
) -> tuple[float, float]:
    rng = random.Random(seed)
    tasks = list(deltas.values())
    estimates = []
    for _ in range(iterations):
        sample = [rng.choice(tasks) for _ in tasks]
        estimates.append(mean(mean(rng.choices(d, k=len(d))) for d in sample))
    estimates.sort()
    low = estimates[int(iterations * ALPHA / 2)]
    high = estimates[int(iterations * (1 - ALPHA / 2)) - 1]
    return low, high


def mcnemar(pairs: list[Pair]) -> tuple[int, int, float]:
    only_a = sum(p.a and not p.b for p in pairs)
    only_b = sum(p.b and not p.a for p in pairs)
    return only_a, only_b, exact_binomial_p(only_a, only_b)


def exact_binomial_p(x: int, y: int) -> float:
    n = x + y
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, k) for k in range(min(x, y) + 1)) / 2**n
    return min(1.0, 2 * tail)


def fisher_exact_p(pass_a: int, n_a: int, pass_b: int, n_b: int) -> float:
    total_pass = pass_a + pass_b
    total = n_a + n_b

    def probability(k: int) -> float:
        return (
            math.comb(n_a, k)
            * math.comb(n_b, total_pass - k)
            / math.comb(total, total_pass)
        )

    observed = probability(pass_a)
    low, high = max(0, total_pass - n_b), min(n_a, total_pass)
    return min(
        1.0,
        sum(
            p
            for k in range(low, high + 1)
            if (p := probability(k)) <= observed * (1 + 1e-9)
        ),
    )


def verdict(ci: tuple[float, float], p_value: float) -> str:
    low, high = ci
    if low > 0 and p_value < ALPHA:
        return "B is better"
    if high < 0 and p_value < ALPHA:
        return "A is better"
    if low > 0 or high < 0:
        return "probably different, but the tests disagree; run more trials"
    return "no detectable difference (within noise)"


def summarize_config(trials: list[TrialResult]) -> dict:
    counted = [t for t in trials if t.status != "error"]
    return {
        "trials": len(trials),
        "errors": len(trials) - len(counted),
        "pass_rate": mean(bool(t.passed) for t in counted) if counted else None,
        "mean_score": mean(t.score or 0.0 for t in counted) if counted else None,
        "mean_cost_usd": mean(t.cost_usd for t in counted) if counted else None,
        "total_cost_usd": sum(t.cost_usd for t in trials),
        "mean_latency_ms": mean(t.latency_ms for t in counted) if counted else None,
        "mean_input_tokens": mean(t.input_tokens for t in counted) if counted else None,
        "mean_output_tokens": mean(t.output_tokens for t in counted)
        if counted
        else None,
        "failure_categories": dict(
            Counter(t.failure_category for t in counted if t.failure_category)
        ),
    }


def compare(
    trials: list[TrialResult], config_a: str, config_b: str, seed: int = 0
) -> dict:
    pairs = paired_trials(trials, config_a, config_b)
    deltas = per_task_deltas(pairs)
    report = {
        "config_a": config_a,
        "config_b": config_b,
        "a": summarize_config([t for t in trials if t.config_id == config_a]),
        "b": summarize_config([t for t in trials if t.config_id == config_b]),
        "pairs": len(pairs),
        "tasks": len(deltas),
    }
    if not pairs:
        return report | {"verdict": "no paired trials yet", "per_task": []}
    ci = bootstrap_ci(deltas, seed=seed)
    only_a, only_b, p_value = mcnemar(pairs)
    half_width = (ci[1] - ci[0]) / 2
    return report | {
        "delta": mean_delta(deltas),
        "ci95": list(ci),
        "mcnemar": {
            "only_a_passed": only_a,
            "only_b_passed": only_b,
            "p_value": p_value,
        },
        "verdict": verdict(ci, p_value),
        "detectable_delta": half_width,
        "per_task": task_rows(pairs),
    }


def task_rows(pairs: list[Pair]) -> list[dict]:
    by_task: dict[str, list[Pair]] = defaultdict(list)
    for pair in pairs:
        by_task[pair.task_id].append(pair)
    rows = []
    for task_id, task_pairs in sorted(by_task.items()):
        n = len(task_pairs)
        pass_a = sum(p.a for p in task_pairs)
        pass_b = sum(p.b for p in task_pairs)
        p_value = fisher_exact_p(pass_a, n, pass_b, n)
        rows.append(
            {
                "task_id": task_id,
                "n": n,
                "pass_rate_a": pass_a / n,
                "pass_rate_b": pass_b / n,
                "delta": (pass_b - pass_a) / n,
                "p_value": p_value,
                "signal": task_signal(pass_a, pass_b, n, p_value),
            }
        )
    return sorted(rows, key=lambda r: (-abs(r["delta"]), r["task_id"]))


def task_signal(pass_a: int, pass_b: int, n: int, p_value: float) -> str:
    if pass_a == pass_b == n:
        return "ceiling: both always pass"
    if pass_a == pass_b == 0:
        return "floor: both always fail"
    if p_value < ALPHA:
        return "likely real"
    return "noise"
