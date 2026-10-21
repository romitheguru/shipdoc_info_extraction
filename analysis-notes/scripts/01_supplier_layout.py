"""Note 01: train/dev distribution by supplier (invoices) and carrier brand (waybills).

    uv run python analysis-notes/scripts/01_supplier_layout.py
"""
import glob, json, os, re
from collections import Counter, defaultdict

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
ROW = ["supplier_part_number", "customer_part_number", "purchase_order", "quantity"]


def load(split):
    return [json.load(open(f)) for f in sorted(glob.glob(f"{ROOT}/data/{split}/labels/*.json"))]


def shape(s):
    """Character-class shape of an identifier: A=letter, 9=digit, others kept. Runs collapsed."""
    if s is None:
        return "null"
    s = re.sub(r"[A-Za-z]", "A", re.sub(r"\d", "9", s))
    return re.sub(r"(.)\1+", lambda m: f"{m.group(1)}{{{len(m.group(0))}}}", s)


def group_key(d):
    h = d["header"]
    if d["doc_type"] == "invoice":
        return "INV", h["supplier_name"] or "<null supplier>"
    return "AWB", (h["carrier"] or "<null carrier>").split()[0]


def stats(docs):
    g = defaultdict(list)
    for d in docs:
        g[group_key(d)].append(d)
    out = {}
    for k, ds in g.items():
        rows = [r for d in ds for r in d["line_items"]]
        nulls = Counter(f for d in ds for f, v in d["header"].items() if v is None)
        out[k] = {
            "docs": len(ds),
            "multi_page": sum(len(d["pages"]) > 1 for d in ds),
            "max_pages": max(len(d["pages"]) for d in ds),
            "scanned_docs": sum(any(p.endswith(".jpg") for p in d["pages"]) for d in ds),
            "rows_mean": len(rows) / len(ds),
            "rows_max": max((len(d["line_items"]) for d in ds), default=0),
            "repeat_docs": sum(len({r["supplier_part_number"] for r in d["line_items"]}) < len(d["line_items"]) for d in ds),
            "has_cpn": sum(r["customer_part_number"] is not None for r in rows) / len(rows) if rows else None,
            "has_po": sum(r["purchase_order"] is not None for r in rows) / len(rows) if rows else None,
            "po_per_doc": Counter(len({r["purchase_order"] for r in d["line_items"]}) for d in ds),
            "spn_shapes": Counter(shape(r["supplier_part_number"]) for r in rows).most_common(3),
            "inv_shapes": Counter(shape(d["header"].get("invoice_number") or d["header"].get("mawb")) for d in ds).most_common(2),
            "currencies": Counter(d["header"].get("currency") for d in ds).most_common(3),
            "header_nulls": dict(nulls),
            "row_nulls": Counter(f for r in rows for f in ROW if r[f] is None and f in ("supplier_part_number", "quantity")),
        }
    return out


def main():
    train, dev = load("train"), load("dev")
    st, sd = stats(train), stats(dev)
    print(f"train {len(train)} docs, dev {len(dev)} docs")
    for kind in ("INV", "AWB"):
        print(f"\n== {kind} ==")
        for k in sorted((k for k in st if k[0] == kind), key=lambda k: -st[k]["docs"]):
            s = st[k]
            print(f"{k[1]:<38} train={s['docs']:>3} dev={sd.get(k, {}).get('docs', 0):>2} "
                  f"multi={s['multi_page']:>2} maxp={s['max_pages']} scan={s['scanned_docs']:>2} "
                  f"rows={s['rows_mean']:5.1f}/{s['rows_max']:>2} rep={s['repeat_docs']:>2} "
                  f"cpn={s['has_cpn']} po={s['has_po']} po/doc={dict(s['po_per_doc'])}")
            print(f"{'':<38} spn={s['spn_shapes']} id={s['inv_shapes']} cur={s['currencies']} "
                  f"hnull={s['header_nulls']} rnull={dict(s['row_nulls'])}")
    only_dev = set(sd) - set(st)
    print("\ngroups in dev but not train:", only_dev or "none")


if __name__ == "__main__":
    main()
