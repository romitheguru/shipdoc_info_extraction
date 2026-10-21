"""Deterministic normalisation from raw extracted values to the submission format (note 02).

The model copies values as printed; these rules only change *format* (dates to ISO, airports to bare
IATA codes, amounts to plain numbers), never the characters of an ID or a name. Every rule is generic:
none names a supplier, prefix or layout position (PLAN.md).

A slash date whose day and month are both <= 12 can't be resolved from the date alone (note 03). It
resolves to MM/DD and is returned as a review flag (note 07: a guess beats null).
"""
import re

INVOICE = ["invoice_number", "invoice_date", "supplier_name", "buyer_name", "ship_to_name", "currency",
           "total_amount", "awb_number"]
WAYBILL = ["carrier", "mawb", "hawb", "origin_airport", "destination_airport", "shipper_name",
           "consignee_name", "pieces", "gross_weight_kg"]
ROW = ["supplier_part_number", "customer_part_number", "purchase_order", "quantity"]
MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
NULLS = {"", "null", "none", "n/a", "na", "-", "–", "—"}
CURRENCY_SYMBOLS = {"€": "EUR", "£": "GBP"}  # "$" and "¥" are ambiguous (USD/SGD, JPY/CNY): left null


def clean(v):
    if v is None:
        return None
    v = str(v).strip()
    return None if v.lower() in NULLS else v


def number(v, integer=False):
    """First number in the string as a plain number: '1,234.50 USD' -> '1234.50'.

    For an integer field (quantity, pieces), dot groups of exactly 3 digits are thousands separators
    ('2.500' -> '2500'): a fractional count with 3 decimals is far less likely than a European number.

    A comma followed by exactly 1-2 final digits is a decimal comma ('125,5' -> '125.5', '1.234,50' ->
    '1234.50'); a comma followed by 3 digits is a thousands separator ('1,200' -> '1200').
    """
    v = clean(v)
    if v is None:
        return None
    if integer and (m := re.search(r"(?<![\d.,])\d{1,3}(?:\.\d{3})+(?![\d.,])", v)):
        return m.group(0).replace(".", "")
    if m := re.search(r"\d{1,3}(?:\.\d{3})+,\d{1,2}(?!\d)|\d+,\d{1,2}(?![\d,.])", v):
        return m.group(0).replace(".", "").replace(",", ".")
    m = re.search(r"\d[\d,]*(?:\.\d+)?", v)
    return m.group(0).replace(",", "") if m else None


def _ymd(y, mo, d):
    return f"{y:04d}-{mo:02d}-{d:02d}" if mo and 1 <= mo <= 12 and 1 <= d <= 31 else None


def iso_date(raw):
    """(ISO date or None, ambiguous flag)."""
    s = clean(raw)
    if s is None:
        return None, False
    s = re.sub(r"(\d)(st|nd|rd|th)\b", r"\1", s, flags=re.I)
    if m := re.fullmatch(r"(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})", s):
        y, mo, d = map(int, m.groups())
        return _ymd(y, mo, d), False
    if m := re.fullmatch(r"(\d{1,2})[-\s.]([A-Za-z]{3})[A-Za-z]*[-\s,.]+(\d{4})", s):
        return _ymd(int(m.group(3)), MONTHS.get(m.group(2).lower()), int(m.group(1))), False
    if m := re.fullmatch(r"([A-Za-z]{3})[A-Za-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s):
        return _ymd(int(m.group(3)), MONTHS.get(m.group(1).lower()), int(m.group(2))), False
    if m := re.fullmatch(r"(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})", s):
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if a > 12:
            return _ymd(y, b, a), False
        if b > 12:
            return _ymd(y, a, b), False
        return _ymd(y, a, b), a != b
    return None, False


def iata(v):
    """Bare IATA code: 'HKG HONG KONG', 'Los Angeles (LAX)', 'LONDON LHR' -> code; no code -> None.

    Known limit: with two 3-letter capital tokens and no brackets ('NEW YORK JFK') the first wins, as in
    the train template; telling them apart would need an airport list.
    """
    v = clean(v)
    if v is None:
        return None
    if re.fullmatch(r"[A-Za-z]{3}", v):
        return v.upper()
    if m := re.search(r"\(([A-Z]{3})\)", v):
        return m.group(1)
    tokens = v.split()
    for t in (tokens[0], tokens[-1]):
        if re.fullmatch(r"[A-Z]{3}", t):
            return t
    return None


def currency(v):
    v = clean(v)
    if v is None:
        return None
    if m := re.search(r"\b[A-Za-z]{3}\b", v):
        return m.group(0).upper()
    return next((code for sym, code in CURRENCY_SYMBOLS.items() if sym in v), None)


def normalise(out):
    """Raw model dict -> (submission doc with schema keys only, review flags {target: reason}; see shipdoc.flags)."""
    doc_type = "waybill" if str(out.get("doc_type", "")).lower().startswith("w") else "invoice"
    h = out.get("header") or {}
    flags = {}
    if doc_type == "invoice":
        date, ambiguous = iso_date(h.get("invoice_date_raw", h.get("invoice_date")))
        if ambiguous:
            flags["header.invoice_date"] = "ambiguous_day_month"
        header = {k: clean(h.get(k)) for k in INVOICE}
        header.update(invoice_date=date, total_amount=number(h.get("total_amount")),
                      currency=currency(h.get("currency")))
        rows = [{"supplier_part_number": clean(r.get("supplier_part_number")),
                 "customer_part_number": clean(r.get("customer_part_number")),
                 "purchase_order": clean(r.get("purchase_order")),
                 "quantity": number(r.get("quantity"), integer=True)}
                for r in out.get("line_items") or [] if isinstance(r, dict)]
    else:
        header = {k: clean(h.get(k)) for k in WAYBILL}
        header.update(origin_airport=iata(h.get("origin_airport")), destination_airport=iata(h.get("destination_airport")),
                      pieces=number(h.get("pieces"), integer=True), gross_weight_kg=number(h.get("gross_weight_kg")))
        rows = []
    return {"doc_type": doc_type, "header": header, "line_items": rows}, flags


def to_submission(out):
    return normalise(out)[0]
