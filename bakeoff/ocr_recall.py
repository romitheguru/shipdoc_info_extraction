"""How often does each gold value appear exactly among the cached OCR tokens? This is an upper bound
on any OCR-first pipeline: a value that OCR never produced can't be extracted. For misses, the
nearest token (by edit distance) and its OCR confidence are shown.

    uv run python -m bakeoff.ocr_recall --model server
"""
import argparse, json, os, re
from collections import Counter, defaultdict

from bakeoff.ocr_run import CACHE
from eval.data import page_paths, slices
from eval.evaluate import gold_set

ROW = ["supplier_part_number", "customer_part_number", "purchase_order", "quantity"]
HDR = ["invoice_number", "awb_number", "supplier_name", "buyer_name", "ship_to_name", "currency",
       "carrier", "mawb", "hawb", "shipper_name", "consignee_name", "pieces", "gross_weight_kg", "total_amount"]
NAMES = {"supplier_name", "buyer_name", "ship_to_name", "carrier", "shipper_name", "consignee_name"}


def norm(field, s):
    if field in NAMES:
        return re.sub(r"[^0-9a-z]", "", s.lower())
    if field in ("quantity", "pieces", "gross_weight_kg", "total_amount"):
        return re.sub(r"[,\s]", "", s).rstrip("0").rstrip(".") if "." in s else re.sub(r"[,\s]", "", s)
    return re.sub(r"\s", "", s).upper()


def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def tokens(doc_id, model):
    """(text, score) for every OCR line and every whitespace piece of it, plus 'CUR 1,234.56' tails."""
    out = []
    for p in page_paths(doc_id):
        c = json.load(open(os.path.join(CACHE, f"ocr_{model}", os.path.splitext(os.path.basename(p))[0] + ".json")))
        for t, s in zip(c["texts"], c["scores"]):
            out.append((t, s))
            out += [(w, s) for w in t.split()] if " " in t else []
            out += [(t.split(":", 1)[1].strip().split()[-1], s)] if ":" in t and t.split(":", 1)[1].strip() else []
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="server")
    a = ap.parse_args()
    gold = gold_set("bakeoff")
    found = defaultdict(lambda: [0, 0])          # (field, scanned) -> [found, total]
    rows_ok = defaultdict(lambda: [0, 0])
    docs_ok = defaultdict(lambda: [0, 0])
    misses, miss_conf, hit_conf = [], [], []
    for d, g in gold.items():
        sc = slices(g)["scanned"]
        toks = tokens(d, a.model)
        all_rows_ok = True
        for k in HDR:
            v = g["header"].get(k)
            if v is None:
                continue
            ok = any(norm(k, t) == norm(k, v) for t, _ in toks)
            found[k, sc][0] += ok; found[k, sc][1] += 1
        for r in g["line_items"]:
            row_ok = True
            for k in ROW:
                v = r[k]
                if v is None:
                    continue
                hits = [s for t, s in toks if norm(k, t) == norm(k, v)]
                found[k, sc][0] += bool(hits); found[k, sc][1] += 1
                if hits:
                    hit_conf.append(max(hits))
                else:
                    row_ok = False
                    near = min(toks, key=lambda ts: lev(norm(k, ts[0]), norm(k, v)))
                    misses.append((d, k, v, near[0], near[1]))
                    miss_conf.append(near[1])
            rows_ok[sc][0] += row_ok; rows_ok[sc][1] += 1
            all_rows_ok &= row_ok
        if g["line_items"]:
            docs_ok[sc][0] += all_rows_ok; docs_ok[sc][1] += 1

    print(f"OCR model PP-OCRv5_{a.model}: value found verbatim among tokens (digital | scanned)")
    for k in ROW + HDR:
        dg, sn = found[k, False], found[k, True]
        if dg[1] + sn[1]:
            f = lambda x: f"{100 * x[0] / x[1]:5.1f}% ({x[0]}/{x[1]})" if x[1] else "   n/a"
            print(f"  {k:<22} {f(dg):>18} | {f(sn):>18}")
    for name, c in (("rows with every field found", rows_ok), ("invoices with every row found", docs_ok)):
        print(f"  {name:<30} digital {100 * c[False][0] / c[False][1]:5.1f}%   scanned {100 * c[True][0] / c[True][1]:5.1f}%")
    print(f"\nmisses: {len(misses)}; by field {dict(Counter(m[1] for m in misses))}")
    for d, k, v, t, s in misses[:40]:
        print(f"  {d} {k:<21} gold {v!r:<20} nearest OCR {t!r:<24} conf {s:.3f}")
    if miss_conf and hit_conf:
        for thr in (0.90, 0.95, 0.98, 0.99):
            flagged_miss = sum(c < thr for c in miss_conf); flagged_hit = sum(c < thr for c in hit_conf)
            print(f"  flag if conf < {thr}: catches {flagged_miss}/{len(miss_conf)} misses, "
                  f"flags {flagged_hit}/{len(hit_conf)} correct values")


if __name__ == "__main__":
    main()
