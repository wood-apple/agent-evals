import dataclasses

import pytest

from evals.config import Config, Settings


def make_config(**settings):
    return Config(
        harness="baseline",
        model="gemini/gemini-2.5-flash",
        settings=Settings(**settings),
    )


def test_same_settings_give_same_id():
    assert make_config().id == make_config().id


def test_any_settings_change_gives_new_id():
    base = make_config()
    assert base.id != dataclasses.replace(base, model="groq/llama-3.3-70b-versatile").id
    assert base.id != make_config(temperature=0.3).id
    assert base.id != make_config(memory=True).id


def test_label_does_not_affect_id():
    a = dataclasses.replace(make_config(), label="label-a")
    b = dataclasses.replace(make_config(), label="label-b")
    assert a.id == b.id


def test_config_is_immutable():
    config = make_config()
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.model = "other"
    with pytest.raises(dataclasses.FrozenInstanceError):
        config.settings.temperature = 1.0


def test_skill_order_does_not_affect_id():
    assert make_config(skills=("a", "b")).id == make_config(skills=("b", "a")).id


def test_int_and_float_temperature_gives_same_id():
    assert make_config(temperature=0.0).id == make_config(temperature=0).id


def test_list_inputs_are_stored_as_tuples():
    config = make_config(skills=["a", "b"], tools=["A", "B"])
    assert config.settings.skills == ("a", "b")
    assert config.settings.tools == ("A", "B")
    hash(config)
