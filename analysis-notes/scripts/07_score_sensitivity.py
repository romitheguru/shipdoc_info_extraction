"""Note 07: how much each kind of error costs under the official scorer.

Takes the gold labels (train+dev, 500 docs), applies one simulated failure mode at a time, and
scores the result with score.py's own functions. Also writes slice meta files for
`score.py --meta` to analysis-notes/out/meta_{train,dev}.json.

    uv run python analysis-notes/scripts/07_score_sensitivity.py
"""
import copy, glob, importlib, json, os, random, sys

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(__file__))
import score  # noqa: E402  official scorer
awb_lines = importlib.import_module("05_awb_line_presence")

LOOK = {"O": "0", "0": "O", "I": "1", "1": "I", "S": "5", "5": "S", "B": "8", "8": "B", "Z": "2", "2": "Z"}


def load(split):
    return {d["doc_id"]: d for d in (json.load(open(f)) for f in sorted(glob.glob(f"{ROOT}/data/{split}/labels/*.json")))}


def run(gold, pred):
    return score.aggregate([score.score_doc(pred.get(k), g) for k, g in gold.items()])


def flip_char(s, rng):
    """Swap one look-alike character in the part-number body (after the prefix), if any."""
    idx = [i for i, c in enumerate(s) if c in LOOK and i >= 2]
    if not idx:
        return s[:-1] + ("X" if s[-1] != "X" else "Y")
    i = rng.choice(idx)
    return s[:i] + LOOK[s[i]] + s[i + 1:]


def swap_dm(iso):
    y, m, d = iso.split("-")
    return f"{y}-{d}-{m}" if int(d) <= 12 else iso


def scenarios(gold, rng):
    def each(fn):
        p = copy.deepcopy(gold)
        for d in p.values():
            fn(d)
        return p

    inv = lambda d: d["doc_type"] == "invoice"
    out = {}
    out["perfect"] = copy.deepcopy(gold)
    out["right doc_type only (all null, no rows)"] = each(lambda d: (d["header"].update({k: None for k in d["header"]}), d.__setitem__("line_items", [])))
    out["perfect header, no rows"] = each(lambda d: d.__setitem__("line_items", []))
    out["perfect rows, header all null"] = each(lambda d: d["header"].update({k: None for k in d["header"]}))
    out["date read as MM/DD vs DD/MM swapped (when day<=12)"] = each(lambda d: inv(d) and d["header"]["invoice_date"] and d["header"].__setitem__("invoice_date", swap_dm(d["header"]["invoice_date"])))
    out["ambiguous dates -> null (abstain)"] = each(lambda d: inv(d) and d["header"]["invoice_date"] and int(d["header"]["invoice_date"][8:]) <= 12 and d["header"].__setitem__("invoice_date", None))

    def one_char_one_row(d):
        if d["line_items"]:
            r = rng.choice(d["line_items"]); r["supplier_part_number"] = flip_char(r["supplier_part_number"], rng)
    out["1 look-alike char error in 1 row per invoice"] = each(one_char_one_row)

    def char_5pct(d):
        for r in d["line_items"]:
            if rng.random() < 0.05:
                r["supplier_part_number"] = flip_char(r["supplier_part_number"], rng)
    out["look-alike char error in 5% of rows"] = each(char_5pct)

    def dedupe(d):
        seen, keep = set(), []
        for r in d["line_items"]:
            if r["supplier_part_number"] not in seen:
                seen.add(r["supplier_part_number"]); keep.append(r)
        d["line_items"] = keep
    out["repeated part numbers de-duplicated"] = each(dedupe)
    out["page 2+ rows dropped (approx: rows after #14 of multi-page docs)"] = each(lambda d: len(d["pages"]) > 1 and d.__setitem__("line_items", d["line_items"][:14]))
    out["quantity read with thousands sep as decimal ('5,000'->5.000)"] = each(lambda d: [r.__setitem__("quantity", str(int(r["quantity"]) / 1000)) for r in d["line_items"] if len(r["quantity"]) == 4 and rng.random() < 0.1])

    def false_fill(d):
        for k, v in d["header"].items():
            if v is None:
                d["header"][k] = "GUESS123"
    out["every null header field guessed (false fill)"] = each(false_fill)
    out["PO hallucinated where no PO column (header-level copy)"] = each(lambda d: inv(d) and d["line_items"] and d["line_items"][0]["purchase_order"] is None and [r.__setitem__("purchase_order", "PO4500000000") for r in d["line_items"]])
    out["customer_part_number <-> purchase_order columns swapped (docs with both)"] = each(lambda d: [r.update(customer_part_number=r["purchase_order"], purchase_order=r["customer_part_number"]) for r in d["line_items"] if r["purchase_order"] and r["customer_part_number"]])
    out["ship_to copied from buyer (Sold To)"] = each(lambda d: inv(d) and d["header"].__setitem__("ship_to_name", d["header"]["buyer_name"]))
    out["airport as 'AMS AMSTERDAM' instead of 'AMS'"] = each(lambda d: d["doc_type"] == "waybill" and d["header"].update(origin_airport=d["header"]["origin_airport"] + " CITY", destination_airport=d["header"]["destination_airport"] + " CITY"))
    return out


def meta(split, docs):
    rows = []
    for d in docs.values():
        h, li = d["header"], d["line_items"]
        ill = d["doc_type"] == "invoice" and (h["invoice_number"] is None or h["invoice_date"] is None or
              (h["awb_number"] is None and awb_lines.header_lines(f"{ROOT}/data/{split}/images/{d['pages'][0]}") == 4))
        rows.append({"doc_id": d["doc_id"], "scanned": d["pages"][0].endswith(".jpg"), "multi_page": len(d["pages"]) > 1,
                     "repeated_parts": len({r["supplier_part_number"] for r in li}) < len(li), "illegible": bool(ill),
                     "waybill": d["doc_type"] == "waybill"})
    return rows


def main():
    rng = random.Random(0)
    gold = {**load("train"), **load("dev")}
    base = None
    print(f"{'scenario':<74}{'OVERALL':>8}{'Δ':>7}{'hdr':>7}{'rowF1':>7}{'exact':>7}{'ffill':>7}")
    for name, pred in scenarios(gold, rng).items():
        a = run(gold, pred)
        base = base or a["OVERALL"]
        print(f"{name:<74}{100 * a['OVERALL']:8.2f}{100 * (a['OVERALL'] - base):7.2f}{100 * a['header_field_accuracy']:7.2f}"
              f"{100 * a['row_f1']:7.2f}{100 * a['documents_fully_correct']:7.2f}{100 * a['false_fill_rate']:7.1f}")

    os.makedirs(f"{ROOT}/analysis-notes/out", exist_ok=True)
    for split in ("train", "dev"):
        m = meta(split, load(split))
        json.dump(m, open(f"{ROOT}/analysis-notes/out/meta_{split}.json", "w"), indent=0)
        print(f"\nmeta_{split}.json:", {t: sum(r[t] for r in m) for t in ("scanned", "multi_page", "repeated_parts", "illegible", "waybill")}, "of", len(m))


if __name__ == "__main__":
    main()
