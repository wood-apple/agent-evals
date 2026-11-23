from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, dataclass
from pathlib import Path

from evals.graders import GraderError, Judge
from evals.model import ModelError
from evals.task import Task


@dataclass(frozen=True)
class Item:
    id: str
    task_id: str
    response: str
    human_pass: bool
    judge_pass: bool
    judge_score: int
    reasoning: str


def load_labels(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


async def validate(
    labels: list[dict], tasks: dict[str, Task], judge: Judge, concurrency: int = 4
) -> dict:
    semaphore = asyncio.Semaphore(concurrency)

    async def judge_one(label: dict) -> Item | str:
        task = tasks[label["task_id"]]
        spec = next(g for g in task.graders if g["type"] == "llm_judge")
        async with semaphore:
            try:
                passed, score, reasoning = await judge.grade(
                    task, spec, label["response"]
                )
            except (ModelError, GraderError) as e:
                return f"{label['id']}: {e}"[:300]
        return Item(
            id=label["id"],
            task_id=task.id,
            response=label["response"],
            human_pass=label["human_pass"],
            judge_pass=passed,
            judge_score=round(score * 4 + 1),
            reasoning=reasoning,
        )

    results = await asyncio.gather(*(judge_one(label) for label in labels))
    items = [r for r in results if isinstance(r, Item)]
    return report(items, judge) | {"failed": [r for r in results if isinstance(r, str)]}


def report(items: list[Item], judge: Judge) -> dict:
    confusion = {
        "both_pass": sum(i.human_pass and i.judge_pass for i in items),
        "both_fail": sum(not i.human_pass and not i.judge_pass for i in items),
        "judge_too_lenient": sum(not i.human_pass and i.judge_pass for i in items),
        "judge_too_strict": sum(i.human_pass and not i.judge_pass for i in items),
    }
    return {
        "judge_model": judge.model.name,
        "n": len(items),
        "agreement": (confusion["both_pass"] + confusion["both_fail"]) / len(items),
        "kappa": cohens_kappa(
            [i.human_pass for i in items], [i.judge_pass for i in items]
        ),
        "confusion": confusion,
        "cost_usd": judge.cost_usd,
        "disagreements": [asdict(i) for i in items if i.human_pass != i.judge_pass],
        "items": [asdict(i) for i in items],
    }


def cohens_kappa(a: list[bool], b: list[bool]) -> float:
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    p_a, p_b = sum(a) / n, sum(b) / n
    expected = p_a * p_b + (1 - p_a) * (1 - p_b)
    if expected == 1:
        return 1.0
    return (observed - expected) / (1 - expected)
