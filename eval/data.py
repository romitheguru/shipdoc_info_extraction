"""Labelled documents, their layout group (supplier or carrier brand) and slice tags."""
import glob, json, os
from functools import lru_cache

import cv2
import numpy as np

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATA = os.path.join(ROOT, "data")
EVAL = os.path.join(ROOT, "eval")


def load_labels(split):
    """{doc_id: label} for a labelled split ('train' or 'dev')."""
    return {d["doc_id"]: d for d in (json.load(open(f)) for f in sorted(glob.glob(f"{DATA}/{split}/labels/*.json")))}


def all_labels():
    return {**load_labels("train"), **load_labels("dev")}


def page_paths(doc_id):
    split = doc_id.split("_")[0]
    return sorted(glob.glob(f"{DATA}/{split}/images/{doc_id}_p*.*"), key=lambda p: int(p.rsplit("_p", 1)[1].split(".")[0]))


def group(doc):
    """Layout group: invoice supplier, or carrier brand for waybills (one shared template; note 01)."""
    h = doc["header"]
    if doc["doc_type"] == "invoice":
        return "INV:" + h["supplier_name"]
    return "AWB:" + h["carrier"].split()[0]


@lru_cache(maxsize=None)
def header_lines(path):
    """Text lines in the invoice header block; 4 means the `AWB / Waybill:` line is printed (note 05)."""
    g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    band = (g[200:370] < 110).astype(np.uint8)
    cols = band[:, :620] if band[:, :620].sum() > band[:, 620:].sum() else band[:, 620:]
    n = run = 0
    for r in list(cols.sum(1) > 6) + [False]:
        if r:
            run += 1
        else:
            n += run >= 8
            run = 0
    return n


def slices(doc):
    """Boolean slice tags for score.py --meta (definitions in analysis-notes 05 and 07)."""
    h, rows = doc["header"], doc["line_items"]
    pages = page_paths(doc["doc_id"])
    illegible = doc["doc_type"] == "invoice" and (
        h["invoice_number"] is None or h["invoice_date"] is None
        or (h["awb_number"] is None and header_lines(pages[0]) == 4))
    return {
        "scanned": pages[0].endswith(".jpg"),
        "multi_page": len(pages) > 1,
        "repeated_parts": len({r["supplier_part_number"] for r in rows}) < len(rows),
        "illegible": bool(illegible),
        "waybill": doc["doc_type"] == "waybill",
    }
