# Agent Evals

Evaluate any agent harness (X) running any model (Y) and answer one question with evidence: **did a change make the agent better, worse, or no different, and how sure are we?**

- Two harnesses behind one interface: [Hermes Agent](https://github.com/NousResearch/hermes-agent) and a minimal tool-calling baseline.
- Any LiteLLM model: Gemini, Groq (open-weight gpt-oss), Anthropic, local Ollama.
- 25 tasks with deterministic graders (exact match, numeric, regex, file state, hidden unit tests) and a rubric-based LLM judge that is validated against labelled examples.
- Versioned configs, N trials per task, isolated trials, timeouts, retries, budget cap and resume.
- Paired comparison: bootstrap confidence interval, McNemar test, per-task deltas with a noise flag, plus cost, latency and tokens.
- A trajectory view for every trial, and failure categories.

See [DESIGN.md](DESIGN.md) for how it works and why, [EXPERIMENT.md](EXPERIMENT.md) for the three experiments and what they found, and [Known limits](DESIGN.md#known-limits).

## Run it

```bash
cp .env.example .env        # add at least one provider key
docker compose up --build   # http://localhost:3000
```

Results live in `results/evals.db` (SQLite), which is mounted into the container, so runs survive restarts.

Start runs from the UI (or `docker compose exec app evals ...`) while the container is up. Don't run the worker on the host against the same `results/` folder at the same time: SQLite's WAL mode needs reader and writer on the same machine, and Docker Desktop's file sharing crosses a VM boundary, so the container reads the database as malformed until the host writer stops.

In the UI: **Configs** → define two configs that differ in one thing → **Experiments** → pick both, choose trials and a budget → **Run**. The experiment page fills in live: verdict and confidence interval, cost and latency, per-task deltas, and a grid of trials. Click any trial to see its full trajectory and grader reasoning. Export results as JSON or CSV from the same page.

### Without Docker

Requires Python 3.11+, [uv](https://docs.astral.sh/uv/) and Node 22.

```bash
cd worker && uv sync && cd ..
cd api && npm ci && npm run build && cd ..
cd ui && npm ci && npm run build && cd ..
# only for the Hermes harness: Hermes no longer ships wheels, so install a pinned source checkout
git clone https://github.com/NousResearch/hermes-agent.git ~/.local/share/hermes-agent-src
(cd ~/.local/share/hermes-agent-src && git checkout 0f602c5f && uv sync --frozen --python 3.14 --extra anthropic --extra google)
ln -s ~/.local/share/hermes-agent-src/.venv/bin/hermes ~/.local/bin/hermes
node --disable-warning=ExperimentalWarning api/dist/main.js   # serves API + UI on :3000
```

Everything the UI does is also a CLI command:

```bash
cd worker
uv run evals tasks
uv run evals config add ../configs/baseline-gpt-oss-120b.json
uv run evals run --name "120b vs 20b" \
  --config ../configs/baseline-gpt-oss-120b.json --config ../configs/baseline-gpt-oss-20b.json \
  --trials 3 --budget 2            # re-running the same command resumes it
uv run evals compare <experiment-id>
uv run evals export <experiment-id> --format csv --out results.csv
uv run evals judge-validate
```

### Tests

```bash
cd worker && uv run pytest        # 185 tests, no network calls
cd api && npm test
cd ui && npm test
```

## Add a task

Create `tasks/<id>/task.json` (the folder name must match `id`):

```json
{
  "id": "log-503-count",
  "title": "Count 503 errors in a time window",
  "category": "data",
  "sessions": [{ "prompt": "... End your reply with a line of the form `ANSWER: <answer>`." }],
  "graders": [{ "type": "exact_match", "expected": "9" }],
  "timeout_s": 300,
  "expected_tools": ["read_file", "run_python"]
}
```

- `fixtures/` is copied into the agent's sandbox. `reference/` holds the gold solution and `tests/` holds hidden unit tests. The agent never sees either.
- More than one entry in `sessions` makes a multi-session task. Each session starts a fresh conversation, so only memory carries over.
- Grader types: `exact_match` (with `normalize`), `numeric` (with `tolerance`), `regex` (`patterns` and `forbidden`), `file_state` (`json_equals`, `lines_equal`, `equals`, `regex`, `not_contains`), `unit_tests` (`files` and `command`) and `llm_judge` (`rubric` and `pass_threshold`, optional `reference` and `target`). A grader with `"required": false` is advisory: it is recorded but doesn't decide pass or fail.
- Put the gold answer in `reference/answer.txt`, or gold files in `reference/`. `pytest tests/test_task_graders.py` then checks that the reference solution passes and the untouched fixtures fail.

Editing a task changes its version, which is a hash of everything that affects behaviour. The runner refuses to resume an experiment across task versions.

## Add a harness

Implement one method and register it in `worker/evals/harnesses/__init__.py`:

```python
class MyHarness:
    async def run(self, task: Task, config: Config, env: TrialEnv, trace: Trace) -> HarnessResult:
        # env.workdir: sandbox with fixtures; env.state_dir: survives across sessions of this trial only
        # trace.add(...) for events, trace.count_usage(...) for tokens and cost
        return HarnessResult(answers=(final_answer_per_session,))
```

`harnesses/hermes.py` (a subprocess adapter) and `harnesses/baseline.py` (an in-process loop) are the two worked examples. Nothing in the runner, graders, stats, API or UI changes.

## Add a model

Any [LiteLLM model string](https://docs.litellm.ai/docs/providers) works as-is in a config (`"model": "groq/openai/gpt-oss-120b"`). Put the provider's key in `.env`. A provider LiteLLM doesn't support needs a class with `async complete(messages, tools, temperature, max_tokens) -> ModelResponse` (see `worker/evals/model.py`). For Hermes, add the provider prefix to `NATIVE_PROVIDERS` or `OPENAI_COMPATIBLE` in `harnesses/hermes.py`.

## Repository layout

```
worker/   Python: tasks, configs, harnesses, graders, runner, stats, CLI   (the platform core)
api/      NestJS: REST over the results database; starts runs via the worker CLI
ui/       React + Vite: configs, experiments, comparison, trajectories, judge validation
tasks/    25 tasks       skills/  5 skills       configs/  example configs
judge-validation/  labelled examples for checking the judge
```

The UI is in React rather than Vue. I'm familiar with React, so I went ahead with it; if High Level objects, I can redo it in Vue quickly with AI help.

## Inspecting results directly

```bash
sqlite3 -init .sqliterc results/evals.db
```
