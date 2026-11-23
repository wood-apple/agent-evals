import json

import pytest

from evals import cli
from evals.graders import Judge
from evals.harness import HarnessResult


class AnswerHarness:
    async def run(self, task, config, env, trace):
        trace.count_usage(10, 5, 0.0)
        return HarnessResult(("ANSWER: 3",))


@pytest.fixture
def db(tmp_path, monkeypatch):
    monkeypatch.setattr("evals.runner.get_harness", lambda name: AnswerHarness())
    monkeypatch.setattr(
        "evals.cli.run_experiment",
        lambda *args, **kwargs: cli_run(*args, **kwargs),
    )
    return tmp_path / "evals.db"


def cli_run(*args, **kwargs):
    from evals.runner import run_experiment

    return run_experiment(*args, harness_factory=lambda name: AnswerHarness(), **kwargs)


def config_file(tmp_path, model):
    path = tmp_path / f"{model}.json"
    path.write_text(
        json.dumps({"harness": "baseline", "model": f"fake/{model}", "label": model})
    )
    return str(path)


def test_run_compare_and_export(db, tmp_path, capsys):
    a, b = config_file(tmp_path, "a"), config_file(tmp_path, "b")
    args = [
        "--db",
        str(db),
        "run",
        "--name",
        "t",
        "--config",
        a,
        "--config",
        b,
        "--tasks",
        "json-config-lookup",
        "--trials",
        "2",
    ]
    assert cli.main(args) == 0
    lines = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert lines[0]["event"] == "start"
    assert lines[0]["judge_model"] == Judge().model.name
    assert lines[-1]["statuses"] == {"ok": 4}
    experiment = lines[0]["experiment_id"]

    assert cli.main(args) == 0
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["ran"] == 0

    cli.main(["--db", str(db), "compare", experiment, "--json"])
    report = json.loads(capsys.readouterr().out)
    assert report["pairs"] == 2
    assert report["verdict"] == "no detectable difference (within noise)"

    out = tmp_path / "out.csv"
    cli.main(
        ["--db", str(db), "export", experiment, "--format", "csv", "--out", str(out)]
    )
    assert len(out.read_text().splitlines()) == 5


def test_unknown_task_is_rejected(db, tmp_path, capsys):
    code = cli.main(
        [
            "--db",
            str(db),
            "run",
            "--name",
            "t",
            "--config",
            config_file(tmp_path, "a"),
            "--tasks",
            "nope",
        ]
    )
    assert code == 2
    assert "unknown tasks" in capsys.readouterr().err


def test_config_add_prints_the_id(db, tmp_path, capsys):
    cli.main(["--db", str(db), "config", "add", config_file(tmp_path, "a")])
    saved = json.loads(capsys.readouterr().out)
    cli.main(["--db", str(db), "config", "list"])
    assert [c["id"] for c in json.loads(capsys.readouterr().out)] == [saved["id"]]
