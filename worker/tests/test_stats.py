import pytest

from evals.experiment import TrialResult
from evals.stats import (
    Pair,
    bootstrap_ci,
    compare,
    exact_binomial_p,
    fisher_exact_p,
    mcnemar,
    paired_trials,
    verdict,
)


def trial(task, config, index, passed, status="ok", **fields):
    return TrialResult("e", task, "v", config, index, status, passed=passed, **fields)


def test_pairs_match_task_and_trial_index_and_skip_errors():
    trials = [
        trial("t1", "A", 0, True),
        trial("t1", "B", 0, False),
        trial("t1", "A", 1, True),
        trial("t1", "B", 1, None, status="error"),
        trial("t2", "A", 0, False, status="timeout"),
        trial("t2", "B", 0, True),
    ]
    assert paired_trials(trials, "A", "B") == [
        Pair("t1", 0, True, False),
        Pair("t2", 0, False, True),
    ]


def test_exact_binomial_matches_known_values():
    assert exact_binomial_p(0, 0) == 1.0
    assert exact_binomial_p(0, 5) == pytest.approx(2 / 32)
    assert exact_binomial_p(1, 9) == pytest.approx(0.021484375)
    assert exact_binomial_p(5, 5) == 1.0


def test_fisher_exact_matches_scipy_values():
    assert fisher_exact_p(5, 5, 0, 5) == pytest.approx(0.007937, abs=1e-6)
    assert fisher_exact_p(5, 5, 1, 5) == pytest.approx(0.047619, abs=1e-6)
    assert fisher_exact_p(3, 5, 3, 5) == pytest.approx(1.0)


def test_mcnemar_counts_discordant_pairs():
    pairs = [
        Pair("t", i, a, b)
        for i, (a, b) in enumerate([(1, 1), (1, 0), (0, 1), (0, 1), (0, 0)])
    ]
    assert mcnemar(pairs)[:2] == (1, 2)


def test_bootstrap_ci_is_reproducible_and_brackets_the_mean():
    deltas = {f"t{i}": [1.0, 0.0, 1.0] if i % 2 else [0.0, 0.0, 0.0] for i in range(10)}
    low, high = bootstrap_ci(deltas, iterations=2000, seed=1)
    assert (low, high) == bootstrap_ci(deltas, iterations=2000, seed=1)
    assert low < 1 / 3 < high


def test_identical_configs_are_called_noise():
    trials = [
        trial(f"t{t}", config, i, (t + i) % 2 == 0)
        for t in range(10)
        for i in range(4)
        for config in ("A", "B")
    ]
    report = compare(trials, "A", "B")
    assert report["delta"] == 0
    assert report["verdict"] == "no detectable difference (within noise)"


def test_clear_improvement_is_detected():
    trials = [trial(f"t{t}", "A", i, t < 3) for t in range(12) for i in range(3)]
    trials += [trial(f"t{t}", "B", i, t < 10) for t in range(12) for i in range(3)]
    report = compare(trials, "A", "B")
    assert report["delta"] == pytest.approx(7 / 12)
    assert report["ci95"][0] > 0
    assert report["verdict"] == "B is better"
    top = report["per_task"][0]
    assert top["delta"] == 1.0
    assert top["signal"] == "noise"


def test_one_task_flip_needs_five_trials_to_count():
    trials = [trial("t", "A", i, False) for i in range(5)] + [
        trial("t", "B", i, True) for i in range(5)
    ]
    assert compare(trials, "A", "B")["per_task"][0]["signal"] == "likely real"


def test_ceiling_tasks_are_flagged():
    trials = [trial("easy", c, i, True) for c in "AB" for i in range(3)]
    trials += [trial("hard", c, i, i == 0) for c in "AB" for i in range(3)]
    rows = {r["task_id"]: r["signal"] for r in compare(trials, "A", "B")["per_task"]}
    assert rows == {"easy": "ceiling: both always pass", "hard": "noise"}


def test_verdict_when_tests_disagree():
    assert verdict((0.01, 0.2), 0.2).startswith("probably different")


def test_config_summary_reports_cost_and_errors():
    trials = [
        trial("t", "A", 0, True, cost_usd=0.02, latency_ms=100, input_tokens=10),
        trial("t", "A", 1, None, status="error", cost_usd=0.01),
        trial("t", "B", 0, False, failure_category="wrong_tool"),
    ]
    report = compare(trials, "A", "B")
    assert report["a"]["errors"] == 1
    assert report["a"]["pass_rate"] == 1.0
    assert report["a"]["total_cost_usd"] == pytest.approx(0.03)
    assert report["b"]["failure_categories"] == {"wrong_tool": 1}


def test_no_pairs_yet():
    assert compare([], "A", "B")["verdict"] == "no paired trials yet"


def test_concentrated_effect_is_not_called_noise():
    text = verdict((0.0, 0.216), 1e-4, 0.096)
    assert text.startswith("B is better on the tasks that differ")
    assert "includes 0" in text
    assert verdict((-0.2, 0.0), 1e-4, -0.1).startswith("A is better on the tasks")
