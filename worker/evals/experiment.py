from __future__ import annotations

from dataclasses import dataclass

from evals.hashing import content_hash


@dataclass(frozen=True)
class Experiment:
    id: str
    name: str
    task_ids: tuple[str, ...]
    config_ids: tuple[str, ...]
    n_trials: int
    seed: int = 0

    def __post_init__(self):
        object.__setattr__(self, "task_ids", tuple(sorted(self.task_ids)))
        object.__setattr__(self, "config_ids", tuple(self.config_ids))
        if self.n_trials < 1:
            raise ValueError("n_trials must be at least 1")


@dataclass(frozen=True)
class TrialResult:
    experiment_id: str
    task_id: str
    task_version: str
    config_id: str
    trial_index: int
    status: str
    passed: bool | None = None
    score: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: int = 0
    error: str | None = None
    failure_category: str | None = None
    finished_at: str | None = None

    @property
    def id(self) -> str:
        return trial_id(
            self.experiment_id,
            self.task_id,
            self.config_id,
            self.trial_index,
        )


@dataclass(frozen=True)
class TrialTrace:
    events: list[dict]
    grades: list[dict]


def trial_id(experiment_id: str, task_id: str, config_id: str, trial_index: int) -> str:
    return content_hash(
        {
            "experiment_id": experiment_id,
            "task_id": task_id,
            "config_id": config_id,
            "trial_index": trial_index,
        }
    )
