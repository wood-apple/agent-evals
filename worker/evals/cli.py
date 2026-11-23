from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from dataclasses import asdict
from pathlib import Path

from dotenv import load_dotenv

from evals import sandbox
from evals.config import Config, Settings
from evals.experiment import Experiment, TrialResult, experiment_id
from evals.export import export_csv, export_json
from evals.graders import Judge
from evals.judge_validation import load_labels, validate
from evals.runner import Budget, run_experiment
from evals.stats import compare
from evals.store import Store
from evals.task_loader import load_tasks

ROOT = Path(os.environ.get("EVALS_ROOT", Path(__file__).resolve().parents[2]))


def main(argv: list[str] | None = None) -> int:
    load_dotenv(ROOT / ".env")
    logging.basicConfig(
        level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )
    if sandbox.AGENT_USER:
        # the agent user writes into trial dirs this process creates, so they
        # need group write whether we were started by the API or by docker exec
        os.umask(0o002)
    args = parser().parse_args(argv)
    return args.handler(args) or 0


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="evals", description="Evaluate agent harnesses and models."
    )
    p.add_argument(
        "--db",
        type=Path,
        default=Path(os.environ.get("EVALS_DB", ROOT / "results/evals.db")),
    )
    sub = p.add_subparsers(required=True)

    tasks = sub.add_parser("tasks", help="list tasks as JSON")
    tasks.set_defaults(handler=cmd_tasks)

    config = sub.add_parser("config", help="save or list configs")
    config_sub = config.add_subparsers(required=True)
    add = config_sub.add_parser("add", help="save a config from a JSON file or string")
    add.add_argument("source", help="path to a config JSON file, or a JSON string")
    add.set_defaults(handler=cmd_config_add)
    config_sub.add_parser("list").set_defaults(handler=cmd_config_list)

    run = sub.add_parser("run", help="run an experiment (resumes if it already exists)")
    run.add_argument("--name", required=True)
    run.add_argument(
        "--config",
        action="append",
        required=True,
        help="config id or JSON file; repeat",
    )
    run.add_argument("--tasks", help="comma-separated task ids (default: all)")
    run.add_argument("--category", help="only tasks in this category")
    run.add_argument("--trials", type=int, default=5)
    run.add_argument("--concurrency", type=int, default=4)
    run.add_argument(
        "--budget", type=float, default=float(os.environ.get("EVALS_BUDGET_USD", "5"))
    )
    run.add_argument("--seed", type=int, default=0)
    run.add_argument(
        "--trial-attempts",
        type=int,
        default=3,
        help="attempts per trial on infrastructure errors",
    )
    run.set_defaults(handler=cmd_run)

    cmp = sub.add_parser("compare", help="compare two configs in an experiment")
    cmp.add_argument("experiment")
    cmp.add_argument("--a", help="baseline config id (default: first config)")
    cmp.add_argument("--b", help="candidate config id (default: second config)")
    cmp.add_argument("--json", action="store_true")
    cmp.set_defaults(handler=cmd_compare)

    export = sub.add_parser("export", help="export trial results")
    export.add_argument("experiment")
    export.add_argument("--format", choices=["json", "csv"], default="json")
    export.add_argument(
        "--traces", action="store_true", help="include traces (JSON only)"
    )
    export.add_argument("--out", type=Path, required=True)
    export.set_defaults(handler=cmd_export)

    archive = sub.add_parser("archive", help="hide an experiment in the UI")
    archive.add_argument("experiment")
    archive.add_argument("--undo", action="store_true", help="unarchive")
    archive.set_defaults(handler=cmd_archive)

    judge = sub.add_parser(
        "judge-validate", help="score the judge against labelled examples"
    )
    judge.add_argument(
        "--labels", type=Path, default=ROOT / "judge-validation/labelled.jsonl"
    )
    judge.add_argument(
        "--out", type=Path, default=ROOT / "results/judge-validation.json"
    )
    judge.add_argument("--concurrency", type=int, default=1)
    judge.set_defaults(handler=cmd_judge_validate)
    return p


def open_store(args) -> Store:
    args.db.parent.mkdir(parents=True, exist_ok=True)
    return Store(args.db)


def cmd_tasks(args) -> None:
    rows = [
        {
            "id": t.id,
            "title": t.title,
            "category": t.category,
            "version": t.version,
            "sessions": list(t.sessions),
            "graders": [g["type"] for g in t.graders],
            "timeout_s": t.timeout_s,
        }
        for t in load_tasks(ROOT / "tasks")
    ]
    print(json.dumps(rows, indent=2))


def parse_config(source: str) -> Config:
    text = Path(source).read_text() if Path(source).is_file() else source
    data = json.loads(text)
    return Config(
        harness=data["harness"],
        model=data["model"],
        settings=Settings(**data.get("settings", {})),
        label=data.get("label", ""),
    )


def config_json(config: Config) -> dict:
    return {"id": config.id, **asdict(config)}


def cmd_config_add(args) -> None:
    config = parse_config(args.source)
    open_store(args).save_config(config)
    print(json.dumps(config_json(config)))


def cmd_config_list(args) -> None:
    store = open_store(args)
    ids = [
        row["id"]
        for row in store.conn.execute("select id from configs order by created_at")
    ]
    print(json.dumps([config_json(store.get_config(i)) for i in ids], indent=2))


def resolve_config(store: Store, ref: str) -> Config:
    if Path(ref).is_file() or ref.lstrip().startswith("{"):
        return parse_config(ref)
    return store.get_config(ref)


def cmd_run(args) -> int:
    store = open_store(args)
    configs = [resolve_config(store, ref) for ref in args.config]
    tasks = {t.id: t for t in load_tasks(ROOT / "tasks")}
    selected = sorted(args.tasks.split(",")) if args.tasks else sorted(tasks)
    if args.category:
        selected = [t for t in selected if tasks[t].category == args.category]
    unknown = [t for t in selected if t not in tasks]
    if unknown:
        print(f"unknown tasks: {unknown}", file=sys.stderr)
        return 2
    config_ids = [c.id for c in configs]
    judge = Judge()
    experiment = Experiment(
        id=experiment_id(
            args.name,
            {t: tasks[t].version for t in selected},
            config_ids,
            args.trials,
            args.seed,
            judge.model.name,
        ),
        name=args.name,
        task_ids=tuple(selected),
        config_ids=tuple(config_ids),
        n_trials=args.trials,
        seed=args.seed,
    )
    labels = {c.id: c.label or c.id for c in configs}
    total = len(selected) * len(configs) * args.trials
    print(
        json.dumps(
            {
                "event": "start",
                "experiment_id": experiment.id,
                "planned_trials": total,
                "judge_model": judge.model.name,
            }
        ),
        flush=True,
    )

    def progress(result: TrialResult) -> None:
        line = {
            "event": "trial",
            "task": result.task_id,
            "config": labels[result.config_id],
            "trial": result.trial_index,
            "status": result.status,
            "passed": result.passed,
            "cost_usd": result.cost_usd,
        }
        print(json.dumps(line), flush=True)

    summary = asyncio.run(
        run_experiment(
            store,
            experiment,
            tasks,
            configs,
            skills_dir=ROOT / "skills",
            budget=Budget(args.budget),
            judge=judge,
            concurrency=args.concurrency,
            trial_attempts=args.trial_attempts,
            on_trial=progress,
        )
    )
    print(json.dumps({"event": "done", **asdict(summary)}), flush=True)
    return 0


def cmd_compare(args) -> None:
    store = open_store(args)
    experiment = store.get_experiment(args.experiment)
    a = args.a or experiment.config_ids[0]
    b = args.b or experiment.config_ids[1]
    report = compare(store.get_trials(experiment.id), a, b, seed=experiment.seed)
    report["labels"] = {a: store.get_config(a).label, b: store.get_config(b).label}
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_report(report))


def pct(value: float | None) -> str:
    return "—" if value is None else f"{value * 100:.1f}%"


def format_report(r: dict) -> str:
    la, lb = r["labels"][r["config_a"]] or "A", r["labels"][r["config_b"]] or "B"
    lines = [
        f"A = {la}   B = {lb}   ({r['pairs']} paired trials over {r['tasks']} tasks)"
    ]
    for key, label in (("a", la), ("b", lb)):
        s = r[key]
        lines.append(
            f"  {label:<24} pass {pct(s['pass_rate']):>6}   cost ${s['total_cost_usd']:.4f}"
            f"   latency {(s['mean_latency_ms'] or 0) / 1000:.1f}s"
            f"   tokens {s['mean_input_tokens'] or 0:,.0f} in / {s['mean_output_tokens'] or 0:,.0f} out"
            f"   errors {s['errors']}"
        )
    if "delta" in r:
        low, high = r["ci95"]
        lines.append(
            f"Δ pass rate (B − A): {r['delta'] * 100:+.1f} pp, 95% CI [{low * 100:+.1f}, {high * 100:+.1f}]"
        )
        m = r["mcnemar"]
        lines.append(
            f"McNemar: A-only {m['only_a_passed']}, B-only {m['only_b_passed']}, p = {m['p_value']:.3f}"
        )
        lines.append(f"Verdict: {r['verdict']}")
        lines.append("Per task:")
        for row in r["per_task"]:
            lines.append(
                f"  {row['task_id']:<28} {pct(row['pass_rate_a']):>6} → {pct(row['pass_rate_b']):>6}"
                f"  ({row['delta'] * 100:+.0f} pp, p={row['p_value']:.2f}) {row['signal']}"
            )
    else:
        lines.append(f"Verdict: {r['verdict']}")
    return "\n".join(lines)


def cmd_export(args) -> None:
    store = open_store(args)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    if args.format == "csv":
        export_csv(store, args.experiment, args.out)
    else:
        export_json(store, args.experiment, args.out, include_traces=args.traces)
    print(args.out)


def cmd_archive(args) -> None:
    open_store(args).set_archived(args.experiment, not args.undo)
    print(json.dumps({"id": args.experiment, "archived": not args.undo}))


def cmd_judge_validate(args) -> None:
    tasks = {t.id: t for t in load_tasks(ROOT / "tasks")}
    report = asyncio.run(
        validate(load_labels(args.labels), tasks, Judge(), args.concurrency)
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2))
    print(
        f"judge {report['judge_model']}: agreement {report['agreement']:.0%}, "
        f"kappa {report['kappa']:.2f}, confusion {report['confusion']}, cost ${report['cost_usd']:.4f}"
    )
    for failure in report["failed"]:
        print(f"  not judged: {failure}")
    for item in report["disagreements"]:
        print(
            f"  {item['id']}: human {'pass' if item['human_pass'] else 'fail'}, judge {item['judge_score']}/5"
        )


if __name__ == "__main__":
    sys.exit(main())
