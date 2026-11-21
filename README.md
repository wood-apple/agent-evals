# Agent Evals

Evaluate any agent harness running with any model and settings, and tell whether a change made it better, worse, or made no difference.

Work in progress.

## Development

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
cd worker
uv sync
uv run pytest
```

### Inspecting results

Results live in a single SQLite file. Open it with the bundled settings for readable output:

```bash
sqlite3 -init .sqliterc results/evals.db
```
