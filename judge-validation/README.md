# Judge validation set

`labelled.jsonl` holds 32 responses to the four judge-graded tasks (`judge-incident-update`, `judge-code-review`, `judge-decline-email`, `skill-release-notes`), each labelled pass or fail against the task's rubric. About 40% pass. The failures are deliberately hard: near-misses that break exactly one rubric item, leaked internal hostnames, invented blockers, an over-length email, an implied purchase commitment and a prompt-injection attempt.

Run the judge over them:

```bash
cd worker
uv run evals judge-validate            # uses JUDGE_MODEL, default anthropic/claude-haiku-5-5
```

It prints agreement, Cohen's κ, the confusion matrix and every disagreement, and writes `results/judge-validation.json`, which the UI shows.

## Labels need a human pass

The labels were drafted by an AI assistant following each rubric (`labeller: "draft:claude"`). Until a person has checked them, agreement measures whether the judge applies the rubric the way its author intended, not agreement with humans. To turn it into a human-labelled set, read each `response`, set `human_pass` and put your name in `labeller`.

Add an item whenever a live trial shows the judge disagreeing with the deterministic checks: those are the cases most likely to expose judge errors.
