"""Size-sweep table (PLAN.md A2): accuracy, false fills and speed per model on the bake-off set.

    uv run python -m bakeoff.sweep_report Qwen3-VL-2B-Instruct-8bit Qwen3-VL-4B-Instruct-8bit ...

Each tag reads bakeoff/preds/vlm_<tag>_bakeoff.json and the per-doc stats in bakeoff/cache/vlm_<tag>/.
Docs whose output didn't parse are missing from the predictions and score zero, as in score.py.
"""
import json, os, statistics, sys

from bakeoff.ocr_run import CACHE
from eval.data import ROOT
from eval.evaluate import evaluate, gold_set

sys.path.insert(0, ROOT)
import score  # noqa: E402


def row(tag, gold):
    pred = json.load(open(os.path.join(ROOT, "bakeoff", "preds", f"vlm_{tag}_bakeoff.json")))
    r = evaluate(pred, gold)
    stats = [json.load(open(os.path.join(CACHE, f"vlm_{tag}", d + ".json"))) for d in gold]
    secs = sorted(s["secs"] for s in stats)
    peaks = [s["peak_gb"] for s in stats if s.get("peak_gb")]
    pn = lambda k: 100 * r[k]["line_item_field_accuracy"]["supplier_part_number"]
    return {
        "model": tag,
        "OVERALL": 100 * r["all"]["OVERALL"],
        "digital": 100 * r["scanned=no"]["OVERALL"],
        "scanned": 100 * r["scanned=yes"]["OVERALL"],
        "row F1": 100 * r["all"]["row_f1"],
        "exact": 100 * r["all"]["documents_fully_correct"],
        "false fill": f"{round(r['all']['false_fill_rate'] * r['all']['illegible_fields'])}/{r['all']['illegible_fields']}",
        "doc_type": f"{sum(score.score_doc(pred.get(d), g)['type_ok'] for d, g in gold.items())}/{len(gold)}",
        "waybill": 100 * r["waybill=yes"]["OVERALL"],
        "PN exact dig/scan": f"{pn('scanned=no'):.1f}/{pn('scanned=yes'):.1f}",
        "unparsed": len(gold) - len(pred),
        "s/doc p50": statistics.median(secs),
        "p95": secs[int(0.95 * (len(secs) - 1))],
        "peak GB": max(peaks) if peaks else None,
    }


def main():
    gold = gold_set("bakeoff")
    rows = [row(t, gold) for t in sys.argv[1:]]
    cols = list(rows[0])
    print("| " + " | ".join(cols) + " |\n|" + "---|" * len(cols))
    for r in rows:
        print("| " + " | ".join(f"{v:.1f}" if isinstance(v, float) else str(v) for v in r.values()) + " |")


if __name__ == "__main__":
    main()
