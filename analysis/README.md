# Analysis scripts

One-off analyses behind EXPERIMENT.md. They read `/app/results/evals.db`, so run them inside the container:

```bash
docker compose cp analysis/trials_needed.py app:/tmp/ && \
  docker compose exec -w /app/worker app /app/worker/.venv/bin/python /tmp/trials_needed.py <experiment id>...
```

- `trials_needed.py`: re-runs the comparison on subsets of 1, 2 and 3 trials per task and prints the verdicts, to check how many trials an effect needs.
- `behaviour.py`: per config, pass rate, steps, how many coding trials ran code, and how many tasks gave the same final answer in every trial (determinism).
