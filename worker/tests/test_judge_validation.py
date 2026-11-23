import pytest

from evals.judge_validation import cohens_kappa, validate
from evals.task import Task

TASK = Task(
    id="t",
    title="t",
    category="c",
    sessions=("q",),
    graders=({"type": "llm_judge", "rubric": "r"},),
)


def test_kappa_perfect_and_chance():
    assert cohens_kappa([True, False, True, False], [True, False, True, False]) == 1.0
    assert cohens_kappa([True, True, False, False], [True, False, True, False]) == 0.0


def test_kappa_when_everyone_agrees_on_one_class():
    assert cohens_kappa([True, True], [True, True]) == 1.0


class KeywordJudge:
    class model:
        name = "fake"

    cost_usd = 0.0

    async def grade(self, task, spec, response):
        passed = "good" in response
        return passed, 1.0 if passed else 0.0, "keyword"


async def test_validate_reports_disagreements():
    labels = [
        {"id": "1", "task_id": "t", "response": "good", "human_pass": True},
        {"id": "2", "task_id": "t", "response": "bad", "human_pass": False},
        {"id": "3", "task_id": "t", "response": "good but leaks", "human_pass": False},
    ]
    result = await validate(labels, {"t": TASK}, KeywordJudge())
    assert result["agreement"] == pytest.approx(2 / 3)
    assert result["confusion"]["judge_too_lenient"] == 1
    assert [d["id"] for d in result["disagreements"]] == ["3"]


class FlakyJudge(KeywordJudge):
    async def grade(self, task, spec, response):
        if response == "boom":
            from evals.model import ModelError

            raise ModelError("rate limited")
        return await super().grade(task, spec, response)


async def test_judge_failures_are_reported_not_fatal():
    labels = [
        {"id": "1", "task_id": "t", "response": "good", "human_pass": True},
        {"id": "2", "task_id": "t", "response": "boom", "human_pass": False},
    ]
    result = await validate(labels, {"t": TASK}, FlakyJudge())
    assert result["n"] == 1
    assert result["failed"] == ["2: rate limited"]
