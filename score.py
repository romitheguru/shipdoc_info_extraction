#!/usr/bin/env python3
"""Official scorer for the Document Extraction challenge.

    python3 score.py --gold data/dev/labels --pred my_dev_predictions.json

`--pred` is ONE JSON file: {"<doc_id>": {"doc_type": ..., "header": {...}, "line_items": [...]}, ...}
(see sample_submission.json). A document missing from the file scores zero on every field.
Standard library only.

What is scored
  header       every header field of the document's type, including fields whose true value
               is null (the value is not legible on the page). For those, the correct answer
               is null; any other value is a FALSE FILL and counts as wrong.
  line_items   rows are matched order-independently and one-to-one (a part number that appears
               twice must be predicted twice). A row is correct only if all four fields match.
               Row precision, recall and F1 are reported.
  document     fully correct = right doc_type, every header field right, and exactly the right
               set of rows (no missing, no extra).

  OVERALL = 0.4 * header field accuracy + 0.4 * line-item row F1 + 0.2 * documents fully correct
            (waybills have no line items; their line-item part is scored on the header alone)

Normalisation - deliberately small:
  names          case, spacing and punctuation ignored ("ACME Co., Ltd" == "acme co ltd")
  identifiers    case and spaces ignored, other characters kept ("AB-12" != "AB12")
  numbers        numeric comparison, thousands separators ignored ("1,000.00" == "1000")
  dates          must be ISO YYYY-MM-DD
  codes          currency / airport codes: case ignored
"""
import argparse, glob, json, os, re, sys
from collections import defaultdict

HEADER = {
    "invoice": ["invoice_number", "invoice_date", "supplier_name", "buyer_name", "ship_to_name",
                "currency", "total_amount", "awb_number"],
    "waybill": ["carrier", "mawb", "hawb", "origin_airport", "destination_airport", "shipper_name",
                "consignee_name", "pieces", "gross_weight_kg"],
}
ROW = ["supplier_part_number", "customer_part_number", "purchase_order", "quantity"]
KIND = {"supplier_name": "name", "buyer_name": "name", "ship_to_name": "name", "carrier": "name",
        "shipper_name": "name", "consignee_name": "name",
        "total_amount": "num", "quantity": "num", "pieces": "num", "gross_weight_kg": "num",
        "invoice_date": "date", "currency": "code", "origin_airport": "code", "destination_airport": "code"}


def _empty(v):
    return v is None or (isinstance(v, str) and not v.strip())


def _num(v):
    try:
        return float(re.sub(r"[,\s]", "", str(v)))
    except ValueError:
        return None


def same(field, pred, gold):
    """True if `pred` is an acceptable answer for `gold` in this field."""
    if _empty(gold):
        return _empty(pred)
    if _empty(pred):
        return False
    kind = KIND.get(field, "id")
    p, g = str(pred).strip(), str(gold).strip()
    if kind == "name":
        return re.sub(r"[^0-9a-z]", "", p.lower()) == re.sub(r"[^0-9a-z]", "", g.lower())
    if kind == "num":
        a, b = _num(p), _num(g)
        return a is not None and b is not None and abs(a - b) < 0.005
    if kind == "date":
        return re.fullmatch(r"\d{4}-\d{2}-\d{2}", p) is not None and p == g
    if kind == "code":
        return p.upper() == g.upper()
    return re.sub(r"\s", "", p).upper() == re.sub(r"\s", "", g).upper()


def row_ok(p, g):
    return all(same(k, p.get(k), g.get(k)) for k in ROW)


def match_rows(pred, gold):
    """One-to-one, order-independent. Returns the number of fully correct rows and, per field,
    the number of matched pairs agreeing on that field. Pass 1 pairs identical rows; pass 2
    pairs the rest by part number so field-level credit is still given."""
    free_p, free_g = list(range(len(pred))), list(range(len(gold)))
    full, pairs = 0, []
    for gi in list(free_g):
        for pi in free_p:
            if row_ok(pred[pi], gold[gi]):
                free_p.remove(pi); free_g.remove(gi); pairs.append((pi, gi)); full += 1
                break
    for gi in list(free_g):
        for pi in free_p:
            if same("supplier_part_number", pred[pi].get("supplier_part_number"), gold[gi].get("supplier_part_number")):
                free_p.remove(pi); free_g.remove(gi); pairs.append((pi, gi))
                break
    fields = {k: sum(same(k, pred[pi].get(k), gold[gi].get(k)) for pi, gi in pairs) for k in ROW}
    return full, fields


def score_doc(pred, gold):
    pred = pred if isinstance(pred, dict) else {}
    ph = pred.get("header") if isinstance(pred.get("header"), dict) else {}
    pr = [r for r in (pred.get("line_items") or []) if isinstance(r, dict)]
    fields = HEADER[gold["doc_type"]]
    right = {k: same(k, ph.get(k), gold["header"].get(k)) for k in fields}
    null_fields = [k for k in fields if _empty(gold["header"].get(k))]
    false_fill = sum(1 for k in null_fields if not _empty(ph.get(k)))
    gr = gold["line_items"]
    full, row_fields = match_rows(pr, gr)
    exact = (pred.get("doc_type") == gold["doc_type"] and all(right.values())
             and full == len(gr) == len(pr))
    return {"type_ok": pred.get("doc_type") == gold["doc_type"], "header": right,
            "null_fields": len(null_fields), "false_fill": false_fill,
            "rows_gold": len(gr), "rows_pred": len(pr), "rows_full": full, "row_fields": row_fields,
            "exact": exact}


def aggregate(results):
    n = len(results)
    if not n:
        return {}
    h_right = sum(sum(r["header"].values()) for r in results)
    h_total = sum(len(r["header"]) for r in results)
    per_field = defaultdict(lambda: [0, 0])
    for r in results:
        for k, ok in r["header"].items():
            per_field[k][0] += ok; per_field[k][1] += 1
    rg = sum(r["rows_gold"] for r in results); rp = sum(r["rows_pred"] for r in results)
    rf = sum(r["rows_full"] for r in results)
    prec = rf / rp if rp else (1.0 if not rg else 0.0)
    rec = rf / rg if rg else 1.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    nulls = sum(r["null_fields"] for r in results)
    ff = sum(r["false_fill"] for r in results)
    header_acc = h_right / h_total
    exact = sum(r["exact"] for r in results) / n
    items_part = f1 if rg else header_acc
    overall = 0.4 * header_acc + 0.4 * items_part + 0.2 * exact
    out = {"documents": n, "doc_type_accuracy": sum(r["type_ok"] for r in results) / n,
           "header_field_accuracy": header_acc,
           "header_by_field": {k: v[0] / v[1] for k, v in sorted(per_field.items())},
           "line_item_rows": rg, "row_precision": prec, "row_recall": rec, "row_f1": f1,
           "line_item_field_accuracy": {k: sum(r["row_fields"][k] for r in results) / rg for k in ROW} if rg else {},
           "illegible_fields": nulls, "false_fill_rate": ff / nulls if nulls else 0.0,
           "documents_fully_correct": exact, "OVERALL": overall}
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--gold", required=True, help="folder of gold label JSON files")
    ap.add_argument("--pred", required=True, help="submission JSON file")
    ap.add_argument("--meta", help="optional: JSON list of {doc_id, <tag>: bool} to report slices")
    ap.add_argument("--out", help="optional: write the full report here as JSON")
    a = ap.parse_args()
    gold = {}
    for f in sorted(glob.glob(os.path.join(a.gold, "*.json"))):
        g = json.load(open(f)); gold[g["doc_id"]] = g
    if not gold:
        sys.exit(f"no gold labels found in {a.gold}")
    pred = json.load(open(a.pred))
    if not isinstance(pred, dict):
        sys.exit("submission must be a JSON object keyed by doc_id")
    unknown = set(pred) - set(gold)
    per = {d: score_doc(pred.get(d), g) for d, g in gold.items()}
    report = {"all": aggregate(list(per.values())),
              "invoices": aggregate([per[d] for d, g in gold.items() if g["doc_type"] == "invoice"]),
              "waybills": aggregate([per[d] for d, g in gold.items() if g["doc_type"] == "waybill"])}
    if a.meta:
        meta = {m["doc_id"]: m for m in json.load(open(a.meta)) if m["doc_id"] in gold}
        tags = sorted({k for m in meta.values() for k, v in m.items() if isinstance(v, bool)})
        for t in tags:
            report[f"{t}=yes"] = aggregate([per[d] for d, m in meta.items() if m.get(t)])
            report[f"{t}=no"] = aggregate([per[d] for d, m in meta.items() if not m.get(t)])
    missing = sum(1 for d in gold if d not in pred)
    A = report["all"]
    print(f"documents scored        {A['documents']}   (missing from submission: {missing}, "
          f"unknown ids ignored: {len(unknown)})")
    print(f"doc_type accuracy       {100 * A['doc_type_accuracy']:6.2f}%")
    print(f"header field accuracy   {100 * A['header_field_accuracy']:6.2f}%")
    print(f"line-item rows          P {100 * A['row_precision']:6.2f}%   R {100 * A['row_recall']:6.2f}%   "
          f"F1 {100 * A['row_f1']:6.2f}%   ({A['line_item_rows']} rows)")
    print(f"false fills             {100 * A['false_fill_rate']:6.2f}% of {A['illegible_fields']} illegible fields")
    print(f"documents fully correct {100 * A['documents_fully_correct']:6.2f}%")
    print(f"OVERALL                 {100 * A['OVERALL']:6.2f}")
    for k, v in report.items():
        if k != "all" and v:
            print(f"   {k:<24} overall {100 * v['OVERALL']:6.2f}   header {100 * v['header_field_accuracy']:6.2f}%"
                  f"   row F1 {100 * v['row_f1']:6.2f}%   fully correct {100 * v['documents_fully_correct']:6.2f}%"
                  f"   (n={v['documents']})")
    if a.out:
        json.dump(report, open(a.out, "w"), indent=1)


if __name__ == "__main__":
    main()
