import json

import pytest
from fakes import reply

from evals.graders import (
    Grade,
    GraderError,
    Judge,
    combine,
    extract_answer,
    grade_trial,
    unittest_score,
)
from evals.task import Task


def make_task(*graders, grading_files=None):
    return Task(
        id="t",
        title="t",
        category="c",
        sessions=("q",),
        graders=graders,
        grading_files=grading_files or {},
    )


async def grade_one(spec, answer="", workdir=None, judge=None, **task_args):
    [grade] = await grade_trial(make_task(spec, **task_args), answer, workdir, judge)
    return grade


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("work...\nANSWER: 60", "60"),
        ("ANSWER: 1\nmore\n**ANSWER:** 2", "2"),
        ("  just text  ", "just text"),
        ("", ""),
    ],
)
def test_extract_answer(text, expected):
    assert extract_answer(text) == expected


async def test_exact_match_normalizes_both_sides():
    spec = {
        "type": "exact_match",
        "expected": "INV-2611-NTC",
        "normalize": ["trim", "strip_punct", "lower"],
    }
    assert (await grade_one(spec, "ANSWER: inv2611ntc.")).passed
    assert not (await grade_one(spec, "ANSWER: INV-2611-NTX")).passed


async def test_exact_match_strips_markdown_by_default():
    assert (
        await grade_one({"type": "exact_match", "expected": "60"}, "ANSWER: **60**")
    ).passed


@pytest.mark.parametrize(
    ("answer", "passed"),
    [("ANSWER: 9,340.07", True), ("ANSWER: 9340.1", False), ("no idea", False)],
)
async def test_numeric_tolerance(answer, passed):
    spec = {"type": "numeric", "expected": 9340.07, "tolerance": 0.011}
    assert (await grade_one(spec, answer)).passed is passed


async def test_regex_patterns_and_forbidden():
    spec = {"type": "regex", "patterns": [r"18\.11\.2026"], "forbidden": ["api-gw-02"]}
    assert (await grade_one(spec, "18.11.2026 | ₹2,500")).passed
    grade = await grade_one(spec, "18.11.2026 via api-gw-02")
    assert not grade.passed
    assert "forbidden" in grade.reasoning


async def test_file_state_checks(tmp_path):
    (tmp_path / "c.json").write_text(json.dumps({"a": 1}))
    (tmp_path / "names.txt").write_text("a\nb\n")
    spec = {
        "type": "file_state",
        "checks": [
            {"path": "c.json", "json_equals": {"a": 1}},
            {"path": "names.txt", "lines_equal": ["a", "b"], "not_contains": ["z"]},
        ],
    }
    assert (await grade_one(spec, workdir=tmp_path)).passed
    (tmp_path / "c.json").write_text("{broken")
    grade = await grade_one(spec, workdir=tmp_path)
    assert not grade.passed
    assert grade.score == pytest.approx(2 / 3)
    assert "invalid JSON" in grade.reasoning


async def test_file_state_missing_file(tmp_path):
    grade = await grade_one(
        {"type": "file_state", "checks": [{"path": "x", "equals": "y"}]},
        workdir=tmp_path,
    )
    assert (grade.passed, grade.reasoning) == (False, "x: missing")


TEST_FILE = """\
import unittest
from add import add

class T(unittest.TestCase):
    def test_small(self):
        self.assertEqual(add(1, 2), 3)

    def test_negative(self):
        self.assertEqual(add(-1, -2), -3)
"""


async def test_unit_tests_run_hidden_tests_on_a_copy(tmp_path):
    spec = {
        "type": "unit_tests",
        "files": ["test_add.py"],
        "command": ["python3", "-m", "unittest", "test_add"],
    }
    files = {"tests/test_add.py": TEST_FILE}
    (tmp_path / "add.py").write_text("def add(a, b):\n    return a + b\n")
    assert (await grade_one(spec, workdir=tmp_path, grading_files=files)).passed
    assert not (tmp_path / "test_add.py").exists()

    (tmp_path / "add.py").write_text("def add(a, b):\n    return abs(a) + abs(b)\n")
    grade = await grade_one(spec, workdir=tmp_path, grading_files=files)
    assert not grade.passed
    assert grade.score == 0.5


def test_unittest_score_on_import_error():
    assert unittest_score("ImportError: no module named add", passed=False) == 0.0


def test_combine_ignores_advisory_graders():
    grades = [
        Grade("judge", True, 1.0, ""),
        Grade("style", False, 0.0, "", required=False),
    ]
    verdict = combine(grades)
    assert verdict.passed
    assert verdict.score == 1.0


def test_combine_needs_a_required_grader():
    with pytest.raises(GraderError):
        combine([Grade("style", True, 1.0, "", required=False)])


class FakeJudgeModel:
    def __init__(self, *texts):
        self.texts = list(texts)
        self.prompts = []

    async def complete(self, messages, tools, temperature, max_tokens):
        self.prompts.append(messages[0]["content"])
        return reply(self.texts.pop(0))


JUDGE_SPEC = {"type": "llm_judge", "rubric": "1. Polite.", "pass_threshold": 4}


async def test_judge_passes_at_threshold():
    model = FakeJudgeModel(
        '{"items": [{"item": 1, "met": true, "why": "polite"}], "score": 4}'
    )
    grade = await grade_one(JUDGE_SPEC, "Dear team", judge=Judge(model))
    assert grade.passed
    assert grade.score == 0.75
    assert "✓ 1: polite" in grade.reasoning
    assert "<response>\nDear team\n</response>" in model.prompts[0]


async def test_judge_retries_unparseable_output_once():
    model = FakeJudgeModel("I think it's fine", '{"score": 2}')
    grade = await grade_one(JUDGE_SPEC, "x", judge=Judge(model))
    assert not grade.passed
    assert len(model.prompts) == 2


async def test_judge_rejects_out_of_range_scores():
    model = FakeJudgeModel('{"score": 9}', '{"score": 0}')
    with pytest.raises(GraderError, match="unparseable"):
        await grade_one(JUDGE_SPEC, "x", judge=Judge(model))


async def test_judge_can_grade_a_file(tmp_path):
    spec = {**JUDGE_SPEC, "target": {"kind": "file", "path": "NOTES.md"}}
    model = FakeJudgeModel('{"score": 5}')
    grade = await grade_one(spec, "see file", workdir=tmp_path, judge=Judge(model))
    assert (grade.passed, grade.reasoning) == (False, "NOTES.md was not created")
    (tmp_path / "NOTES.md").write_text("# Notes")
    assert (
        await grade_one(spec, "see file", workdir=tmp_path, judge=Judge(model))
    ).passed


async def test_unknown_grader_type_is_an_error():
    with pytest.raises(GraderError, match="unknown grader"):
        await grade_one({"type": "vibes"})


async def test_judge_sees_the_files_the_agent_was_given():
    model = FakeJudgeModel('{"score": 5}')
    task = Task(
        id="t",
        title="t",
        category="c",
        sessions=("q",),
        graders=(JUDGE_SPEC,),
        fixtures={"changes.json": "[1]"},
    )
    await grade_trial(task, "notes", None, Judge(model))
    assert "--- changes.json ---\n[1]" in model.prompts[0]
