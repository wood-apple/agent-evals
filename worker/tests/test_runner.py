import asyncio
import dataclasses

import pytest

from evals.config import Config, Settings
from evals.experiment import Experiment
from evals.graders import DEFAULT_JUDGE_MODEL, Judge
from evals.harness import HarnessResult
from evals.runner import Budget, ResumeError, run_experiment
from evals.store import Store
from evals.task import Task

ANSWER_TASK = Task(
    id="answer",
    title="answer",
    category="c",
    sessions=("What is 6 x 7?",),
    graders=({"type": "exact_match", "expected": "42"},),
)
FILE_TASK = Task(
    id="file",
    title="file",
    category="c",
    sessions=("Write out.txt",),
    graders=(
        {"type": "file_state", "checks": [{"path": "out.txt", "equals": "done"}]},
    ),
    fixtures={"in.txt": "hello"},
)
TASKS = {t.id: t for t in (ANSWER_TASK, FILE_TASK)}
A = Config("scripted", "good", Settings(), label="A")
B = Config("scripted", "bad", Settings(), label="B")


class ScriptedHarness:
    def __init__(self, behaviour):
        self.behaviour = behaviour
        self.calls = []

    async def run(self, task, config, env, trace):
        self.calls.append((task.id, config.label))
        trace.count_usage(100, 10, 0.01)
        trace.add("model_response", session=0, step=0, text="", tool_calls=[])
        return await self.behaviour(task, config, env, trace)


async def solve(task, config, env, trace):
    seen = sorted(p.name for p in env.workdir.iterdir())
    assert seen == sorted(task.fixtures), "leaked state from another trial"
    (env.workdir / "leak.txt").write_text("x")
    if config.model == "good":
        (env.workdir / "out.txt").write_text("done")
        return HarnessResult(("ANSWER: 42",))
    return HarnessResult(("ANSWER: 41",))


async def no_sleep(_):
    pass


class NoJudge:
    model = None


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path / "evals.db")
    yield store
    store.close()


def experiment(n_trials=2, task_ids=("answer", "file")):
    return Experiment(
        id="exp",
        name="demo",
        task_ids=task_ids,
        config_ids=(A.id, B.id),
        n_trials=n_trials,
    )


async def run(
    store, harness, budget=10.0, exp=None, tasks=TASKS, tmp_path=None, **kwargs
):
    return await run_experiment(
        store,
        exp or experiment(),
        tasks,
        [A, B],
        skills_dir=tmp_path,
        budget=Budget(budget),
        judge=Judge(NoJudge.model),
        harness_factory=lambda name: harness,
        **{"sleep": no_sleep, "trial_attempts": 1} | kwargs,
    )


async def test_runs_every_task_config_and_trial(store, tmp_path):
    harness = ScriptedHarness(solve)
    summary = await run(store, harness, tmp_path=tmp_path)
    trials = store.get_trials("exp")
    assert summary.ran == len(trials) == 8
    assert {(t.config_id == A.id, t.passed) for t in trials} == {
        (True, True),
        (False, False),
    }
    assert all(t.status == "ok" and t.input_tokens == 100 for t in trials)
    assert summary.spent_usd == pytest.approx(0.08)
    assert store.get_experiment_status("exp") == "done"


async def test_trial_order_keeps_configs_paired(store, tmp_path):
    harness = ScriptedHarness(solve)
    await run(store, harness, tmp_path=tmp_path, concurrency=1)
    assert harness.calls[:4] == [
        ("answer", "A"),
        ("answer", "B"),
        ("file", "A"),
        ("file", "B"),
    ]


async def test_rerun_resumes_without_repeating_work(store, tmp_path):
    harness = ScriptedHarness(solve)
    await run(store, harness, tmp_path=tmp_path)
    summary = await run(store, harness, tmp_path=tmp_path)
    assert summary.ran == 0
    assert len(harness.calls) == 8


async def test_errors_are_recorded_and_retried_on_resume(store, tmp_path):
    async def flaky(task, config, env, trace):
        if config.label == "B":
            raise ConnectionError("provider down")
        return await solve(task, config, env, trace)

    summary = await run(store, ScriptedHarness(flaky), tmp_path=tmp_path)
    assert summary.statuses == {"ok": 4, "error": 4}
    assert store.get_experiment_status("exp") == "partial"
    errored = [t for t in store.get_trials("exp") if t.status == "error"]
    assert errored[0].error == "ConnectionError: provider down"
    assert store.get_trace(errored[0].id).events[-1]["type"] == "error"

    summary = await run(store, ScriptedHarness(solve), tmp_path=tmp_path)
    assert summary.ran == 4
    assert store.get_experiment_status("exp") == "done"


async def test_timeouts_count_as_failures(store, tmp_path, monkeypatch):
    async def slow(task, config, env, trace):
        await asyncio.sleep(5)

    fast_tasks = {k: dataclasses.replace(t, timeout_s=0) for k, t in TASKS.items()}
    monkeypatch.setattr("evals.runner.TIMEOUT_GRACE_S", 0.05)
    await run(
        store,
        ScriptedHarness(slow),
        exp=experiment(1),
        tasks=fast_tasks,
        tmp_path=tmp_path,
    )
    trials = store.get_trials("exp")
    assert {(t.status, t.passed, t.failure_category) for t in trials} == {
        ("timeout", False, "timeout")
    }


async def test_step_limit_counts_as_step_exhaustion(store, tmp_path):
    async def loops(task, config, env, trace):
        trace.add("stop", session=0, reason="max_steps")
        return HarnessResult(("",), "max_steps")

    await run(store, ScriptedHarness(loops), exp=experiment(1), tmp_path=tmp_path)
    assert {t.failure_category for t in store.get_trials("exp")} == {"step_exhaustion"}


async def test_budget_stops_new_trials(store, tmp_path):
    summary = await run(
        store, ScriptedHarness(solve), budget=0.025, tmp_path=tmp_path, concurrency=1
    )
    assert summary.ran == 3
    assert summary.skipped_for_budget == 5
    assert store.get_experiment_status("exp") == "partial"


async def test_resume_refuses_changed_tasks(store, tmp_path):
    await run(store, ScriptedHarness(solve), tmp_path=tmp_path)
    edited = {
        **TASKS,
        "answer": dataclasses.replace(ANSWER_TASK, sessions=("What is 6 x 8?",)),
    }
    with pytest.raises(ResumeError, match="answer"):
        await run(store, ScriptedHarness(solve), tasks=edited, tmp_path=tmp_path)


async def test_missing_task_is_rejected(store, tmp_path):
    with pytest.raises(ResumeError, match="not found"):
        await run(
            store,
            ScriptedHarness(solve),
            exp=experiment(task_ids=("answer", "gone")),
            tmp_path=tmp_path,
        )


async def test_trace_records_grading(store, tmp_path):
    await run(store, ScriptedHarness(solve), exp=experiment(1), tmp_path=tmp_path)
    trial = next(t for t in store.get_trials("exp") if t.task_id == "file" and t.passed)
    trace = store.get_trace(trial.id)
    grading = trace.events[-1]
    assert grading["type"] == "grading"
    assert grading["files"] == ["in.txt", "leak.txt", "out.txt"]
    assert trace.grades[0]["reasoning"] == "all file checks passed"


async def test_grading_event_records_the_judge_model(store, tmp_path):
    await run(store, ScriptedHarness(solve), exp=experiment(1), tmp_path=tmp_path)
    trial = store.get_trials("exp")[0]
    assert store.get_trace(trial.id).events[-1]["judge_model"] == DEFAULT_JUDGE_MODEL


async def test_timeout_spent_waiting_on_rate_limits_is_an_infra_error(
    store, tmp_path, monkeypatch
):
    from evals.model import rate_limit_wait_s

    async def throttled(task, config, env, trace):
        rate_limit_wait_s.get().append(30.0)
        await asyncio.sleep(5)

    fast_tasks = {k: dataclasses.replace(t, timeout_s=0) for k, t in TASKS.items()}
    monkeypatch.setattr("evals.runner.TIMEOUT_GRACE_S", 0.05)
    await run(
        store,
        ScriptedHarness(throttled),
        exp=experiment(1),
        tasks=fast_tasks,
        tmp_path=tmp_path,
    )
    trials = store.get_trials("exp")
    assert {t.status for t in trials} == {"error"}
    assert "rate limits" in trials[0].error


async def test_infra_errors_are_retried_with_a_fresh_sandbox(store, tmp_path):
    calls = []

    async def flaky_once(task, config, env, trace):
        calls.append((task.id, config.label))
        if calls.count((task.id, config.label)) == 1:
            (env.workdir / "half-done.txt").write_text("x")
            raise ConnectionError("gateway disconnected")
        return await solve(task, config, env, trace)

    summary = await run(
        store,
        ScriptedHarness(flaky_once),
        exp=experiment(1),
        tmp_path=tmp_path,
        trial_attempts=3,
    )
    assert summary.statuses == {"ok": 4}
    assert len(calls) == 8
    trial = store.get_trials("exp")[0]
    first = store.get_trace(trial.id).events[0]
    assert first == {
        "type": "retried",
        "attempts": 2,
        "errors": ["ConnectionError: gateway disconnected"],
    }


async def test_retries_give_up_after_the_last_attempt(store, tmp_path):
    async def always_down(task, config, env, trace):
        raise ConnectionError("down")

    delays = []

    async def record(seconds):
        delays.append(seconds)

    await run(
        store,
        ScriptedHarness(always_down),
        exp=experiment(1, task_ids=("answer",)),
        tmp_path=tmp_path,
        trial_attempts=3,
        sleep=record,
        retry_base_s=10.0,
    )
    assert {t.status for t in store.get_trials("exp")} == {"error"}
    assert len(delays) == 4
    assert all(5 <= d <= 15 for d in delays[::2]) and all(
        10 <= d <= 30 for d in delays[1::2]
    )
