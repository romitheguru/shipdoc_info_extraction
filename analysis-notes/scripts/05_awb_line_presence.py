"""Note 05: for invoices with a null awb_number, is the `AWB / Waybill:` line printed (value
illegible) or absent? The header block has 3 or 4 fixed-pitch lines (Invoice No., Date,
[AWB / Waybill], Currency), so a 4th line of ink means the AWB line is present.

    uv run python analysis-notes/scripts/05_awb_line_presence.py
"""
import glob, json, os
from collections import Counter

import cv2
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def header_lines(path):
    """Count text lines in the invoice header block (the half of the page holding `Invoice No.`)."""
    g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    ink = (g < 110).astype(np.uint8)
    band = ink[200:370]                                   # header block sits between title and Sold To
    half = 0 if band[:, :620].sum() > band[:, 620:].sum() else 1
    cols = band[:, :620] if half == 0 else band[:, 620:]
    rows = cols.sum(1) > 6
    # count runs of inked rows taller than 8 px (text lines), ignoring thin specks
    n, run = 0, 0
    for r in list(rows) + [False]:
        if r:
            run += 1
        else:
            n += run >= 8
            run = 0
    return n


def main():
    res = Counter()
    for s in ("train", "dev"):
        for f in sorted(glob.glob(f"{ROOT}/data/{s}/labels/*.json")):
            d = json.load(open(f))
            if d["doc_type"] != "invoice":
                continue
            n = header_lines(f"{ROOT}/data/{s}/images/{d['pages'][0]}")
            awb = "awb_null" if d["header"]["awb_number"] is None else "awb_set"
            res[awb, n] += 1
    for k in sorted(res):
        print(k, res[k])


if __name__ == "__main__":
    main()
