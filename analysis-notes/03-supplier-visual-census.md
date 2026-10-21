# 03: Visual census of all 18 invoice suppliers

Method: for every supplier I viewed page 1 of one multi-page doc in full, the header band of 3 more docs, and the top of page 2 for 3 multi-page docs. That's 72 page-1s and 54 page-2s, all from train. Montages come from `analysis-notes/scripts/montage.py`.

## TL;DR
- **Every supplier's properties are fixed across its docs:**
  - date format
  - title
  - column set, order and header wording
  - whether page 2 repeats the table header
  - invoice-number prefix
  - part-number prefix

  Only the font changes (serif, sans or mono, per doc).
- **The header-block labels are identical for all 18 suppliers:** `Invoice No.:`, `Date:`, `AWB / Waybill:`, `Currency:`, `Sold To:`, `Ship To:`. Train has **zero variation** in header wording, so unseen test suppliers using `Inv #`, `Bill To` or `Consignee` will be the first time the model sees them. This is the biggest generalisation gap in the data.
- **Table column headers vary a lot and collide:**
  - `Your Part No.` is the *customer* part number.
  - `Our Part No.` is the *supplier* part number.
  - `Your Order` and `Customer PO` are the *PO*.
  - Kastitek has both `Customer P/N` and `Customer PO`.

  The model must understand these headers, not just pattern-match them.
- **Date formats split 7/5/4/2.** 7 suppliers use slash formats: 4 use MM/DD (Brenara, Kastitek, Kaston, Zerova) and 3 use DD/MM (Jovova, Talara, Vexaris). For an unseen slash-format supplier, a date with day ≤ 12 can't be resolved from that date alone.
- **A document titled "PACKING LIST" (5 suppliers) or "TAX INVOICE" (1) is still `doc_type: invoice`.** Don't classify from the title word.

## Per-supplier layout table
| Supplier | Title | Supplier / header side | Date format | Supplier PN header | Cust PN header | PO header | Qty header | Table rules | p2 repeats header |
|---|---|---|---|---|---|---|---|---|---|
| Brenara | COMMERCIAL INVOICE | R / L | MM/DD/YYYY | Mfr Part # | Cust. Part | PO No. | Units | grid | **yes** |
| Fenium | PACKING LIST | L / R | Month DD, YYYY | Mfr Part # | Customer P/N | P.O. Number (1st col) | Qty Shipped | header rule only | no |
| Galdek | TAX INVOICE | R / L | Month DD, YYYY | Part No. | Your Part No. | – | Quantity | grid | no |
| Galdon | INVOICE | L / R | DD-MON-YYYY | Mfr Part # | – | – | Quantity | grid | no |
| Heskeon | PACKING LIST | L / R | DD-MON-YYYY | Mfr Part # | – | PO No. (1st col) | Quantity | grid | no |
| Jovon | PACKING LIST | L / R | Month DD, YYYY | Part No. | – | PO No. (1st col) | Quantity | grid | **yes** |
| Jovova | INVOICE | R / L | DD/MM/YYYY | Item Code (3rd col) | Cust. Part | Your Order (1st col) | Units | header rule only | no |
| Kastara | INVOICE | L / R | DD-MON-YYYY | Our Part No. | – | – | Qty Shipped | header rule only | **yes** |
| Kastitek | INVOICE | R / L | MM/DD/YYYY | Item Code | Customer P/N | Customer PO | Qty Shipped | grid | **yes** |
| Kaston | COMMERCIAL INVOICE | R / L | MM/DD/YYYY | Part No. | Customer P/N | – | Qty | header rule only | no |
| Lumex | COMMERCIAL INVOICE | R / L | YYYY-MM-DD | Our Part No. (3rd col) | Your Part No. | Your Order (1st col) | Units | grid | **yes** |
| Talara | INVOICE | L / R | DD/MM/YYYY | Product | – | Customer PO | Quantity | grid | **yes** |
| Talitek | COMMERCIAL INVOICE | L / R | YYYY-MM-DD | Part No. | – | – | Qty Shipped | grid | no |
| Tambova | INVOICE | R / L | DD-MON-YYYY | Part No. | – | – | Quantity | grid | no |
| Vexaris | INVOICE | L / R | DD/MM/YYYY | Product | – | – | Units | header rule only | no |
| Vexenta | PACKING LIST | L / R | DD-MON-YYYY | Mfr Part # | – | – | Qty | grid | no |
| Vexova | COMMERCIAL INVOICE | L / R | Month DD, YYYY | Part No. | – | Customer PO | Qty Shipped | grid | no |
| Zerova | PACKING LIST | R / L | MM/DD/YYYY | Our Part No. | – | Your Order (4th col) | Quantity | grid | no |

"Supplier / header side" gives the letterhead side, then the side of the invoice header block (L = left, R = right).

Summary counts:
- **Date formats:** DD-MON-YYYY 5, MM/DD 4, Month DD YYYY 4, DD/MM 3, ISO 2.
- **Titles:** INVOICE 7, COMMERCIAL INVOICE 5, PACKING LIST 5, TAX INVOICE 1.
- **Page-2 header row:** 6 suppliers repeat it, 12 don't. Rows without a header must be mapped to columns using page 1's header. Grid-less tables (5 suppliers) make this harder.

## Other fixed structure (all suppliers)
- **Page 2+ banner:** `<TITLE> - continued   <invoice number>`, then table rows. **Totals (`Total Qty:` then `Total Amount: CUR 1,234.56`) appear only on the last page**, so total_amount needs the last page. `Total Qty` sits directly above `Total Amount` and is not wanted.
- **The AWB line comes and goes per document** within a supplier: it's printed in some docs and absent in others (see note 05).
- **Invoice numbers use a fixed 2-letter prefix per supplier** (PI, NB, ZT, ST, MZ, ME, TY, KH, LK, WW, QU, NK, GY, EW, GJ, CQ, OK, GF) followed by 8 digits.
- **Other columns present** (never extracted): Description, Country of Origin / COO / Origin, Price / U/P / Unit Price, Amount / Line Total / Ext. Price. `Origin` (country) must not be confused with the waybill sense of origin.

## Implications
1. **Column assignment must use header semantics.** "Our/Your" flips meaning depending on the speaker. Few-shot or fine-tuning data should stress the Lumex, Galdek, Kastitek and Zerova cases.
2. **Header-label augmentation is worth considering.** Because train has a single header vocabulary, a fine-tuned model may learn "the value after `Invoice No.:`". Synthetic relabelling (rendering train pages with alternate labels) is a lever, but it costs time.
3. **Date policy for unseen layouts:**
   - A month name, `DD-MON` or ISO date is unambiguous.
   - A slash date with a component above 12 settles the order.
   - Otherwise it's ambiguous; see note 07 for why we should guess plus flag, not null.
4. **Multi-page:** pass all pages together (one context) so page-2 rows inherit page-1 column semantics. Totals come from the last page.
