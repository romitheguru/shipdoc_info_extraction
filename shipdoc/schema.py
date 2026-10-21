"""Check a submission against schema.json with the standard library only (like score.py).

Covers what schema.json uses: required keys, no extra keys, string-or-null values, the doc_type enum,
the invoice-or-waybill header shape matching doc_type, and the ISO date pattern.
"""
import json, re
from pathlib import Path

from shipdoc.pages import ROOT

SCHEMA = json.loads(Path(ROOT, "schema.json").read_text())["$defs"]


def _keys(name):
    return set(SCHEMA[name]["required"])


def errors(sub):
    """List of problems in a {doc_id: doc} submission; empty means valid."""
    out = []
    if not isinstance(sub, dict):
        return ["submission is not an object"]
    for d, doc in sub.items():
        if not isinstance(doc, dict) or set(doc) != {"doc_type", "header", "line_items"}:
            out.append(f"{d}: keys must be doc_type, header, line_items")
            continue
        if doc["doc_type"] not in ("invoice", "waybill"):
            out.append(f"{d}: bad doc_type {doc['doc_type']!r}")
            continue
        want = _keys(f"{doc['doc_type']}_header")
        h = doc["header"]
        if not isinstance(h, dict) or set(h) != want:
            out.append(f"{d}: header keys {sorted(h) if isinstance(h, dict) else h} != {sorted(want)}")
            continue
        out += [f"{d}: header.{k} is not string/null" for k, v in h.items() if not (v is None or isinstance(v, str))]
        date = h.get("invoice_date")
        if isinstance(date, str) and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", date):
            out.append(f"{d}: invoice_date {date!r} is not ISO")
        rows = doc["line_items"]
        if not isinstance(rows, list):
            out.append(f"{d}: line_items is not a list")
            continue
        for i, r in enumerate(rows):
            if not isinstance(r, dict) or set(r) != _keys("line_item"):
                out.append(f"{d}: line_items[{i}] has wrong keys")
            else:
                out += [f"{d}: line_items[{i}].{k} is not string/null" for k, v in r.items() if not (v is None or isinstance(v, str))]
    return out
