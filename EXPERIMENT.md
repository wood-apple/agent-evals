# Experiment: do skills help?

**Experiment id:** `exp-1ece8817f7b0` (in `results/evals.db`; reproduce with the command below)

## Hypothesis

Giving the baseline agent the five ACME skills raises its pass rate on tasks whose conventions exist *only* in those skills (invoice IDs, fiscal quarters, the qlog format, shipping rates, release-note house style), and makes no difference on the other 20 tasks. Cost should rise slightly, because the skill list goes into the system prompt and a skill is loaded when needed.

This is a deliberately strong, known effect. Besides answering the question, it's a **positive control for the platform**: if the statistics can't detect a 0% → 100% jump on 5 tasks while calling the other 20 tasks noise or ceiling, the platform can't be trusted on subtler questions.

## Setup

| | A (baseline) | B (candidate) |
|---|---|---|
| Harness | baseline tool-calling loop | same |
| Model | `anthropic/claude-haiku-5-5` | same |
| Settings | max 15 steps, memory on, **no skills** | same, **all 5 skills** |
| Config | `configs/baseline-haiku-no-skills.json` | `configs/baseline-haiku-skills.json` |

The configs differ in exactly one setting. That's visible in their content-hashed ids, which differ only through `skills`.

- **Tasks:** all 25, with N = 5 trials per task per config, so 250 trials and 125 pairs.
- **Judge:** `groq/qwen/qwen3.8-27b`. It's from a different family than the agent, so there's no self-preference. It agreed with the labelled set 94% of the time (κ 0.87); see [DESIGN.md](DESIGN.md#how-the-graders-were-validated).
- **Temperature:** Haiku 5.5 only accepts temperature 1, so the configured 0.0 is dropped by the adapter. Both arms sample at the same temperature, so this doesn't bias the comparison.
- **Run:**

  ```bash
  cd worker
  uv run evals run --name "skills on vs off (haiku, baseline)" \
    --config ../configs/baseline-haiku-no-skills.json --config ../configs/baseline-haiku-skills.json \
    --trials 5 --concurrency 4 --budget 5
  ```

- **Execution:** the first pass produced 3 infrastructure errors, all on the judge for `judge-incident-update`: one Groq rate limit, and two judge replies with raw newlines inside JSON strings, which led to a parser fix (`d292951`). They were kept out of the stats and re-run by resuming with the same command, which ran exactly those 3 trials. The final data has 0 errors and 125 complete pairs.

## Results

| | Pass rate | Cost / trial | Latency | Tokens in / out | Infra errors |
|---|---|---|---|---|---|
| A: no skills | 79.2% | $0.00087 | 5.7 s | 4,336 / 870 | 0 |
| B: skills | **98.4%** | $0.00088 | 4.9 s | 4,961 / 764 | 0 |

- **Δ pass rate (B − A): +19.2 pp, 95% CI [+4.0, +36.0]** (two-level paired bootstrap over tasks, 10,000 resamples).
- **McNemar on 125 trial pairs:** 26 pairs passed only with skills and 2 passed only without. p = 3 × 10⁻⁶.
- **Verdict: B is better.** Both the CI and the test exclude "no difference".

**Per task:**

| Task | A | B | Reading |
|---|---|---|---|
| skill-acme-fiscal-quarter | 0% | 100% | likely real (p = 0.008) |
| skill-acme-invoice-id | 0% | 100% | likely real |
| skill-qlog-bytes | 0% | 100% | likely real |
| skill-release-notes | 0% | 100% | likely real |
| skill-shipping-cost | 0% | 100% | likely real |
| judge-code-review | 80% | 100% | noise (p = 1.0) |
| judge-incident-update | 100% | 60% | noise (p = 0.44) |
| the other 18 tasks | 100% | 100% | ceiling: both always pass |

**Why the CI is wide even though the effect is huge.** The whole gain comes from 5 of the 25 tasks. Resampling tasks sometimes draws few of them and sometimes many, and that's the honest answer to "how much would this generalise to a different task mix?". With only 25 tasks this run can't resolve differences smaller than about ±16 pp, and the report says so.

**Cost and latency.** Skills cost +14% input tokens (the skill list in the system prompt, plus the skill text when it's loaded). Output tokens drop 12% and trials are 14% faster, because the agent stops searching the sandbox and asking for a spec that isn't there. Net cost is +1%.

## Trajectories that explain the difference

1. **`skill-acme-invoice-id`, no skills (trial `1c5511cc2a0e`): fails honestly.** The agent lists the sandbox, finds no files, and answers "Cannot determine. The sandbox has no files, and the ACME invoice ID format is not specified." It doesn't hallucinate a format. That is the right behaviour given what it knows, and all five no-skill trials do the same.
2. **`skill-acme-invoice-id`, skills (trial `16f896b36dba`): load, compute, verify.** The agent's first action is `read_skill("acme-finance")`. It then writes Python implementing the consonant and check-letter rules, gets `INV-2611-NTC-01307-V`, and explains each component. Three steps, every one visible in the trace (`skill_load`, then `run_python`, then the answer).
3. **`skill-release-notes`, no skills (trial `51bf8435b30a`): the graders disagree, and that's informative.** The agent writes sensible release notes in a generic format ("Bug fixes", "#755"). The judge gives them 5/5 for clarity and accuracy, but the structural check fails on every house-style rule (title line, section names and order, `(ACME-755)` ticket format). The failure is categorised as `grader_disagreement`, which is exactly the case where looking at both graders matters: the writing is good, the convention is unknowable without the skill.
4. **`judge-incident-update`, skills, the "regression" (trials `aafcbdfac9cb`, `035686807262`): noise.** Neither trial loaded a skill, because none is relevant, so the configs behave identically on this task. Both drafts were judged 2–3/5, mostly for giving the window as "14:00–14:44" (the certificate expiry time) instead of the first error at 14:02, and for a missing apology. The no-skills arm happened to word it better in all 5 trials. Fisher's exact test puts this at p = 0.44, and the platform labels it noise. Treating it as a skills regression would be wrong.

## Conclusion

Skills give the baseline agent knowledge it otherwise lacks, and it uses them correctly: it loads the right skill on its first step every time. That turns 5 impossible tasks into reliable passes, at essentially no extra cost. On tasks where skills are irrelevant, the platform reports no difference: 18 tasks at ceiling, and 2 small swings correctly marked as noise.

**Caveats:**
- The skill tasks were *designed* to need the skills, so the 19 pp effect says more about this task set than about skills in general.
- 18 of the 25 tasks are at ceiling for Haiku, which is a signal to add harder tasks before using this set to compare strong models.
- The judge-graded tasks have the most run-to-run variance, which argues for N ≥ 10 when the question is about writing quality.

## Cost

```
cost = tasks × trials × configs × (avg input tokens × input price + avg output tokens × output price) + judge cost
     = 25 × 5 × 2 × (4,649 × $0.10/M + 817 × $0.50/M)                                   + judge
     = 250 × $0.00087                                                                    + $0.0755
     ≈ $0.22 agent + $0.08 judge = $0.29
```

Haiku 5.5 list prices are $0.10 / $0.50 per million input / output tokens for requests under 100k tokens (5× above that; no call here came close). The judge's $0.08 is the list price of 40 Qwen judge calls on 4 tasks. Groq's free tier meant the judge actually cost $0. Measured spend matches the formula. Wall time was 14 minutes at concurrency 4.

**Projection for a Hermes run with the same design:** Hermes used about 22k–48k input tokens per session in the smoke tests, against about 4.6k for the baseline. The same experiment would therefore cost roughly 5–10× more, about $1.50–3 on Haiku, before prompt caching.

## What didn't work

- **Free-tier comparison (gpt-oss-120b vs 20b on Groq), runs `exp-a8f0b66439bc` and `exp-e69a46b046f0`, abandoned.** Groq's free tier allows 200k tokens per model per day, and the run needed over a million. Its partial results are kept in the database but not used. Two lessons from it are now built into the platform: rate-limit waits that run out the clock are infrastructure errors, not agent timeouts (`c866a76`), and malformed tool calls rejected by the provider count against the agent (`e039cc2`).
- **Hermes on Claude.** Requests were rejected with "credit balance too low" while the same key worked through LiteLLM and curl. Capturing Hermes's request with a local proxy and replaying it showed why: Hermes 0.19.0 treats any Anthropic key that doesn't start with `sk-ant-api` as a Claude Code subscription token, adds a "You are Claude Code" identity to the system prompt, and the request is then billed as a subscription request. Our key was a non-Console `sk-ant-usr-` key. The adapter now rejects such keys up front with a clear message; a Console API key fixes it. The Hermes adapter is covered by tests against a fake Hermes binary and was run successfully against Groq and Gemini. A Hermes experiment ("memory on vs off") is the obvious next run once this is resolved.
