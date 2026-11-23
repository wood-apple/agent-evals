import shutil
from pathlib import Path

import pytest

from evals.graders import combine, grade_trial
from evals.task_loader import load_tasks

TASKS = load_tasks(Path(__file__).parents[2] / "tasks")


class ApprovingJudge:
    async def grade(self, task, spec, response):
        return True, 1.0, "approved"


class RejectingJudge:
    async def grade(self, task, spec, response):
        return False, 0.0, "rejected"


def seed(workdir: Path, files: dict[str, str]) -> None:
    for path, text in files.items():
        target = workdir / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)


def reference(task):
    answer = task.grading_files.get("reference/answer.txt", "")
    files = {
        path.removeprefix("reference/"): text
        for path, text in task.grading_files.items()
        if path.startswith("reference/") and path != "reference/answer.txt"
    }
    return answer, files


def test_task_set_is_big_enough_and_mixed():
    assert len(TASKS) >= 20
    types = {spec["type"] for task in TASKS for spec in task.graders}
    assert {"exact_match", "unit_tests", "file_state", "llm_judge"} <= types


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
async def test_reference_solution_passes(task, tmp_path):
    answer, files = reference(task)
    seed(tmp_path, task.fixtures)
    seed(tmp_path, files)
    verdict = combine(await grade_trial(task, answer, tmp_path, ApprovingJudge()))
    assert verdict.passed


@pytest.mark.parametrize("task", TASKS, ids=lambda t: t.id)
async def test_untouched_fixtures_fail(task, tmp_path):
    seed(tmp_path, task.fixtures)
    verdict = combine(
        await grade_trial(task, "I could not finish this.", tmp_path, RejectingJudge())
    )
    assert not verdict.passed


def test_reference_files_do_not_leak_into_fixtures():
    for task in TASKS:
        assert not any(
            path.startswith(("reference/", "tests/")) for path in task.fixtures
        ), task.id
    assert shutil.which("python3")
