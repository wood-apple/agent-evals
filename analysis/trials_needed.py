import itertools
import random
import sys

from evals.stats import compare
from evals.store import Store

store = Store("/app/results/evals.db")
for exp_id in sys.argv[1:]:
    exp = store.get_experiment(exp_id)
    trials = store.get_trials(exp.id)
    a, b = exp.config_ids[:2]
    full = compare(trials, a, b, seed=exp.seed)["verdict"]
    print(f"\n{exp.name}: full N=5 verdict = {full}")
    for n in (1, 2, 3):
        subsets = list(itertools.combinations(range(5), n))
        random.Random(0).shuffle(subsets)
        verdicts = {}
        for keep in subsets[:10]:
            sub = [t for t in trials if t.trial_index in keep]
            v = compare(sub, a, b, seed=exp.seed)["verdict"]
            verdicts[v] = verdicts.get(v, 0) + 1
        print(f"  N={n}: " + "; ".join(f"{k} x{v}" for k, v in verdicts.items()))
