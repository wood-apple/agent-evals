from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, fields
from datetime import UTC, datetime
from pathlib import Path

from evals.config import Config, Settings
from evals.experiment import Experiment, TrialResult, TrialTrace

SCHEMA = (Path(__file__).parent / "schema.sql").read_text()


class Store:
    def __init__(self, path: Path | str):
        self.conn = sqlite3.connect(path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("pragma journal_mode = wal")
        self.conn.execute("pragma foreign_keys = on")
        self.conn.executescript(SCHEMA)

    def close(self) -> None:
        self.conn.close()

    def save_config(self, config: Config) -> str:
        with self.conn:
            self.conn.execute(
                "insert or ignore into configs (id, harness, model, settings, label, created_at)"
                "values(?, ?, ?, ?, ?, ?)",
                (
                    config.id,
                    config.harness,
                    config.model,
                    json.dumps(asdict(config.settings)),
                    config.label,
                    now(),
                ),
            )
        return config.id

    def get_config(self, config_id: str) -> Config:
        row = self.conn.execute(
            "select * from configs where id = ?", (config_id,)
        ).fetchone()
        if row is None:
            raise KeyError(config_id)
        return Config(
            harness=row["harness"],
            model=row["model"],
            label=row["label"],
            settings=Settings(**json.loads(row["settings"])),
        )

    def save_experiment(self, experiment: Experiment) -> None:
        with self.conn:
            self.conn.execute(
                "insert into experiments"
                " (id, name, task_ids, config_ids, n_trials, seed, status, created_at)"
                " values (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    experiment.id,
                    experiment.name,
                    json.dumps(list(experiment.task_ids)),
                    json.dumps(list(experiment.config_ids)),
                    experiment.n_trials,
                    experiment.seed,
                    "pending",
                    now(),
                ),
            )

    def set_experiment_status(self, experiment_id: str, status: str) -> None:
        with self.conn:
            self.conn.execute(
                "update experiments set status = ? where id = ?",
                (status, experiment_id),
            )

    def save_trial(self, result: TrialResult, trace: TrialTrace) -> bool:
        with self.conn:
            cursor = self.conn.execute(
                "insert or ignore into trials"
                " (id, experiment_id, task_id, task_version, config_id, trial_index, status,"
                " passed, score, input_tokens, output_tokens, cost_usd, latency_ms, error,"
                " failure_category, finished_at)"
                " values (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    result.id,
                    result.experiment_id,
                    result.task_id,
                    result.task_version,
                    result.config_id,
                    result.trial_index,
                    result.status,
                    result.passed,
                    result.score,
                    result.input_tokens,
                    result.output_tokens,
                    result.cost_usd,
                    result.latency_ms,
                    result.error,
                    result.failure_category,
                    result.finished_at or now(),
                ),
            )
            if cursor.rowcount == 0:
                return False
            self.conn.execute(
                "insert into traces (trial_id, events, grades) values (?, ?, ?)",
                (result.id, json.dumps(trace.events), json.dumps(trace.grades)),
            )
        return True

    def finished_trial_ids(self, experiment_id: str) -> set[str]:
        rows = self.conn.execute(
            "select id from trials where experiment_id = ? and status != 'error'",
            (experiment_id,),
        )
        return {row["id"] for row in rows}

    def clear_errored_trials(self, experiment_id: str) -> int:
        with self.conn:
            self.conn.execute(
                "delete from traces where trial_id in"
                " (select id from trials where experiment_id = ? and status = 'error')",
                (experiment_id,),
            )
            cursor = self.conn.execute(
                "delete from trials where experiment_id = ? and status = 'error'",
                (experiment_id,),
            )
        return cursor.rowcount

    def get_trials(self, experiment_id: str) -> list[TrialResult]:
        rows = self.conn.execute(
            "select * from trials where experiment_id = ?"
            " order by task_id, config_id, trial_index",
            (experiment_id,),
        )
        return [row_to_trial_result(row) for row in rows]

    def get_trace(self, trial_id: str) -> TrialTrace:
        row = self.conn.execute(
            "select * from traces where trial_id = ? ",
            (trial_id,),
        ).fetchone()
        if row is None:
            raise KeyError(trial_id)
        return TrialTrace(
            grades=json.loads(row["grades"]),
            events=json.loads(row["events"]),
        )


def now() -> str:
    return datetime.now(UTC).isoformat()


def row_to_trial_result(row: sqlite3.Row) -> TrialResult:
    values = {f.name: row[f.name] for f in fields(TrialResult)}
    if values["passed"] is not None:
        values["passed"] = bool(values["passed"])
    return TrialResult(**values)
