from __future__ import annotations

import asyncio
import logging
import tempfile
import time
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from evals.config import Config
from evals.experiment import Experiment, TrialResult, TrialTrace, trial_id
from evals.failures import classify
from evals.graders import Judge, combine, grade_trial
from evals.harness import Harness, HarnessResult, Trace, TrialEnv
from evals.harnesses import get_harness
from evals.store import Store
from evals.task import Task

log = logging.getLogger(__name__)
TIMEOUT_GRACE_S = 15


class ResumeError(Exception):
    pass


@dataclass
class Budget:
    limit_usd: float
    spent_usd: float = 0.0

    @property
    def exhausted(self) -> bool:
        return self.spent_usd >= self.limit_usd


@dataclass
class RunSummary:
    experiment_id: str
    ran: int = 0
    skipped_for_budget: int = 0
    statuses: dict[str, int] = field(default_factory=dict)
    spent_usd: float = 0.0


@dataclass(frozen=True)
class Job:
    task: Task
    config: Config
    trial_index: int


async def run_experiment(
    store: Store,
    experiment: Experiment,
    tasks: dict[str, Task],
    configs: list[Config],
    skills_dir: Path,
    budget: Budget,
    judge: Judge | None = None,
    concurrency: int = 4,
    harness_factory: Callable[[str], Harness] = get_harness,
    on_trial: Callable[[TrialResult], None] | None = None,
) -> RunSummary:
    for config in configs:
        store.save_config(config)
    store.save_experiment(experiment)
    check_task_versions(store, experiment, tasks)
    store.clear_errored_trials(experiment.id)
    done = store.finished_trial_ids(experiment.id)
    jobs = [
        Job(tasks[task_id], config, index)
        for index in range(experiment.n_trials)
        for task_id in experiment.task_ids
        for config in configs
        if trial_id(experiment.id, task_id, config.id, index) not in done
    ]
    store.set_experiment_status(experiment.id, "running")
    summary = RunSummary(experiment.id)
    semaphore = asyncio.Semaphore(concurrency)
    harnesses = {config.harness: harness_factory(config.harness) for config in configs}
    judge = judge or Judge()

    async def worker(job: Job) -> None:
        async with semaphore:
            if budget.exhausted:
                summary.skipped_for_budget += 1
                return
            result, trace = await run_trial(
                experiment, job, harnesses[job.config.harness], skills_dir, judge
            )
            store.save_trial(result, trace)
            judge_cost = sum(
                e.get("cost_usd", 0) for e in trace.events if e["type"] == "grading"
            )
            budget.spent_usd += result.cost_usd + judge_cost
            summary.ran += 1
            summary.statuses[result.status] = summary.statuses.get(result.status, 0) + 1
            if on_trial:
                on_trial(result)

    try:
        await asyncio.gather(*(worker(job) for job in jobs))
    finally:
        summary.spent_usd = budget.spent_usd
        complete = summary.skipped_for_budget == 0 and not summary.statuses.get("error")
        store.set_experiment_status(experiment.id, "done" if complete else "partial")
    return summary


def trial_id_for(
    experiment: Experiment, task_id: str, config: Config, index: int
) -> str:
    return TrialResult(experiment.id, task_id, "", config.id, index, "").id


def check_task_versions(
    store: Store, experiment: Experiment, tasks: dict[str, Task]
) -> None:
    missing = [task_id for task_id in experiment.task_ids if task_id not in tasks]
    if missing:
        raise ResumeError(f"tasks not found: {missing}")
    changed = [
        task_id
        for task_id, versions in store.task_versions(experiment.id).items()
        if task_id in tasks and versions != {tasks[task_id].version}
    ]
    if changed:
        raise ResumeError(
            f"tasks changed since this experiment started: {changed}. "
            "Start a new experiment instead of mixing task versions."
        )


async def run_trial(
    experiment: Experiment, job: Job, harness: Harness, skills_dir: Path, judge: Judge
) -> tuple[TrialResult, TrialTrace]:
    task, config = job.task, job.config
    trace = Trace()
    grades = []
    status, passed, score, error = "ok", None, None, None
    latency_ms = 0
    trial_judge = Judge(judge.model)
    with tempfile.TemporaryDirectory(prefix="trial-") as scratch:
        env = make_env(Path(scratch), task, skills_dir)
        try:
            outcome = await asyncio.wait_for(
                harness.run(task, config, env, trace), task.timeout_s + TIMEOUT_GRACE_S
            )
            latency_ms = elapsed_ms(trace)
            if outcome.stop_reason != "done":
                status, passed, score = "timeout", False, 0.0
            else:
                grades = await grade(task, outcome, env.workdir, trial_judge, trace)
                verdict = combine(grades)
                passed, score = verdict.passed, verdict.score
        except TimeoutError:
            latency_ms = elapsed_ms(trace)
            trace.add("stop", reason="timeout")
            status, passed, score = "timeout", False, 0.0
        except Exception as e:  # noqa: BLE001 - any harness or grader crash is recorded, not raised
            latency_ms = latency_ms or elapsed_ms(trace)
            status, error = "error", f"{type(e).__name__}: {e}"
            trace.add("error", message=error, traceback=traceback.format_exc(limit=5))
            log.warning(
                "trial %s/%s/%d errored: %s",
                task.id,
                config.label or config.id,
                job.trial_index,
                error,
            )
    result = TrialResult(
        experiment_id=experiment.id,
        task_id=task.id,
        task_version=task.version,
        config_id=config.id,
        trial_index=job.trial_index,
        status=status,
        passed=passed,
        score=score,
        input_tokens=trace.input_tokens,
        output_tokens=trace.output_tokens,
        cost_usd=round(trace.cost_usd, 6),
        latency_ms=latency_ms,
        error=error,
        failure_category=classify(
            status, passed, trace.events, grades, task.expected_tools
        ),
        finished_at=datetime.now(UTC).isoformat(),
    )
    return result, TrialTrace(events=trace.events, grades=[asdict(g) for g in grades])


async def grade(
    task: Task, outcome: HarnessResult, workdir: Path, judge: Judge, trace: Trace
):
    grades = await grade_trial(task, outcome.final_answer, workdir, judge)
    trace.add(
        "grading",
        answer=outcome.final_answer,
        files=sorted(
            p.relative_to(workdir).as_posix() for p in workdir.rglob("*") if p.is_file()
        ),
        cost_usd=judge.cost_usd,
    )
    return grades


def make_env(scratch: Path, task: Task, skills_dir: Path) -> TrialEnv:
    workdir = scratch / "work"
    state = scratch / "state"
    state.mkdir()
    workdir.mkdir()
    for path, text in task.fixtures.items():
        target = workdir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
    return TrialEnv(workdir=workdir, state_dir=state, skills_dir=skills_dir)


def elapsed_ms(trace: Trace) -> int:
    return int((time.monotonic() - trace.started) * 1000)
