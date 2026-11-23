from __future__ import annotations

import csv
import json
from dataclasses import asdict
from pathlib import Path

from evals.store import Store


def trial_records(store: Store, experiment_id: str) -> list[dict]:
    experiment = store.get_experiment(experiment_id)
    configs = {
        config_id: store.get_config(config_id) for config_id in experiment.config_ids
    }
    records = []
    for trial in store.get_trials(experiment_id):
        config = configs[trial.config_id]
        records.append(
            {
                "trial_id": trial.id,
                "experiment_name": experiment.name,
                "config_label": config.label,
                "harness": config.harness,
                "model": config.model,
                **{
                    f"settings.{key}": value
                    for key, value in asdict(config.settings).items()
                },
                **asdict(trial),
            }
        )
    return records


def export_json(
    store: Store, experiment_id: str, path: Path, include_traces: bool = False
) -> None:
    records = trial_records(store, experiment_id)
    if include_traces:
        for record in records:
            record["trace"] = asdict(store.get_trace(record["trial_id"]))
    path.write_text(json.dumps(records, indent=2))


def export_csv(store: Store, experiment_id: str, path: Path) -> None:
    records = [flatten(record) for record in trial_records(store, experiment_id)]
    with path.open("w", newline="") as f:
        if records:
            writer = csv.DictWriter(f, fieldnames=list(records[0]))
            writer.writeheader()
            writer.writerows(records)


def flatten(record: dict) -> dict:
    return {
        key: ";".join(value) if isinstance(value, (tuple, list)) else value
        for key, value in record.items()
    }
