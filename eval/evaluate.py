"""Score a predictions file on an evaluation set, with slices. Uses score.py's own scoring.

    uv run python -m eval.evaluate --pred preds.json --set dev
    uv run python -m eval.evaluate --pred preds.json --set bakeoff --out report.json
    uv run python -m eval.evaluate --pred preds.json --set fold:2     # held-out suppliers of fold 2

Sets: train | dev | all | bakeoff | fold:K. Documents missing from --pred score zero, as in score.py.
For fold:K every scored doc is from suppliers held out of fold K, i.e. the `unseen` slice.
"""
import argparse, json, os, sys

from eval.data import EVAL, ROOT, all_labels, group, load_labels, slices

sys.path.insert(0, ROOT)
import score  # noqa: E402  official scorer


def gold_set(name):
    if "/" in name:  # intersection, e.g. dev/fold:4 = the fold-4 docs of dev
        a, b = (gold_set(n) for n in name.split("/", 1))
        return {d: g for d, g in a.items() if d in b}
    if name in ("train", "dev"):
        return load_labels(name)
    docs = all_labels()
    if name == "all":
        return docs
    if name == "bakeoff":
        return {d: docs[d] for d in json.load(open(os.path.join(EVAL, "bakeoff.json")))}
    if name.startswith("fold:"):
        folds, k = json.load(open(os.path.join(EVAL, "folds.json"))), int(name.split(":")[1])
        return {d: g for d, g in docs.items() if folds[group(g)] == k}
    raise SystemExit(f"unknown set {name}")


def evaluate(pred, gold):
    per = {d: score.score_doc(pred.get(d), g) for d, g in gold.items()}
    report = {"all": score.aggregate(list(per.values()))}
    tags = {d: slices(g) for d, g in gold.items()}
    for t in next(iter(tags.values())):
        for val in (True, False):
            sub = [per[d] for d in gold if tags[d][t] == val]
            if sub:
                report[f"{t}={'yes' if val else 'no'}"] = score.aggregate(sub)
    report["per_doc"] = {d: {"exact": r["exact"], "header_wrong": [k for k, ok in r["header"].items() if not ok],
                             "rows_gold": r["rows_gold"], "rows_pred": r["rows_pred"], "rows_full": r["rows_full"],
                             "false_fill": r["false_fill"]} for d, r in per.items()}
    return report


def show(report, missing):
    a = report["all"]
    print(f"documents {a['documents']}  (missing from predictions: {missing})")
    print(f"OVERALL {100 * a['OVERALL']:6.2f}   header {100 * a['header_field_accuracy']:6.2f}%   "
          f"row P/R/F1 {100 * a['row_precision']:5.1f}/{100 * a['row_recall']:5.1f}/{100 * a['row_f1']:5.1f}   "
          f"exact {100 * a['documents_fully_correct']:5.1f}%   false fill {100 * a['false_fill_rate']:5.1f}% of {a['illegible_fields']}")
    print("header by field: " + "  ".join(f"{k} {100 * v:.0f}" for k, v in a["header_by_field"].items()))
    if a.get("line_item_field_accuracy"):
        print("row fields (matched pairs): " + "  ".join(f"{k} {100 * v:.1f}" for k, v in a["line_item_field_accuracy"].items()))
    for k, v in report.items():
        if k not in ("all", "per_doc"):
            print(f"   {k:<20} n={v['documents']:>3}  overall {100 * v['OVERALL']:6.2f}  header {100 * v['header_field_accuracy']:6.2f}"
                  f"  rowF1 {100 * v['row_f1']:6.2f}  exact {100 * v['documents_fully_correct']:6.2f}  ffill {100 * v['false_fill_rate']:5.1f}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--set", default="dev")
    ap.add_argument("--out")
    a = ap.parse_args()
    gold, pred = gold_set(a.set), json.load(open(a.pred))
    report = evaluate(pred, gold)
    show(report, sum(d not in pred for d in gold))
    if a.out:
        json.dump(report, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
