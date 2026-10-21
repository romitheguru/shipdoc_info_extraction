"""Needs-review flags: values that are readable but uncertain (PLAN.md principle 3).

A flag never changes a value. Flags are {target: reason}, where target is
  header.<field>         one header value
  row.<i>.<field>        one value of predicted row i
  rows                   every row of the document (e.g. an uncertain column mapping)
  doc                    the whole document (e.g. unparseable or truncated output)

Signals (all generic: no supplier names, prefixes or positions):
  ambiguous_day_month    slash date with day and month both <= 12 (postprocess)
  column roles           duplicate or missing roles, cells under unknown headers (extract)
  not_in_ocr             an ID the extractor read is absent from an independent OCR reading of the pages
"""
import json, os, re

ID_HEADER = ["invoice_number", "awb_number", "mawb", "hawb"]
ID_ROW = ["supplier_part_number", "customer_part_number", "purchase_order"]


def _squash(s):
    return re.sub(r"\s+", "", str(s)).upper()  # the scorer ignores case and whitespace for IDs


def ocr_text(pages, cache_dir):
    """All OCR tokens of a document as one squashed string, or None if any page is missing from the cache.

    The cache holds <page stem>.json = {"texts": [...]} per page (bakeoff/ocr_run.py writes this format).
    """
    texts = []
    for p in pages:
        path = os.path.join(cache_dir, os.path.splitext(os.path.basename(p))[0] + ".json")
        if not os.path.exists(path):
            return None
        texts += json.load(open(path))["texts"]
    return _squash("".join(texts))


def not_in_ocr(doc, text, raw_date=None):
    """Flag IDs (and the invoice date as printed) that the OCR text doesn't contain verbatim.
    Short values (< 4 chars) are skipped."""
    if text is None:
        return {}
    flags = {}
    if raw_date and doc["header"].get("invoice_date") and _squash(raw_date) not in text:
        flags["header.invoice_date"] = "not_in_ocr"
    for k in ID_HEADER:
        v = doc["header"].get(k)
        if v and len(_squash(v)) >= 4 and _squash(v) not in text:
            flags[f"header.{k}"] = "not_in_ocr"
    for i, r in enumerate(doc["line_items"]):
        for k in ID_ROW:
            v = r.get(k)
            if v and len(_squash(v)) >= 4 and _squash(v) not in text:
                flags[f"row.{i}.{k}"] = "not_in_ocr"
    return flags
