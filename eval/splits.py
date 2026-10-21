"""Build the evaluation sets (deterministic; rerunning gives identical files).

    uv run python -m eval.splits

eval/folds.json    layout group -> fold 0..4. Leave-supplier-out over train+dev (500 docs):
                   anything learned (few-shot examples, thresholds) for fold k may only use docs
                   outside fold k; fold k's docs are then the `unseen` slice.
eval/bakeoff.json  40 dev docs for the step-2 bake-off, covering every dev layout group and
                   enriched for the hard slices.
"""
import json, os, random
from collections import Counter, defaultdict

from eval.data import EVAL, all_labels, group, load_labels, slices

N_FOLDS = 5
SEED = 0
BAKEOFF_INVOICES, BAKEOFF_WAYBILLS = 32, 8
# minimum hard-slice coverage among the bake-off invoices
TARGETS = {"illegible": 6, "multi_page": 12, "scanned": 14, "repeated_parts": 8}


def make_folds(docs):
    """Greedy balance: biggest groups first, each to the fold with the fewest docs of its kind."""
    size = Counter(group(d) for d in docs.values())
    folds = {}
    for kind in ("INV:", "AWB:"):
        load = [0] * N_FOLDS
        for g in sorted((g for g in size if g.startswith(kind)), key=lambda g: (-size[g], g)):
            k = min(range(N_FOLDS), key=lambda i: (load[i], i))
            folds[g] = k
            load[k] += size[g]
    return folds


def make_bakeoff(dev):
    rng = random.Random(SEED)
    tags = {d: slices(doc) for d, doc in dev.items()}
    by_group = defaultdict(list)
    for d, doc in sorted(dev.items()):
        by_group[group(doc)].append(d)
    need = dict(TARGETS)

    def gain(d):
        return sum(need[t] > 0 for t in need if tags[d][t]) + rng.random() * 0.5

    picked = []
    inv_groups = sorted(g for g in by_group if g.startswith("INV:"))
    for g in inv_groups:                                  # one doc per supplier first
        d = max(by_group[g], key=gain)
        picked.append(d)
        for t in need:
            need[t] -= tags[d][t]
    pool = [d for g in inv_groups for d in by_group[g] if d not in picked]
    while len(picked) < BAKEOFF_INVOICES:                 # then fill the hard slices
        d = max(pool, key=gain)
        pool.remove(d); picked.append(d)
        for t in need:
            need[t] -= tags[d][t]
    awb_groups = sorted(g for g in by_group if g.startswith("AWB:"))
    rng.shuffle(awb_groups)
    for g in awb_groups[:BAKEOFF_WAYBILLS]:              # one waybill per carrier brand
        picked.append(rng.choice(by_group[g]))
    return sorted(picked)


def main():
    docs = all_labels()
    folds = make_folds(docs)
    bake = make_bakeoff(load_labels("dev"))
    json.dump(folds, open(os.path.join(EVAL, "folds.json"), "w"), indent=1, sort_keys=True)
    json.dump(bake, open(os.path.join(EVAL, "bakeoff.json"), "w"), indent=1)

    print("fold  groups (docs)")
    for k in range(N_FOLDS):
        gs = sorted(g for g, f in folds.items() if f == k)
        n = Counter(group(d) for d in docs.values())
        print(f"  {k}   {sum(n[g] for g in gs):>3} docs: " + ", ".join(f"{g.split(':')[1].split()[0]}({n[g]})" for g in gs))
    t = Counter(t for d in bake for t, v in slices(docs[d]).items() if v)
    print(f"\nbake-off: {len(bake)} docs, {len({group(docs[d]) for d in bake})} layout groups, slices {dict(t)}")


if __name__ == "__main__":
    main()
