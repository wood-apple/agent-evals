from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from evals.config import Config
from evals.task import Task


@dataclass(frozen=True)
class TrialEnv:
    workdir: Path
    state_dir: Path
    skills_dir: Path


@dataclass
class Trace:
    events: list[dict] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    started: float = field(default_factory=time.monotonic)

    def add(self, type: str, **data) -> None:
        elapsed_ms = int((time.monotonic() - self.started) * 1000)
        self.events.append({"type": type, "t_ms": elapsed_ms, **data})

    def count_usage(
        self, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> None:
        self.input_tokens += input_tokens
        self.output_tokens += output_tokens
        self.cost_usd += cost_usd

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class HarnessResult:
    answers: tuple[str, ...]
    stop_reason: str = "done"

    @property
    def final_answer(self) -> str:
        return self.answers[-1] if self.answers else ""


class Harness(Protocol):
    async def run(
        self, task: Task, config: Config, env: TrialEnv, trace: Trace
    ) -> HarnessResult: ...
