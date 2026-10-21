"""Deterministic normalisation from raw extracted values to the submission format (note 02).

Dates are parsed from the printed string. A slash date whose day and month are both <= 12 is
ambiguous without supplier knowledge; it resolves to MM/DD and is reported as ambiguous so a
review flag can be raised (note 07: a guess beats null).
"""
import re

INVOICE = ["invoice_number", "invoice_date", "supplier_name", "buyer_name", "ship_to_name", "currency",
           "total_amount", "awb_number"]
WAYBILL = ["carrier", "mawb", "hawb", "origin_airport", "destination_airport", "shipper_name",
           "consignee_name", "pieces", "gross_weight_kg"]
ROW = ["supplier_part_number", "customer_part_number", "purchase_order", "quantity"]
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}


def clean(v):
    if v is None:
        return None
    v = str(v).strip()
    return None if not v or v.lower() in ("null", "none", "n/a") else v


def number(v):
    v = clean(v)
    if v is None:
        return None
    m = re.search(r"\d[\d,]*(?:\.\d+)?", v)
    return m.group(0).replace(",", "") if m else None


def iso_date(raw):
    """(ISO date or None, ambiguous flag)."""
    raw = clean(raw)
    if raw is None:
        return None, False
    s = raw.strip()
    if m := re.fullmatch(r"(\d{4})-(\d{1,2})-(\d{1,2})", s):
        y, mo, d = map(int, m.groups())
        return f"{y:04d}-{mo:02d}-{d:02d}", False
    if m := re.fullmatch(r"(\d{1,2})[-\s]([A-Za-z]{3})[A-Za-z]*[-\s,]+(\d{4})", s):
        d, mo, y = int(m.group(1)), MONTHS.get(m.group(2).lower()), int(m.group(3))
        return (f"{y:04d}-{mo:02d}-{d:02d}" if mo else None), False
    if m := re.fullmatch(r"([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s):
        mo, d, y = MONTHS.get(m.group(1).lower()), int(m.group(2)), int(m.group(3))
        return (f"{y:04d}-{mo:02d}-{d:02d}" if mo else None), False
    if m := re.fullmatch(r"(\d{1,2})[/.](\d{1,2})[/.](\d{4})", s):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12:
            return f"{y:04d}-{b:02d}-{a:02d}", False
        if b > 12:
            return f"{y:04d}-{a:02d}-{b:02d}", False
        return f"{y:04d}-{a:02d}-{b:02d}", a != b
    return None, False


def iata(v):
    v = clean(v)
    m = re.match(r"\s*([A-Za-z]{3})\b", v) if v else None
    return m.group(1).upper() if m else None


def to_submission(out):
    """Raw model dict -> {"doc_type", "header", "line_items"} with schema keys only."""
    doc_type = "waybill" if str(out.get("doc_type", "")).lower().startswith("w") else "invoice"
    h = out.get("header") or {}
    if doc_type == "invoice":
        date, _ = iso_date(h.get("invoice_date_raw", h.get("invoice_date")))
        header = {k: clean(h.get(k)) for k in INVOICE}
        header.update(invoice_date=date, total_amount=number(h.get("total_amount")),
                      currency=(clean(h.get("currency")) or "").upper()[:3] or None)
        rows = [{"supplier_part_number": clean(r.get("supplier_part_number")),
                 "customer_part_number": clean(r.get("customer_part_number")),
                 "purchase_order": clean(r.get("purchase_order")),
                 "quantity": number(r.get("quantity"))}
                for r in out.get("line_items") or [] if isinstance(r, dict)]
    else:
        header = {k: clean(h.get(k)) for k in WAYBILL}
        header.update(origin_airport=iata(h.get("origin_airport")), destination_airport=iata(h.get("destination_airport")),
                      pieces=number(h.get("pieces")), gross_weight_kg=number(h.get("gross_weight_kg")))
        rows = []
    return {"doc_type": doc_type, "header": header, "line_items": rows}
