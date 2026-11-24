import collections
import json
import sqlite3
import statistics as st
import sys

CODING = {
    "code-dedupe-records",
    "code-fix-binary-search",
    "code-parse-duration",
    "code-roman",
    "code-slugify",
}

c = sqlite3.connect("/app/results/evals.db")
label = dict(c.execute("select id, label from configs"))
for exp in sys.argv[1:]:
    name = c.execute("select name from experiments where id=?", (exp,)).fetchone()[0]
    print(f"\n## {name} ({exp})")
    rows = c.execute(
        "select t.config_id, t.task_id, t.trial_index, t.passed, t.status, t.cost_usd, t.latency_ms, "
        "t.input_tokens, t.output_tokens, x.events from trials t join traces x on x.trial_id=t.id "
        "where t.experiment_id=?",
        (exp,),
    ).fetchall()
    per = collections.defaultdict(list)
    for cfg, task, i, passed, status, cost, lat, tin, tout, ev in rows:
        per[cfg].append((task, i, passed, status, cost, lat, tin, tout, json.loads(ev)))
    for cfg, xs in per.items():
        ok = [x for x in xs if x[3] != "error"]
        coding = [x for x in ok if x[0] in CODING]
        ran = sum(
            1
            for x in coding
            if any(
                tc["name"] in ("run_python", "execute_code", "terminal")
                for e in x[8]
                if e["type"] == "model_response"
                for tc in (e.get("tool_calls") or [])
            )
        )
        steps = [sum(1 for e in x[8] if e["type"] == "model_response") for x in ok]
        finals = collections.defaultdict(set)
        outcomes = collections.defaultdict(set)
        for x in ok:
            fr = [
                e.get("text")
                for e in x[8]
                if e["type"] == "model_response" and not e.get("tool_calls")
            ]
            finals[x[0]].add((fr[-1] or "").strip()[:400] if fr else None)
            outcomes[x[0]].add(x[2])
        multi = [t for t in finals if sum(1 for x in ok if x[0] == t) > 1]
        same = sum(1 for t in multi if len(finals[t]) == 1)
        mixed = sum(1 for t in outcomes if len(outcomes[t]) > 1)
        n_pass = sum(1 for x in ok if x[2])
        status = collections.Counter(x[3] for x in xs)
        print(
            f"- {label[cfg]}: n={len(xs)} {dict(status)} pass={n_pass}/{len(ok)} "
            f"cost=${sum(x[4] or 0 for x in xs):.3f} lat_med={st.median([x[5] or 0 for x in ok]) / 1000:.1f}s "
            f"steps_med={st.median(steps) if steps else '-'} max={max(steps) if steps else '-'} "
            f"coding trials that ran code={ran}/{len(coding)} identical-final-answer tasks={same}/{len(multi)} "
            f"mixed-outcome tasks={mixed}"
        )
