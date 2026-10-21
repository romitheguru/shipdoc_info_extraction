"""How well do review flags predict errors? Precision/recall at three levels.

    uv run python -m eval.flags --pred P.json --flags P_review_flags.json --set bakeoff

- doc:   a doc is flagged if it has any flag; it is wrong if it is not fully correct (score.py's `exact`).
- value: units are header fields and predicted rows. A header field is wrong if score.py's `same` fails;
         a predicted row is wrong if it is not matched one-to-one to an identical gold row. A row counts
         as flagged if any of its fields is, or the doc has a `rows` or `doc` flag.
         Missing rows (fewer predicted than gold) can't be flagged at this level; they show up at doc level.
- signal: precision of each reason on its own, and how many errors only that reason catches.
"""
import argparse, json, os, sys
from collections import Counter, defaultdict

from eval.data import ROOT
from eval.evaluate import gold_set

sys.path.insert(0, ROOT)
import score  # noqa: E402


def correct_rows(pred_rows, gold_rows):
    """Indices of predicted rows matched one-to-one to an identical gold row (score.py's pass 1)."""
    free_g, ok = list(range(len(gold_rows))), set()
    for pi, p in enumerate(pred_rows):
        for gi in free_g:
            if score.row_ok(p, gold_rows[gi]):
                free_g.remove(gi)
                ok.add(pi)
                break
    return ok


def units(pred, gold, flags):
    """[(unit, wrong, reasons)] for one doc."""
    out = []
    doc_reason = flags.get("doc")
    rows_reason = flags.get("rows")
    ph = pred.get("header", {})
    for k in score.HEADER[gold["doc_type"]]:
        wrong = not score.same(k, ph.get(k), gold["header"].get(k))
        reasons = [r for r in (flags.get(f"header.{k}"), doc_reason) if r]
        out.append((f"header.{k}", wrong, reasons))
    ok = correct_rows(pred.get("line_items", []), gold["line_items"])
    for i, r in enumerate(pred.get("line_items", [])):
        reasons = [v for t, v in flags.items() if t.startswith(f"row.{i}.")] + [r for r in (rows_reason, doc_reason) if r]
        out.append((f"row.{i}", i not in ok, reasons))
    return out


def pr(tp, fp, fn):
    p = tp / (tp + fp) if tp + fp else float("nan")
    r = tp / (tp + fn) if tp + fn else float("nan")
    return f"precision {100 * p:5.1f}%  recall {100 * r:5.1f}%  (flagged {tp + fp}, errors {tp + fn}, caught {tp})"


def report(pred, flags, gold):
    lines = []
    tp = fp = fn = 0
    for d, g in gold.items():
        wrong = not score.score_doc(pred.get(d), g)["exact"]
        flagged = bool(flags.get(d))
        tp, fp, fn = tp + (wrong and flagged), fp + (flagged and not wrong), fn + (wrong and not flagged)
    lines.append(f"doc    {pr(tp, fp, fn)}")

    tp = fp = fn = 0
    by_reason, only = defaultdict(Counter), Counter()
    for d, g in gold.items():
        for _, wrong, reasons in units(pred.get(d, {}), g, flags.get(d, {})):
            tp, fp, fn = tp + (wrong and bool(reasons)), fp + (bool(reasons) and not wrong), fn + (wrong and not reasons)
            for r in {r.split(":")[0] for r in reasons}:
                by_reason[r]["tp" if wrong else "fp"] += 1
            if wrong and len({r.split(":")[0] for r in reasons}) == 1:
                only[reasons[0].split(":")[0]] += 1
    lines.append(f"value  {pr(tp, fp, fn)}")
    for r, c in sorted(by_reason.items(), key=lambda x: -sum(x[1].values())):
        lines.append(f"  {r[:40]:40s} flags {c['tp'] + c['fp']:4d}  precision {100 * c['tp'] / (c['tp'] + c['fp']):5.1f}%  "
                     f"errors caught {c['tp']:3d} (only by this signal {only[r]})")
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--flags", help="defaults to <pred>_review_flags.json")
    ap.add_argument("--set", default="dev")
    a = ap.parse_args()
    flags_path = a.flags or os.path.splitext(a.pred)[0] + "_review_flags.json"
    gold = gold_set(a.set)
    print(report(json.load(open(a.pred)), json.load(open(flags_path)), gold))


if __name__ == "__main__":
    main()
