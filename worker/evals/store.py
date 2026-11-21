from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from evals.config import Config, Settings

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


def now() -> str:
    return datetime.now(UTC).isoformat()
