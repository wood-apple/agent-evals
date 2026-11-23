import csv
import json

import pytest

from evals.config import Config, Settings
from evals.experiment import Experiment, TrialResult, TrialTrace
from evals.export import export_csv, export_json
from evals.store import Store

CONFIG = Config(
    harness="baseline",
    model="m",
    settings=Settings(skills=("b", "a")),
    label="with skills",
)


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path / "evals.db")
    store.save_config(CONFIG)
    store.save_experiment(
        Experiment(
            id="exp1",
            name="demo",
            task_ids=("t1",),
            config_ids=(CONFIG.id,),
            n_trials=2,
        )
    )
    for index, passed in enumerate([True, False]):
        result = TrialResult(
            experiment_id="exp1",
            task_id="t1",
            task_version="v1",
            config_id=CONFIG.id,
            trial_index=index,
            status="ok",
            passed=passed,
        )
        store.save_trial(result, TrialTrace(events=[{"step": index}], grades=[]))
    yield store
    store.close()


def test_json_records_carry_full_context(store, tmp_path):
    path = tmp_path / "out.json"
    export_json(store, "exp1", path)
    records = json.loads(path.read_text())
    assert [r["passed"] for r in records] == [True, False]
    first = records[0]
    assert first["experiment_name"] == "demo"
    assert first["config_label"] == "with skills"
    assert first["settings.skills"] == ["a", "b"]
    assert "trace" not in first


def test_json_export_can_include_traces(store, tmp_path):
    path = tmp_path / "out.json"
    export_json(store, "exp1", path, include_traces=True)
    records = json.loads(path.read_text())
    assert [r["trace"]["events"] for r in records] == [[{"step": 0}], [{"step": 1}]]


def test_csv_and_json_have_the_same_columns(store, tmp_path):
    export_json(store, "exp1", tmp_path / "out.json")
    export_csv(store, "exp1", tmp_path / "out.csv")
    json_records = json.loads((tmp_path / "out.json").read_text())
    with (tmp_path / "out.csv").open(newline="") as f:
        csv_rows = list(csv.DictReader(f))
    assert len(csv_rows) == len(json_records)
    assert list(csv_rows[0]) == list(json_records[0])
    assert csv_rows[0]["settings.skills"] == "a;b"


def test_empty_experiment_gives_empty_csv(store, tmp_path):
    store.save_experiment(
        Experiment(
            id="exp2",
            name="empty",
            task_ids=("t1",),
            config_ids=(CONFIG.id,),
            n_trials=1,
        )
    )
    path = tmp_path / "out.csv"
    export_csv(store, "exp2", path)
    assert path.read_text() == ""


def test_unknown_experiment_raises(store, tmp_path):
    with pytest.raises(KeyError, match="nope"):
        export_json(store, "nope", tmp_path / "out.json")
