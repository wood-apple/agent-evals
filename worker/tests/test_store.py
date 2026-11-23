import dataclasses
import sqlite3

import pytest

from evals.config import Config, Settings
from evals.experiment import Experiment, TrialResult, TrialTrace
from evals.store import Store

CONFIG = Config(harness="baseline", model="m")
EMPTY = TrialTrace(events=[], grades=[])


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path / "evals.db")
    yield store
    store.close()


@pytest.fixture
def experiment(store):
    store.save_config(CONFIG)
    experiment = Experiment(
        id="exp1", name="demo", task_ids=("t1",), config_ids=(CONFIG.id,), n_trials=2
    )
    store.save_experiment(experiment)
    return experiment


def make_result(index=0, status="ok", **fields):
    return TrialResult(
        experiment_id="exp1",
        task_id="t1",
        task_version="v1",
        config_id=CONFIG.id,
        trial_index=index,
        status=status,
        **fields,
    )


def test_config_round_trip_keeps_id(store):
    config = Config(
        harness="baseline",
        model="gemini/gemini-2.5-flash",
        settings=Settings(memory=True, skills=("b", "a")),
        label="memory on",
    )
    store.save_config(config)

    loaded = store.get_config(config.id)
    assert loaded == config
    assert loaded.id == config.id
    assert loaded.label == "memory on"


def test_saving_same_config_twice_keeps_one_row(store):
    config = Config(harness="baseline", model="m")
    store.save_config(config)
    store.save_config(config)
    assert store.conn.execute("select count(*) from configs").fetchone()[0] == 1


def test_unknown_config_raises(store):
    with pytest.raises(KeyError):
        store.get_config("does-not-exist")


def test_reopening_existing_database(tmp_path):
    path = tmp_path / "evals.db"
    Store(path).save_config(Config(harness="baseline", model="m"))
    reopened = Store(path)
    assert reopened.conn.execute("select count(*) from configs").fetchone()[0] == 1


def test_wal_mode_enabled(store):
    assert store.conn.execute("pragma journal_mode").fetchone()[0] == "wal"


def test_trial_and_trace_round_trip(store, experiment):
    result = make_result(passed=True, score=1.0)
    events = [{"type": "message", "role": "user", "content": "hi"}]
    grades = [{"grader": "exact_match", "passed": True}]

    assert store.save_trial(result, TrialTrace(events=events, grades=grades)) is True

    [loaded] = store.get_trials("exp1")
    assert loaded.passed is True
    assert loaded.id == result.id
    assert dataclasses.replace(loaded, finished_at=None) == result
    assert store.get_trace(result.id) == TrialTrace(events=events, grades=grades)


def test_same_trial_is_saved_once(store, experiment):
    store.save_trial(make_result(), EMPTY)
    assert store.save_trial(make_result(), EMPTY) is False
    assert len(store.get_trials("exp1")) == 1


def test_failed_trace_write_rolls_back_trial(store, experiment):
    with pytest.raises(TypeError):
        store.save_trial(make_result(), TrialTrace([{"bad": object()}], []))
    assert store.get_trials("exp1") == []


def test_errored_trials_are_retried_on_resume(store, experiment):
    ok = make_result(index=0, passed=False)
    errored = make_result(index=1, status="error", error="rate limited")
    store.save_trial(ok, EMPTY)
    store.save_trial(errored, EMPTY)

    assert store.finished_trial_ids("exp1") == {ok.id}
    assert store.clear_errored_trials("exp1") == 1
    assert store.save_trial(errored, EMPTY) is True


def test_trial_for_unknown_experiment_is_rejected(store):
    store.save_config(CONFIG)
    with pytest.raises(sqlite3.IntegrityError):
        store.save_trial(make_result(), EMPTY)


def test_lists_become_tuples_and_config_order_is_kept():
    experiment = Experiment(
        id="e", name="n", task_ids=["b", "a"], config_ids=["B", "A"], n_trials=1
    )
    assert experiment.task_ids == ("a", "b")
    assert experiment.config_ids == ("B", "A")


def test_zero_trials_rejected():
    with pytest.raises(ValueError):
        Experiment(id="e", name="n", task_ids=["a"], config_ids=["A"], n_trials=0)


def test_saving_an_experiment_twice_is_a_no_op(store, experiment):
    assert store.save_experiment(experiment) is False


def test_status_of_unknown_experiment_raises(store):
    with pytest.raises(KeyError):
        store.set_experiment_status("nope", "done")


def test_status_round_trip(store, experiment):
    store.set_experiment_status("exp1", "running")
    assert store.get_experiment_status("exp1") == "running"


def test_task_versions_seen_in_trials(store, experiment):
    store.save_trial(make_result(0), EMPTY)
    store.save_trial(dataclasses.replace(make_result(1), task_version="v2"), EMPTY)
    assert store.task_versions("exp1") == {"t1": {"v1", "v2"}}


def test_archive_round_trip(store, experiment):
    store.set_archived("exp1", True)
    store.set_archived("exp1", True)
    assert store.is_archived("exp1")
    store.set_archived("exp1", False)
    assert not store.is_archived("exp1")


def test_archiving_unknown_experiment_raises(store):
    with pytest.raises(KeyError):
        store.set_archived("nope", True)
