import pytest

from evals.config import Config, Settings
from evals.store import Store


@pytest.fixture
def store(tmp_path):
    store = Store(tmp_path / "evals.db")
    yield store
    store.close()


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
