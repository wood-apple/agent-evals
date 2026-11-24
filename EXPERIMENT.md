# Experiments

Fourteen experiments were run on the platform: four during the build, and ten in one overnight run (5–14, judged by Sonnet 5.5). All of them are in `results/evals.db` and can be opened in the UI.

| # | Question | Result |
|---|---|---|
| 1 | Do skills help the baseline agent? (Haiku, baseline) | **Yes**: +19.2 pp, CI [+4.0, +36.0], concentrated in the 5 skill tasks |
| 2 | Does memory help Hermes across sessions? (Haiku, Hermes) | **Yes, on the memory tasks**: 0% → 100% on two of them; the task-level CI includes 0 because only 3 of 25 tasks use memory |
| 3 | Can a local 8B model replace Haiku? (baseline, qwen3:8b on Ollama) | **No**: −63.9 pp, CI [−81.9, −44.4]; free, but it never tests its own code |
| 4 | Does thinking mode rescue the local model? (same as 3, thinking on) | **No**: −61.3 pp, CI [−78.7, −42.7]; 13× slower, helps on some tasks and hurts on others |
| 5 | A/A test: does the platform report differences that aren't there? | **No false positive**: −1.6 pp, CI [−8.8, +3.2] |
| 6 | How much does code execution matter? (Haiku without `run_python`) | **A lot**: −18.4 pp, CI [−32.8, −5.6]; three counting tasks 100% → 0%, and 34% more expensive |
| 7 | Hermes vs baseline, paired (Haiku) | **No difference**: +0.8 pp, at 6.6× the cost and 3.7× the latency |
| 8 | Haiku vs Sonnet 5.5 (baseline) | **No difference**: −2.4 pp at 16× the cost; Sonnet over-applies a skill on one task |
| 9 | Does a "test your code" nudge help? (Haiku, qwen3:8b) | **No**: qwen now runs tests (0/10 → 6/10) but ignores failing output; pass rate unchanged |
| 10 | Does experiment 1 survive a different judge? | **Yes**: +21.6 pp, CI [+7.2, +37.6] with Sonnet as judge |
| 11 | What does "memory off" turn off? (baseline Haiku) | **Only the tool**: agents write their own notes; with a fresh workspace memory-off drops 50% → 0%, and the rerun gives +13.6 pp (baseline) and +14.4 pp (Hermes), both "B is better" |
| 12 | Temperature 0 vs 0.7 (qwen3:8b) | **Same pass rate**; at 0 the trials are identical copies |
| 13 | Do skills help qwen3:8b? | **Barely**: 1 of 5 skill tasks |
| 14 | Which judge to trust? | **Sonnet 5.5** (κ 0.93 twice); Opus is consistently too strict; Haiku is noisy |

## 1. Do skills help?
**Experiment id:** `exp-1ece8817f7b0` (in `results/evals.db`; reproduce with the command below)

### Hypothesis

Giving the baseline agent the five ACME skills raises its pass rate on tasks whose conventions exist *only* in those skills (invoice IDs, fiscal quarters, the qlog format, shipping rates, release-note house style), and makes no difference on the other 20 tasks. Cost should rise slightly, because the skill list goes into the system prompt and a skill is loaded when needed.

This is a deliberately strong, known effect. Besides answering the question, it's a **positive control for the platform**: if the statistics can't detect a 0% → 100% jump on 5 tasks while calling the other 20 tasks noise or ceiling, the platform can't be trusted on subtler questions.

### Setup

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

### Results

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

### Trajectories that explain the difference

1. **`skill-acme-invoice-id`, no skills (trial `1c5511cc2a0e`): fails honestly.** The agent lists the sandbox, finds no files, and answers "Cannot determine. The sandbox has no files, and the ACME invoice ID format is not specified." It doesn't hallucinate a format. That is the right behaviour given what it knows, and all five no-skill trials do the same.
2. **`skill-acme-invoice-id`, skills (trial `16f896b36dba`): load, compute, verify.** The agent's first action is `read_skill("acme-finance")`. It then writes Python implementing the consonant and check-letter rules, gets `INV-2611-NTC-01307-V`, and explains each component. Three steps, every one visible in the trace (`skill_load`, then `run_python`, then the answer).
3. **`skill-release-notes`, no skills (trial `51bf8435b30a`): the graders disagree, and that's informative.** The agent writes sensible release notes in a generic format ("Bug fixes", "#755"). The judge gives them 5/5 for clarity and accuracy, but the structural check fails on every house-style rule (title line, section names and order, `(ACME-755)` ticket format). The failure is categorised as `grader_disagreement`, which is exactly the case where looking at both graders matters: the writing is good, the convention is unknowable without the skill.
4. **`judge-incident-update`, skills, the "regression" (trials `aafcbdfac9cb`, `035686807262`): noise.** Neither trial loaded a skill, because none is relevant, so the configs behave identically on this task. Both drafts were judged 2–3/5, mostly for giving the window as "14:00–14:44" (the certificate expiry time) instead of the first error at 14:02, and for a missing apology. The no-skills arm happened to word it better in all 5 trials. Fisher's exact test puts this at p = 0.44, and the platform labels it noise. Treating it as a skills regression would be wrong.

### Conclusion

Skills give the baseline agent knowledge it otherwise lacks, and it uses them correctly: it loads the right skill on its first step every time. That turns 5 impossible tasks into reliable passes, at essentially no extra cost. On tasks where skills are irrelevant, the platform reports no difference: 18 tasks at ceiling, and 2 small swings correctly marked as noise.

**Caveats:**
- The skill tasks were *designed* to need the skills, so the 19 pp effect says more about this task set than about skills in general.
- 18 of the 25 tasks are at ceiling for Haiku, which is a signal to add harder tasks before using this set to compare strong models.
- The judge-graded tasks have the most run-to-run variance, which argues for N ≥ 10 when the question is about writing quality.

### Cost

```
cost = tasks × trials × configs × (avg input tokens × input price + avg output tokens × output price) + judge cost
     = 25 × 5 × 2 × (4,649 × $0.10/M + 817 × $0.50/M)                                   + judge
     = 250 × $0.00087                                                                    + $0.0755
     ≈ $0.22 agent + $0.08 judge = $0.29
```

Haiku 5.5 list prices are $0.10 / $0.50 per million input / output tokens for requests under 100k tokens (5× above that; no call here came close). The judge's $0.08 is the list price of 40 Qwen judge calls on 4 tasks. Groq's free tier meant the judge actually cost $0. Measured spend matches the formula. Wall time was 14 minutes at concurrency 4.

**Projection for a Hermes run with the same design:** Hermes used about 22k–48k input tokens per session in the smoke tests, against about 4.6k for the baseline. The same experiment would therefore cost roughly 5–10× more, about $1.50–3 on Haiku, before prompt caching.

## 2. Does memory help Hermes?

**Experiment id:** `exp-f49ee0db62fa`

### Hypothesis

With memory on, Hermes can carry facts from one session to the next, so it passes the three memory tasks (a fact is given in session 1 and asked for in session 2). With memory off it can't, and the other 22 tasks don't care.

### Setup

| | A | B |
|---|---|---|
| Harness | Hermes Agent (pinned commit `0f602c5`) | same |
| Model | `anthropic/claude-haiku-5-5` | same |
| Settings | all 5 skills, **memory off** | same, **memory on** |
| Config | `configs/hermes-haiku-no-memory.json` | `configs/hermes-haiku-memory.json` |

All 25 tasks, N = 5, so 250 trials. It ran at concurrency 2 in the Docker container and took 57 minutes, alongside experiment 3.

### Results

| | Pass rate | Cost / trial | Latency | Tokens in / out | Infra errors |
|---|---|---|---|---|---|
| A: memory off | 88.0% | $0.0082 | 21.2 s | 56,112 / 903 | 0 |
| B: memory on | **97.6%** | $0.0066 | 20.6 s | 58,240 / 830 | 0 |

- **Δ pass rate: +9.6 pp, 95% CI [−1.6, +23.2].** McNemar: 15 pairs passed only with memory and 3 only without, p = 0.008.
- **Verdict:** "B is better on the tasks that differ, but the effect is concentrated in a few tasks, so the task-level interval includes 0." That's the honest reading. Memory matters a lot on 3 tasks and not at all on the other 22, so whether it "helps overall" depends on how many memory tasks you put in the set.
- **Per task:** `memory-preferences` and `memory-service-config` go from 0% to 100%, and `memory-staging-host` from 40% to 100%. `judge-incident-update` drops from 100% to 60%, the same noisy judge task as in experiment 1 (p = 0.44). The rest are at ceiling.

### What the platform caught

This is the third Hermes memory run. Run 1 (`exp-e4294d73b390`) was stopped after Hermes's gateway kept disconnecting under load, which is why trials are now retried with backoff in a fresh sandbox. The runs also had isolation problems, and trajectory inspection is what showed them.

1. **Run 2 (`exp-f5d27106846f`): memory off leaked.** Memory-off trials reused one Hermes home across sessions, and Hermes keeps a transcript store there, so session 2 could still find session 1. Fix: a fresh home per session when memory is off (`2ce49c2`).
2. **Run 3, this one: a smaller leak.** The 2 memory-off passes on `memory-staging-host` (trials `e4b262604aef`, `2ce39624eb87`) are not real. In session 2 the agent searched its trial directory, found session 1's Hermes log, and answered from it, saying so honestly ("The only reference I found is a note in another session's log"). Every session home now gets deleted before the next session starts. A test checks this, but the fix landed after this run. Counting those 2 trials as failures gives memory off 86.4% and Δ +11.2 pp. The verdict doesn't change.
3. **Agent isolation.** The earlier Hermes runs also showed agents listing files outside their sandbox. Agent code now runs as a separate `agent` user that can't read tasks, results or other trials (`d1dcdcf`). A scan of this run found no reads outside each trial's own directory.

**Later correction (experiment 11).** The memory-off arm still shared the work directory across sessions, so an agent could leave itself notes there. Experiment 11 showed the baseline agent doing exactly that. Rerun with a fresh workspace per session (and the snapshot leak fixed), Hermes memory gives **+14.4 pp [+1.6, +29.6], B is better** (`exp-8812ead2a842`). The direction here was right; the size and the verdict were understated.

### Cost and latency

Hermes sends about 11× the input tokens of the baseline (57k vs 4.9k per trial), mostly its system prompt and tool schemas, and is 4× slower (21 s vs 5 s). Memory on is *cheaper* than memory off ($0.83 vs $1.03 for 125 trials), because without memory the agent spends steps searching for a fact that isn't there.

```
cost = 250 trials × avg $0.0074 + judge $0.07 = $1.86 + $0.07 ≈ $1.93
```

## 3. Can a local model replace Haiku?

**Experiment id:** `exp-846c597dac0f`

### Hypothesis

`qwen3:8b` running locally on Ollama is free and private. If it comes close to Haiku on these tasks, it's a good default for cheap iteration.

### Setup

| | A | B |
|---|---|---|
| Harness | baseline | same |
| Model | `anthropic/claude-haiku-5-5` | `ollama/qwen3:8b` (32k context, **thinking off**) |
| Settings | all 5 skills, memory on | same |
| Config | `configs/baseline-haiku-skills.json` | `configs/baseline-qwen3-8b-local.json` |

All 25 tasks, N = 3, so 150 trials, at concurrency 1 because Ollama serves one request at a time. It took 82 minutes on a laptop, in parallel with experiment 2. Thinking is off because in a first attempt (`exp-76ba9b667606`, stopped) thinking mode made trials slow enough to hit timeouts.

### Results

| | Pass rate | Cost / trial | Latency | Tokens in / out | Infra errors |
|---|---|---|---|---|---|
| A: Haiku | **97.3%** | $0.00086 | 5.0 s | 4,878 / 735 | 0 |
| B: qwen3:8b local | 33.3% | $0 | 10.9 s | 5,404 / 205 | 3 |

- **Δ pass rate: −63.9 pp, 95% CI [−81.9, −44.4].** McNemar: 46 pairs passed only with Haiku and 0 only with qwen. **Verdict: A is better.**
- **72 pairs over 24 tasks, not 75 over 25.** All 3 qwen trials of `log-503-count` hit the timeout after reading a large log file. A single request took longer than the 2-minute request limit, and the runner counted that retry as waiting on a rate limit, so the trials were classed as infrastructure errors and left out. That favours qwen slightly. It was a bug: only real 429 and 503 responses count as rate-limit waits now, and a slow model's timeouts count against it.
- With N = 3, no single task reaches p < 0.05 (the best possible is p = 0.10), so every per-task row says "noise". The overall difference is clear because it is the same across 16 tasks.

### Why qwen fails

- **It never runs its code.** Across the 15 coding trials, qwen wrote a file and declared it done without once calling `run_python`. Haiku tested its code in all 15. On `code-roman` (trial `3f46af361d28`) qwen's converter passes 2 of 3 hidden tests and fails on rejecting `IIII`, which a single test run would have caught.
- **It uses skills correctly.** qwen loaded the right skill in all 15 skill-task trials, the same as Haiku, but then got the computation wrong on 4 of the 5 tasks.
- **Failure categories:** 33 wrong answer, 6 grader disagreement, 3 wrong tool, 3 gave up early, 3 step exhaustion. It gives up fast: 205 output tokens per trial against Haiku's 735.

### Cost and latency

qwen costs nothing per token, but it's twice as slow on a laptop GPU and is only usable for the simple lookup and file tasks it passes (`csv-revenue-west`, `json-config-lookup`, `file-csv-to-json`, and similar). Haiku ran the same 75 trials for $0.064.

## 4. Does thinking mode rescue the local model?

**Experiment id:** `exp-c7fb9622ff55`

### Hypothesis

qwen3:8b has a thinking mode. Experiment 3 ran it off for speed, so the obvious objection is that it was handicapped. With thinking on it should plan better, and maybe check its work.

### Setup

The same as experiment 3, with one change: the qwen config sets `thinking: true` (`configs/baseline-qwen3-8b-local-thinking.json`). The Haiku config is identical. All 25 tasks, N = 3, so 150 trials at concurrency 1. It took about 7 hours on the laptop.

### Results

| | Pass rate | Latency | Tokens in / out | Timeouts | Infra errors |
|---|---|---|---|---|---|
| A: Haiku | **98.7%** | 5.7 s | 5,142 / 773 | 0 | 0 |
| B: qwen3:8b, thinking on | 37.3% | 139.5 s | 2,193 / 1,534 | 20 | 0 |

- **Δ pass rate: −61.3 pp, 95% CI [−78.7, −42.7].** McNemar: 46 pairs passed only with Haiku and 0 only with qwen. **Verdict: A is better.**
- **Against thinking off (experiment 3):** qwen passes 37.3% instead of 33.3%, but that is two separate experiments, so it isn't a paired comparison. Per task, the difference is not "a bit better everywhere":
  - **Better with thinking:** `memory-preferences`, `word-frequency`, `judge-code-review`, `code-fix-binary-search` and two skill tasks went from 0% to 33–100%. These are the tasks that need a plan or careful reading.
  - **Worse with thinking:** `csv-revenue-west`, `file-csv-to-json` and `skill-qlog-bytes` went from 100% to 0%. These are simple lookups that thinking-off qwen did reliably.
  - **Timeouts:** 20 of 75 trials hit the 5-minute limit, mostly coding tasks (all 3 trials of four of them). The model spends its time thinking and runs out of clock before it finishes.
- **It still never runs its code.** In all 15 coding trials, thinking on or off, qwen never called `run_python`. Thinking doesn't change that habit.

### What the platform caught

The first attempt at this run had all its qwen trials marked as infrastructure errors. A thinking step can take longer than the 2-minute per-request limit. The runner counted the retry after that as waiting on a rate limit, so it called each trial timeout an infrastructure error and retried the trial three times. The result would have been about 20 hours of running and no qwen data at all. Only real 429 and 503 responses count as rate-limit waits now (`d71429c`), and a slow model's timeouts count against it. The same bug explains experiment 3's three errored trials.

## Overnight experiments (23–24 Nov)

Experiments 5–14 ran overnight in Docker, in two lanes: the Claude API, and the local GPU through Ollama. All of them use **Claude Sonnet 5.5 as the judge**. The Groq judge used in experiments 1–4 hit its free-tier cap of 200k tokens a day early in the night (see "What didn't work"). Sonnet had the best and most stable agreement with the labels (experiment 14). The judge is part of an experiment's id, so these results are never mixed with the Groq-judged ones. Compare configs within an experiment, not absolute pass rates across judges. Unless noted, all 25 tasks at N = 5.

### 5. A/A test: does the platform report differences that aren't there?

Two Haiku configs that differ only in a setting that never binds (`token_budget` 300,000 vs 300,001). `exp-db4eea39be18`.

- **−1.6 pp, CI [−8.8, +3.2], McNemar 4 vs 2, p = 0.69. Verdict: no detectable difference.** The platform's false-positive check passes.
- One task still swung 80% → 20% (`judge-code-review`, p = 0.21, labelled noise). Per-task swings of 60 pp happen by chance at N = 5, which is why the verdict rests on the aggregate.

### 6. How much does code execution matter?

Haiku with skills, with and without `run_python`. `exp-a8e923735fc6`.

- **95.2% → 76.8%, −18.4 pp, CI [−32.8, −5.6]. Verdict: A is better.**
- `log-503-count`, `primes-sum` and `word-frequency` go from 100% to 0% (each p = 0.01). These are counting tasks that need computation, not reasoning.
- Taking the tool away makes trials **34% more expensive**: output tokens rise 80% as the model tries to count in prose.

### 7. Hermes vs baseline, paired

Identical settings (Haiku, all skills, memory on); only the harness differs. `exp-35d692289fa0`. The comparison in the conclusions used to be across experiments; this is the paired version.

- **95.2% vs 96.0%, +0.8 pp, CI [−4.0, +6.4]. No detectable difference.**
- Hermes: **10.7× the input tokens** (57k vs 5.3k per trial), **6.6× the cost** ($0.0061 vs $0.0009 per trial) and **3.7× the latency** (18.2 s vs 4.9 s).

### 8. Does a stronger model help? Haiku vs Sonnet 5.5

Baseline with skills. `exp-c64dffeffdc3`.

- **95.2% vs 92.8%, −2.4 pp, CI [−10.4, +4.0]. No detectable difference**, at **16× the cost** ($1.76 vs $0.11 for 125 trials).
- Sonnet loses `judge-decline-email` (100% → 20%, p = 0.05). It loaded the `acme-finance` skill in all 5 trials and rewrote "Q3 2027" as ACME's fiscal months ("August–October 2027"). The judge marked that as an invented fact. Haiku never loaded the skill for that task. Two lessons: a stronger model applies skills more eagerly, including where the user didn't ask, and the judge can't see the skills the agent had, so skill-derived content reads as invented.

### 9. Does telling the agent to test its code help?

A new `verify` setting adds one line to the baseline system prompt: "Before you finish, run any code you wrote with run_python on a few examples and fix what fails."

| | Coding trials that ran code | Pass rate | Δ | Experiment |
|---|---|---|---|---|
| Haiku | 25/25 → 25/25 | 92.8% → 94.4% | +1.6 pp, noise (cost +5%) | `exp-ae9ffa2a6981` |
| qwen3:8b, N = 2 | **0/10 → 6/10** | 32.0% → 32.0% | 0, identical on every task | `exp-a03daa999586` |

The hypothesis was that the small model fails because it never tests (experiments 3 and 4), and that a nudge would gain +5–10 pp. It was wrong. The nudge changed the habit but not the outcome. qwen now runs tests and ignores what they show. On `code-roman` it runs `from_roman('IC')` under its own comment "Should raise ValueError", gets `99`, and replies "successfully created and tested". On `code-fix-binary-search` it calls the function without importing it, gets a `NameError` twice, and stops. The bottleneck is reading test results, not running tests.

### 10. Does experiment 1's conclusion survive a different judge?

Experiment 1 rerun unchanged, with the Sonnet judge. `exp-19fc95995189`.

- **+21.6 pp, CI [+7.2, +37.6], McNemar 28 vs 1. Verdict: B is better** (Groq judge: +19.2 pp). All five skill tasks are again "likely real".
- Absolute rates shift (no skills: 74.4% vs 79.2%). The conclusion holds; the levels depend on the judge.

### 11. What does "memory off" actually turn off?

Baseline Haiku with skills, memory on vs off. `exp-693d645ab768`.

- **+5.6 pp, CI [−0.8, +13.6], McNemar 8 vs 1, p = 0.04. Verdict: concentrated.** The same shape as experiment 2.
- Memory off still passed memory tasks: `memory-staging-host` 100%, `memory-service-config` 60%. The traces show why. With no memory tool, Haiku writes its own notes file in session 1 (`NOTES.md`, `bluefin_service.md`), and session 2 finds it, because the work directory persists across the sessions of a trial. **Every memory-off trial that wrote a note passed (10/10), and every one that didn't failed (5/5).**
- Follow-up with a new `fresh_workspace` setting that restores the fixtures between sessions (`exp-ff33f1858843`, 3 memory tasks, N = 10): memory off with a shared workspace passes **50%**, and with a fresh workspace **0%** (15 vs 0 discordant pairs).
- So "memory off" only removed the memory *tool*, not persistence. The memory effect in experiments 2 and 11 is understated. Memory-off configs now use `fresh_workspace` in both harnesses, and the UI sets it whenever memory is off. Rerun with fresh workspaces:

| Harness | Memory off → on | Δ, 95% CI | Verdict | Experiment |
|---|---|---|---|---|
| Baseline | 84.8% → 98.4% | **+13.6 pp [+1.6, +28.0]**, McNemar 19 vs 2 | **B is better**; all three memory tasks 0% → 100% | `exp-191e63a25d1e` |
| Hermes | 81.6% → 96.0% | **+14.4 pp [+1.6, +29.6]**, McNemar 20 vs 2 | **B is better**; all three memory tasks 0% → 100% | `exp-8812ead2a842` |

With persistence removed, the memory effect is clear rather than "concentrated" in both harnesses: the interval now excludes 0, and the two harnesses agree within a point.

The Hermes rerun found a third leak, this time in our own harness. With memory off, Hermes searched its `state/` directory and read `snapshot-0-after/memory.md`, the copy of its memory the harness saves after each session for the trace. Snapshots are now deleted as soon as they're read (`59355cb`), and the leaky run (`exp-23e9d643f2f7`) is archived. That run also showed `judge-decline-email` falling from 100% to 20% with memory on; the clean rerun has it at 80% → 80%, so it was one of the 25 per-task tests coming up by chance.

### 12. Does temperature 0 make repeated trials pointless?

qwen3:8b, temperature 0 vs 0.7. `exp-5e84b52f22b3`.

- **32.0% vs 32.0%, CI [−8, +8]. No difference** in pass rate.
- At temperature 0 qwen gave **identical final answers on 25/25 tasks across all 5 trials**, and no task had mixed outcomes. Its repeated trials are copies, so N > 1 adds no information, and McNemar over trial pairs counts the same outcome five times. The task-level bootstrap is unaffected, because it resamples tasks.
- At 0.7 the passes move around. Easy tasks get worse (`csv-revenue-west` 100% → 40%) and hard ones sometimes pass (`word-frequency` 0% → 40%; `code-dedupe-records`, `date-weekdays`, `memory-preferences` 0% → 20%). Coverage at pass@5 rises from 8 to 12 tasks, which a best-of-n with a checker could use.
- It never ran its code at either temperature (0/25 coding trials).

### 13. Do skills help the small model?

qwen3:8b, skills off vs on, N = 1 (deterministic at temperature 0). `exp-9e081506a0e4`.

- **29.2% vs 32.0%, no detectable difference.** Only `skill-qlog-bytes` flips to a pass; the other four skill tasks fail even with the skill loaded. That matches experiment 3: qwen finds and reads the right skill but gets the computation wrong.

### 14. Which judge to trust?

Each judge graded the 32 labelled answers (`judge-validation/`) more than once, to separate accuracy from randomness. Results are in `judge-validation/runs/`.

| Judge | κ per run | Verdict flips between runs | Cost per run |
|---|---|---|---|
| Claude Sonnet 5.5 | 0.93, 0.93 | 0/32 | $0.21 |
| Groq qwen3.8-27b | 0.87 | (one run) | free, 200k tokens/day |
| Claude Haiku 5.5 | 0.87, 0.80, 0.93 | 3/32 | $0.013 |
| Claude Opus 5.5 | 0.80, 0.80 | 0/32 | $0.50 |
| qwen3:8b, local | 0.69, 0.74 | 2/31 (plus one empty reply) | free; every error is a pass the labels fail |

- The biggest judge isn't the most accurate. Opus is consistently stricter than the labels, on the same three items both times (`incident-04`, `code-08`, `release-05`).
- A free local judge is too lenient. qwen3:8b never failed a good answer, but it passed 4–5 of the subtle failures the set was built around, which is the expensive direction for a judge.
- A single validation run of a cheap judge is noisy. Haiku's κ varied as much as the gap between judges, and it flipped on the same borderline items Opus fails.
- Task-design fix found through the judge: the `judge-incident-update` rubric required an apology that the prompt never asked for, so the task's pass rate depended on how strictly the judge read rubric item 6 (Groq passed answers without one, Sonnet failed about 80% of them). The prompt now asks for the apology (`3c0c923`).

### Late runs: qwen3:30b-a3b

The laptop was on battery. It reached 1% and the Mac was forced to sleep from 02:32 to 08:52, which `caffeinate` can't prevent, so the 30B runs finished in the afternoon instead. The 30B model ignores `think: false` and writes its reasoning into the answer (3–8k output tokens, 95–315 s per trial). Mixing 8B and 30B configs in one experiment also makes Ollama swap 18 GB on every trial (5 trials in 10 minutes), so local models of different sizes belong in separate experiments.

- **Test nudge on qwen3:30b-a3b** (`exp-0ac72af23cb5`, N = 1, temperature 0): 52.0% → 52.0%, 2 vs 2 discordant tasks, no difference. The 30B model passes 20 points more than the 8B (32%), but it didn't run code in any coding trial, with or without the nudge (0/5 each), where the 8B went 0/10 → 6/10. The nudge also added 4 → 7 timeouts and +31 s median latency.
- **qwen3:30b-a3b as a judge** (1 run): of 32 items, 21 came back empty or as broken JSON, because the reasoning it writes into the answer eats the output. The 11 it did parse all matched the labels. Not usable as a judge without a parser fix or real thinking control.

### Overnight cost

$10.20 in total: $4.66 for agent tokens, $4.11 for Sonnet judge calls and $1.46 for judge validation. The Sonnet comparison (experiment 8) and Hermes (experiment 7) were most of the agent spend.

## Conclusions

- **Skills and memory both work, and only where they're needed.** Each one turns tasks that are impossible without it into reliable passes, and changes nothing elsewhere. The platform's per-task view shows that, and the "concentrated" verdict keeps a 3-task effect from being sold as a general improvement.
- **The harness costs more than it adds on this set.** Hermes and the baseline both pass about 98% with the right features on, but Hermes uses 11× the tokens and 4× the time. Hermes's extra tools would need harder, longer tasks to pay off.
- **Model size matters more than price here.** The local 8B model is free but fails two thirds of the tasks, mostly because it doesn't check its work. Thinking mode doesn't fix that: it trades some tasks for others and makes every trial 13× slower.
- **Cheaper is fine on this set, and bigger isn't better.** Sonnet 5.5 cost 16× Haiku for the same pass rate, and Opus was the least accurate judge. The task set is near the ceiling for Claude models, so it can't separate them. Harder tasks would be needed for that.
- **Small models fail at judgement, not habit.** Prompting qwen3:8b to test its code made it run tests but not act on them (experiment 9). Model capacity is the bottleneck, not instructions.
- **Measure what a setting actually does.** "Memory off" left the filesystem as memory (experiment 11), and "thinking off" was ignored by the 30B model. Both were caught by reading traces, not by the pass rates.
- **The statistics behave.** The A/A test found nothing, the skills result held under a second judge, and N = 2 would have been enough for every real effect found.
- **Trajectory inspection earned its place.** Two of the three Hermes runs had isolation leaks that the numbers alone didn't show. Reading the traces found them.

## What didn't work

- **Groq as judge for a night of runs.** The free tier allows 200k tokens a day for `qwen3.8-27b`, and four parallel experiments used that up within the hour. The adapter then obeyed "try again in 10m" hints, which looked like a hang. The affected partial runs are archived, and experiments 5–14 use Sonnet 5.5.
- **Two infrastructure bugs, fixed on the way.** Runs started with `docker compose exec` got umask 022, so the agent user couldn't create the Hermes home or write files from `run_python` (`c05c36c`; the partial runs are archived). And litellm's request timeout didn't fire on dropped connections, so runs hung on dead sockets (`1197d80`, now an asyncio deadline per call).
- **Running overnight on battery.** See "Not finished" above.

- **Free-tier comparison (gpt-oss-120b vs 20b on Groq), runs `exp-a8f0b66439bc` and `exp-e69a46b046f0`, abandoned.** Groq's free tier allows 200k tokens per model per day, and the run needed over a million. Its partial results are kept in the database but not used. Two lessons from it are now built into the platform: rate-limit waits that run out the clock are infrastructure errors, not agent timeouts (`c866a76`), and malformed tool calls rejected by the provider count against the agent (`e039cc2`).
- **Hermes on Claude.** Requests were rejected with "credit balance too low" while the same key worked through LiteLLM and curl. Capturing Hermes's request with a local proxy and replaying it showed why: Hermes 0.19.0 treats any Anthropic key that doesn't start with `sk-ant-api` as a Claude Code subscription token, adds a "You are Claude Code" identity to the system prompt, and the request is then billed as a subscription request. The Console now issues `sk-ant-usr-` keys, which Hermes fixed on its main branch (#133856) but hasn't released. The platform now pins Hermes to that commit, installed from source, and Hermes runs on Claude: the memory task fails with memory off and passes with memory on, with the memory write and read visible in the trace.
