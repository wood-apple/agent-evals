from evals.task import Task


def make_task(**overrides):
    fields = {
        "id": "csv-revenue-west",
        "title": "Total revenue for one region",
        "category": "data",
        "sessions": ["What is the West revenue?"],
        "graders": [{"type": "numeric", "expected": 9340.07, "tolerance": 0.011}],
        "fixtures": {"sales.csv": "region,units,unit_price\nWest,2,10.5\n"},
    }
    return Task(**{**fields, **overrides})


def test_version_is_stable():
    assert make_task().version == make_task().version


def test_editing_prompt_changes_version():
    assert (
        make_task().version != make_task(sessions=["What is the East revenue?"]).version
    )


def test_editing_graders_changes_version():
    assert (
        make_task().version
        != make_task(
            graders=[{"type": "numeric", "expected": 1.0, "tolerance": 0.01}]
        ).version
    )


def test_metadata_does_not_change_version():
    changed = make_task(id="new id", title="new title", category="new category")
    assert make_task().version == changed.version


def test_session_order_matters():
    a = make_task(sessions=["remember X", "use X"])
    b = make_task(sessions=["use X", "remember X"])
    assert a.version != b.version


def test_json_list_becomes_tuple():
    task = make_task(expected_tools=["write_file", "read_file"])
    assert task.sessions == ("What is the West revenue?",)
    assert task.expected_tools == ("read_file", "write_file")
