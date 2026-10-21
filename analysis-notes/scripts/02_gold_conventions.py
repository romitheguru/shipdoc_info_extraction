"""Note 02: value formats in the gold labels (train + dev), field by field.

    uv run python analysis-notes/scripts/02_gold_conventions.py
"""
import glob, json, os, re
from collections import Counter

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def load():
    return [json.load(open(f)) for s in ("train", "dev")
            for f in sorted(glob.glob(f"{ROOT}/data/{s}/labels/*.json"))]


def shape(s):
    if s is None:
        return "null"
    s = re.sub(r"[A-Z]", "A", re.sub(r"[a-z]", "a", re.sub(r"\d", "9", s)))
    return re.sub(r"(.)\1+", lambda m: f"{m.group(1)}{{{len(m.group(0))}}}", s)


def main():
    docs = load()
    inv = [d for d in docs if d["doc_type"] == "invoice"]
    awb = [d for d in docs if d["doc_type"] == "waybill"]
    print(f"{len(inv)} invoices, {len(awb)} waybills (train+dev)\n")

    for kind, ds in (("invoice", inv), ("waybill", awb)):
        for f in ds[0]["header"]:
            vals = [d["header"][f] for d in ds]
            if f.endswith("_name") or f == "carrier":
                ends = Counter(re.sub(r"^.*?\b(?=(Co\.|Ltd|Inc|LLC|GmbH|B\.V\.|S\.r\.l\.|S\.A\.|Pte|Sdn|Corp|Limited|$))", "", v or "null") for v in vals)
                print(f"{kind}.{f:<20} distinct={len(set(vals))} nulls={vals.count(None)} suffixes={ends.most_common(8)}")
                print(f"{'':<29} punctuation/odd chars: {Counter(c for v in vals if v for c in v if not c.isalnum() and c != ' ').most_common()}")
            else:
                print(f"{kind}.{f:<20} distinct={len(set(vals))} nulls={vals.count(None)} shapes={Counter(map(shape, vals)).most_common(6)}")
        print()

    # numbers: decimals and separators
    tot = [d["header"]["total_amount"] for d in inv if d["header"]["total_amount"]]
    print("total_amount decimals:", Counter(len(t.split(".")[1]) if "." in t else 0 for t in tot),
          " has comma:", sum("," in t for t in tot))
    print("total_amount by currency, decimals:", Counter((d["header"]["currency"], len((d["header"]["total_amount"] or ".").split(".")[-1])) for d in inv).most_common())
    q = [r["quantity"] for d in inv for r in d["line_items"]]
    print("quantity shapes:", Counter(map(shape, q)).most_common(5), " non-integer:", sum("." in x for x in q if x))
    print("quantity values (top):", Counter(q).most_common(10))
    print("gross_weight shapes:", Counter(shape(d["header"]["gross_weight_kg"]) for d in awb).most_common())
    print("pieces shapes:", Counter(shape(d["header"]["pieces"]) for d in awb).most_common())

    # relationships between fields
    same_bs = sum(d["header"]["buyer_name"] == d["header"]["ship_to_name"] for d in inv)
    print(f"\nbuyer == ship_to: {same_bs}/{len(inv)}")
    for d in inv:
        if d["header"]["buyer_name"] != d["header"]["ship_to_name"]:
            print("   differs:", d["doc_id"], d["header"]["buyer_name"], "|", d["header"]["ship_to_name"]); break
    print("buyer names:", Counter(d["header"]["buyer_name"] for d in inv).most_common(12))
    print("consignee names (top):", Counter(d["header"]["consignee_name"] for d in awb).most_common(5), "distinct", len({d['header']['consignee_name'] for d in awb}))
    print("carrier word2:", Counter(" ".join(d["header"]["carrier"].split()[1:]) for d in awb))
    print("supplier pool vs shipper pool overlap:",
          {d["header"]["supplier_name"] for d in inv} & {d["header"]["shipper_name"] for d in awb})
    print("buyer pool vs consignee pool overlap:",
          len({d["header"]["buyer_name"] for d in inv} & {d["header"]["consignee_name"] for d in awb}))
    print("airports:", Counter(d["header"][k] for d in awb for k in ("origin_airport", "destination_airport")).most_common())
    print("origin == destination:", sum(d["header"]["origin_airport"] == d["header"]["destination_airport"] for d in awb))
    dates = sorted(d["header"]["invoice_date"] for d in inv if d["header"]["invoice_date"])
    print("date range:", dates[0], dates[-1], " days<=12:", sum(int(x[8:]) <= 12 for x in dates), "/", len(dates))

    # cross-document links: does an invoice's awb_number match any waybill's mawb?
    mawbs = {d["header"]["mawb"] for d in awb}
    awbn = [d["header"]["awb_number"] for d in inv if d["header"]["awb_number"]]
    print(f"\ninvoice awb_number that equals some waybill mawb: {sum(a in mawbs for a in awbn)}/{len(awbn)}")
    ids = Counter(d["header"]["invoice_number"] for d in inv if d["header"]["invoice_number"])
    print("duplicate invoice numbers:", [k for k, v in ids.items() if v > 1])
    print("duplicate mawb:", [k for k, v in Counter(d["header"]["mawb"] for d in awb).items() if v > 1])
    spn = Counter(r["supplier_part_number"] for d in inv for r in d["line_items"])
    print("supplier part numbers: rows", sum(spn.values()), "distinct", len(spn),
          " ambiguous glyphs O/0/I/1/l/S/5/B/8/Z/2 present in",
          sum(bool(re.search(r"[O0I1l5S8BZ2]", k)) for k in spn), "distinct parts")
    print("letter O in part numbers:", sum("O" in re.sub(r"^[A-Z]+", "", k) for k in spn),
          " letter I:", sum("I" in re.sub(r"^[A-Z]+", "", k) for k in spn))
    print("whitespace inside any value:", sum(bool(re.search(r"\s", v)) for d in inv for r in d["line_items"] for v in r.values() if v))


if __name__ == "__main__":
    main()
