import json
from pathlib import Path

import pytest

from evals.task_loader import TaskLoadError, load_task, load_tasks

TASKS_DIR = Path(__file__).parents[2] / "tasks"


def write_task(root, task_id="demo", **overrides):
    task_dir = root / task_id
    task_dir.mkdir()
    spec = {
        "id": task_id,
        "title": "Demo",
        "category": "data",
        "sessions": [
            {"prompt": "Remember X"},
            {"prompt": "Use X"},
        ],
        "graders": [
            {"type": "exact_match", "expected": "X"},
        ],
        **overrides,
    }
    (task_dir / "task.json").write_text(json.dumps(spec))
    return task_dir


def test_load_session_fixtures_and_grading_files(tmp_path):
    task_dir = write_task(tmp_path)
    (task_dir / "fixtures" / "data").mkdir(parents=True)
    (task_dir / "fixtures" / "data" / "a.csv").write_text("x,y\n")
    (task_dir / "fixtures" / "data" / ".DS_STORE").write_text("junk")
    (task_dir / "tests").mkdir()
    (task_dir / "tests" / "test_demo.py").write_text("assert True\n")

    task = load_task(task_dir)
    assert task.fixtures == {"data/a.csv": "x,y\n"}
    assert task.sessions == ("Remember X", "Use X")
    assert task.grading_files == {"tests/test_demo.py": "assert True\n"}


def test_invalid_task_json(tmp_path):
    task_dir = write_task(tmp_path)
    (task_dir / "task.json").write_text("{not json")
    with pytest.raises(TaskLoadError, match="invalid JSON"):
        load_task(task_dir)


def test_missing_required_keys(tmp_path):
    task_dir = write_task(tmp_path)
    spec = json.loads((task_dir / "task.json").read_text())
    del spec["title"]
    (task_dir / "task.json").write_text(json.dumps(spec))
    with pytest.raises(TaskLoadError, match="title"):
        load_task(task_dir)


def test_id_must_match_folder(tmp_path):
    task_dir = write_task(tmp_path, id="other_id")
    with pytest.raises(TaskLoadError, match="does not match"):
        load_task(task_dir)


def test_can_load_tasks_from_dir():
    tasks = load_tasks(TASKS_DIR)
    assert len(tasks) >= 20
    assert len({task.id for task in tasks}) == len(tasks)


def test_missing_task_json(tmp_path):
    (tmp_path / "empty").mkdir()
    with pytest.raises(TaskLoadError, match="missing task.json"):
        load_task(tmp_path / "empty")
