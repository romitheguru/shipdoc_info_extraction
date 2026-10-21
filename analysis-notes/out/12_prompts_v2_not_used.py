"""Prompts. Generic by rule (PLAN.md): no supplier name, prefix or layout position. Header wordings
are given only as examples of a meaning, and the seller/buyer point of view is stated so unseen wordings
can be resolved the same way.
"""

CLASSIFY = """This is the first page of a shipping document. Is it an air waybill or an invoice?
An air waybill is titled "Air Waybill" and has shipper, consignee, airports, pieces and weight.
Anything with a table of items or parts (Invoice, Commercial Invoice, Tax Invoice, Packing List, ...) is an invoice.
Answer with one word: invoice or waybill."""

_COMMON_RULES = """Rules:
- Copy every value exactly as printed, character by character (keep hyphens, slashes, spaces inside IDs,
  letter O vs digit 0, letter I vs digit 1). Never correct, complete or reformat a value.
- Read each header value ONLY at its labelled position on the first page. Do not take it from anywhere else
  (e.g. a "continued" banner on a later page).
- If a label is absent, or its value is blacked out, scribbled over, smudged or cut off, output null,
  even if a few characters are still visible. A value with lines scribbled through it is NOT readable.
  Never guess, complete or invent a value; every value you output must be printed on the page.
Return ONLY the JSON object, compact on one line (no indentation), no prose, no markdown."""

INVOICE = """You are reading the page images of ONE invoice (all its pages, in order).

Return a JSON object with exactly these keys:
{"header": {
   "invoice_number": invoice number,
   "invoice_date_raw": invoice date exactly as printed,
   "supplier_name": the seller, from the letterhead,
   "buyer_name": the buyer (e.g. Sold To / Bill To / Buyer),
   "ship_to_name": the delivery party (e.g. Ship To / Deliver To / Consignee),
   "currency": currency code,
   "total_amount": the invoice total amount (money, not the total quantity),
   "awb_number": the air waybill / AWB number referenced on the invoice},
 "po_for_all_rows": a purchase order number printed ONCE outside the table that applies to the whole invoice, else null,
 "columns": [{"header": printed column header text, "role": role}, ... one entry per table column, left to right],
 "rows": [{"supplier_part_number": ..., "customer_part_number": ..., "purchase_order": ..., "quantity": ...}, ...]}

Column roles. Decide by meaning, from the SELLER's point of view (the seller issued this invoice):
  "supplier_part_number": the seller's own part / item / product number
      (e.g. "Our Part No.", "Mfr Part #", "Item Code", "Product", or a plain "Part No." when another column
      holds the buyer's part number).
  "customer_part_number": the buyer's part number (e.g. "Your Part No.", "Customer P/N", "Cust. Part").
  "purchase_order": the buyer's order number (e.g. "PO No.", "Customer PO", "Your Order"), even if its values
      look like part numbers.
  "quantity": quantity shipped.
  "other": everything else (line number, description, origin, prices, amounts).
  Words like "Your" and "Customer" mean the BUYER. "Our" and an unqualified part column mean the SELLER.
  Each of the four roles is used by at most one column.

rows: every row of the item table on ALL pages, in order, including rows that repeat a part number.
  Each row has exactly the four keys above. Fill each key from the column you gave that role in "columns",
  and use null when no column has that role. Never put a value from an "other" column into a row.
  Pages after the first may continue the table without repeating the header row: keep the same columns.
  Do not include total or subtotal lines.

""" + _COMMON_RULES

WAYBILL = """You are reading the page images of ONE air waybill (all its pages, in order).

Return a JSON object with exactly these keys:
{"header": {
   "carrier": the carrier company named in the title,
   "mawb": master air waybill number,
   "hawb": house air waybill number,
   "origin_airport": airport of departure, 3-letter IATA code only,
   "destination_airport": airport of destination, 3-letter IATA code only,
   "shipper_name": shipper,
   "consignee_name": consignee,
   "pieces": number of pieces,
   "gross_weight_kg": gross weight in kilograms}}

""" + _COMMON_RULES
