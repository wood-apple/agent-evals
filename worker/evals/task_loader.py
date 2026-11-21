import json
from pathlib import Path

from evals.task import Task

REQUIRED_KEYS = ("id", "title", "category", "sessions", "graders")
GRADING_DIRS = ("tests", "reference")


class TaskLoadError(Exception):
    pass


def load_tasks(root: Path) -> list[Task]:
    task_dirs = sorted(root.iterdir())
    return [load_task(d) for d in task_dirs if d.is_dir()]


def load_task(task_dir: Path) -> Task:
    spec_path = task_dir / "task.json"
    try:
        spec = json.loads(spec_path.read_text())
    except FileNotFoundError:
        raise TaskLoadError(f"{task_dir}: missing task.json") from None
    except json.JSONDecodeError as e:
        raise TaskLoadError(f"{spec_path}: invalid JSON ({e})") from e

    missing_keys = [key for key in REQUIRED_KEYS if key not in spec]
    if missing_keys:
        raise TaskLoadError(f"{spec_path}: missing keys {missing_keys}")

    if spec["id"] != task_dir.name:
        raise TaskLoadError(
            f"{spec_path}: id {spec['id']!r} does not match folder name"
        )

    return Task(
        id=spec["id"],
        title=spec["title"],
        category=spec["category"],
        sessions=[session["prompt"] for session in spec["sessions"]],
        graders=spec["graders"],
        timeout_s=spec.get("timeout_s", 300),
        expected_tools=spec.get("expected_tools", []),
        fixtures=read_tree(task_dir / "fixtures"),
        grading_files={
            f"{name}/{path}": text
            for name in GRADING_DIRS
            for path, text in read_tree(task_dir / name).items()
        },
    )


def read_tree(directory: Path) -> dict[str, str]:
    if not directory.is_dir():
        return {}
    return {
        path.relative_to(directory).as_posix(): path.read_text()
        for path in sorted(directory.rglob("*"))
        if path.is_file() and not path.name.startswith(".")
    }
