# 01: Training data distribution by supplier and layout

Script: `analysis-notes/scripts/01_supplier_layout.py` (reads labels only). The visual observations come from viewing about 10 page images by hand: train_0000, 0001, 0006, 0009, 0012, 0022, 0040, 0072, 0111.

## TL;DR
- **Invoices come from 18 suppliers.** Each one has a fixed layout and a fixed part-number prefix. **Waybills all share one template** with shuffled boxes, so "supplier" for a waybill really means the carrier brand (10 brands). The ~20 suppliers in the brief = 18 invoice suppliers + the waybill template(s).
- **Dev holds no unseen suppliers.** Every dev group appears in train. Dev OVERALL will therefore overstate test performance, since about half of test is unseen. **We need leave-supplier-out evaluation** to estimate it.
- **Most nulls are "not printed", not "illegible".** The commonest null header field is `awb_number` (35% of invoices), and the AWB line is simply absent from the page in those cases. True illegibility (a black bar or scribble) hits `invoice_number`, `invoice_date` and some `awb_number` values (≥ 48 train+dev docs). *Corrected in note 05.* Row cells are never illegible.
- **Date formats differ by supplier, and DD/MM vs MM/DD is ambiguous.** On an unseen layout, a date like `03/04/2026` cannot be resolved from the page alone. This is a false-fill risk.

## Split sizes
| | docs | invoices / waybills | scanned docs | multi-page docs (p2 / p3 pages) |
|---|---|---|---|---|
| train | 400 | 323 / 77 | 150 (38%) | 124 (31%) / 12 |
| dev | 100 | 77 / 23 | 43 (43%) | 28 / 7 |
| test | 200 | ? | 90 (45%) | 68 (34%) / 12 |

- Scanning is **per document**: every doc is either all `.jpg` or all `.png`. So `scanned` is a clean slice tag taken from the file extension.
- All pages are 1240×1754 (A4 at 150 dpi). Digital pages are grayscale PNGs.
- Only invoices are multi-page. Waybills are always one page.

## Invoices: 18 suppliers
| Supplier | train | dev | multi-pg | scanned | rows mean/max | cust PN col | PO col | SPN style |
|---|---|---|---|---|---|---|---|---|
| Galdon Semiconductor S.r.l. | 29 | 3 | 12 | 11 | 12.4 / 30 | – | – | `NQL41408W3V` |
| Jovova Components Ltd | 25 | 3 | 13 | 14 | 12.4 / 30 | ✓ | ✓ | `UO/204/0XK7` |
| Vexova Sensors Inc | 21 | 2 | 8 | 8 | 12.8 / 30 | – | ✓ | `UMNY-645-4` |
| Jovon Power Systems Inc | 21 | 4 | 8 | 7 | 14.5 / 30 | – | ✓ | `US/123/A` |
| Heskeon Power Systems B.V. | 20 | 2 | 9 | 10 | 12.7 / 26 | – | ✓ | `IPLK123A` |
| Talara Power Systems Co., Ltd | 19 | 8 | 8 | 6 | 13.2 / 30 | – | ✓ | `ZO-12345-A` |
| Brenara Industrial Sdn Bhd | 19 | 4 | 9 | 9 | 12.8 / 27 | ✓ | ✓ | `GLT/7655/YQU9` |
| Talitek Power Systems Pte Ltd | 18 | 5 | 3 | 10 | 9.8 / 27 | – | – | `GHSR274209` |
| Kaston Circuits S.r.l. | 18 | 4 | 8 | 6 | 13.1 / 30 | ✓ | – | `NGTT-553-YJ` |
| Lumex Electro S.r.l. | 17 | 5 | 4 | 8 | 11.0 / 28 | ✓ | ✓ | `OVVX12345` |
| Kastitek Devices S.A. de C.V. | 17 | 7 | 4 | 6 | 13.5 / 30 | ✓ | ✓ | `JI-12345-AB` |
| Zerova Circuits Inc | 16 | 3 | 5 | 2 | 13.9 / 29 | – | ✓ | `EOEM-12345-AB` |
| Vexaris Circuits LLC | 15 | 7 | 6 | 4 | 10.3 / 26 | – | – | `LH-123-A` |
| Tambova Circuits S.A. de C.V. | 14 | 5 | 6 | 9 | 11.8 / 27 | – | – | `OWH12345ABC` |
| Galdek Components LLC | 14 | 5 | 4 | 6 | 9.2 / 24 | ✓ | – | `BQN-12345-ABC` |
| Kastara Devices GmbH | 14 | 2 | 5 | 4 | 14.0 / 30 | – | – | `CL-12345-A` |
| Vexenta Electro LLC | 14 | 4 | 8 | 3 | 13.6 / 28 | – | – | `PX/123/ABC` |
| Fenium Semiconductor Sdn Bhd | 12 | 4 | 4 | 5 | 10.9 / 27 | ✓ | ✓ | `RXY/12345/1` |

**Balance.** The suppliers are fairly balanced, with 12–29 docs each in train. In dev, Talara, Kastitek and Vexaris are over-represented and Vexova, Heskeon and Kastara have only 2 each, so per-supplier dev numbers are noisy.

**Column presence is fixed per supplier.** A supplier either prints a column on every row of every doc, or never prints it:
- **Customer part number:** 7 of 18 suppliers print it. Values look like `CP-123456` or `12-3456-78`, mixed within the same doc.
- **PO:** 10 of 18 suppliers print a per-row PO. Values look like `PO45xxxxxxxx` or `B12345678-00N`, also mixed within a doc.
- **Neither:** 6 suppliers print neither column: Galdon, Talitek, Vexaris, Tambova, Kastara and Vexenta.
- **Invoice-level PO:** there are zero cases in train or dev of one PO printed for the whole invoice, even though the schema description allows it. The test set's unseen suppliers might do this. If a PO appears only in the header, it should be copied onto every row.

**Part-number style is fixed per supplier.** Each supplier uses one prefix (100% consistent) and one separator (none, `-` or `/`), with a variable-length body. The bodies mix letters and digits and contain O/0 and I/1 lookalikes: `GHSR61902O6`, `UMNY-582-4I`, `NGTT-212-O`. **Character-level OCR confusion is the main row-level risk.** A wrong O/0 fails the whole row, and repeated part numbers multiply the damage.

**Repeated part numbers.** 65 of 323 train invoices (20%) repeat a part number across rows, with different quantities or POs. Matching is one-to-one, so a deduplicating extractor loses rows.

**Header label variation seen so far** (6 suppliers viewed):
- Title: `COMMERCIAL INVOICE` or `INVOICE`.
- Header block: placed top-left or top-right.
- Supplier block: placed top-left or top-right.
- Labels are fairly consistent: `Invoice No.:`, `Date:`, `AWB / Waybill:`, `Currency:`, `Sold To:`, `Ship To:`.
- Table headers vary a lot:
  - Supplier part number: `Part No.`, `Mfr Part #`, `Item Code`.
  - Customer part number: `Cust. Part`, `Customer P/N`.
  - PO: `Customer PO`, `PO No.`, `Your Order`.
  - Quantity: `Qty Shipped`, `Qty`, `Quantity`, `Units`.
- **Column order varies.** Jovova puts PO first and the supplier part number third.
- **Traps for unseen layouts:**
  - Vexova's `Customer PO` column is the purchase_order, not the customer part number.
  - `Total Qty:` sits right next to `Total Amount:`, and only the amount is wanted.

**Date formats observed** (all normalised to ISO in gold):
| Example | Format | Supplier |
|---|---|---|
| `2026-05-04` | ISO | Talitek |
| `September 02, 2026` | Month DD, YYYY | Vexova |
| `01/23/2026` | MM/DD | Brenara, Kaston |
| `17/02/2026` | DD/MM | Jovova |
| `10-MAY-2026` | DD-MON-YYYY | Galdon |

- **Ambiguous DD/MM vs MM/DD on unseen layouts is the main header false-fill risk.** Possible handling:
  - If the day is above 12, the format is decided.
  - Otherwise, look for other dates in the doc.
  - Otherwise, flag the field for review.
  - Note: outputting `null` scores wrong here, because the gold value is not null.

**Totals and currency.**
- Totals print as `JPY 259,233.20`, and gold is `259233.20`. The scorer compares numerically, so the comma doesn't matter.
- Currencies are spread over USD, EUR, JPY, CNY and SGD. Currency is not tied to supplier.

**Fonts and rendering.** The same supplier renders in different fonts across docs (sans, serif, monospace). Font is noise, not a layout signal.

## Waybills: one template, 10 carrier brands
| Brand | train | dev |
|---|---|---|
| Quillon | 11 | 3 |
| Bluefin | 11 | 1 |
| Skybridge | 9 | 5 |
| Orbis | 9 | 2 |
| Meridian | 7 | 4 |
| Tidewater, Silverline, Northwind, Vantrel | 6 each | 1–3 |
| Kestrel | 6 | 0 |

- **Carrier names** are `<Brand> <Air Cargo|Express|Forwarding|Freight|Logistics>`, giving 40 distinct carriers. The full name is the big title at the top. Shippers are unique per doc and come from a different name pool than the invoice suppliers.
- **Layout:**
  - A 2-column grid of labelled boxes: `MAWB`, `HAWB`, `Origin`, `Destination`, `Shipper`, `Consignee`, `No. of Pieces`, `Gross Weight (kg)`.
  - **Box order is shuffled per doc**, so position carries no information and only the label does.
  - Fonts vary (sans or monospace).
- **Formatting:**
  - MAWB is always `NNN-NNNNNNNN`.
  - HAWB is `AA########`.
  - Airports print as `AMS AMSTERDAM`, and gold keeps only the IATA code `AMS`.
- **Nulls:**
  - Only `hawb` is ever null (17 of 77, 22%), and in that case **the HAWB box is absent** (train_0012).
  - No waybill field was illegible in train.
- Waybills are the easy part. A label→value reader should get them close to 100%, and the template is likely shared with unseen test docs.

## Nulls: absent vs illegible
| Field | train null count | cause |
|---|---|---|
| invoice `awb_number` | 113 / 323 | line not printed (train_0040, train_0072) |
| invoice `invoice_number` | 17 | **illegible**: redaction bar or smudge (train_0072) |
| invoice `invoice_date` | 11 | **illegible** |
| waybill `hawb` | 17 / 77 | box not printed |
| any row field | 0 partial | a column is either fully present or fully absent |

- At most one illegible field per doc.
- Both scanned and digital docs have illegible fields, so illegibility is injected separately from scan noise.
- **"Illegible" slice tag:** superseded by note 05: invoice_number or invoice_date null, or awb_number null with its label printed. That gives 40 train and 8 dev docs.

## Implications for the approach
1. **Build a leave-supplier-out validation split.** For example, use 5 folds of ~3–4 suppliers each, or hold out about 6 suppliers from train and fine-tune on the rest. This is the only way to estimate the unseen-supplier half of test, because dev can't.
2. **Read labels and column headers, not positions.** Rules keyed per supplier won't transfer to unseen layouts. A VLM, or OCR plus an LLM reading header text, will.
3. **Multi-page handling:**
   - Concatenate rows across pages, and don't drop rows whose page has no header row (Vexova and Jovova page 2 have no header).
   - Ignore the `continued` banner and the repeated invoice number on page 2.
4. **Two-kind null policy:**
   - "Absent label → null" is easy and common, and it must never be filled in from other documents.
   - "Label present, value unreadable → null" is the case the false-fill metric is about.
5. **Row exactness on alphanumeric part numbers** dominates row F1. Scan quality plus O/0 and I/1 confusion is the risk to measure per slice.
6. **Slice meta for `score.py --meta`, all derivable:**
   - `scanned`: from the `.jpg` extension.
   - `multi_page`: page count above 1.
   - `repeated_parts`: a duplicate supplier part number among the rows.
   - `illegible`: a null invoice_number or invoice_date.
   - `unseen`: from the held-out suppliers.

## Not yet verified
- Date format and header wording for the 12 suppliers I didn't view.
- Whether each supplier's date format is fixed.
- How multi-page header repetition is distributed per supplier.
- Rotation and blur severity on scans.

These are worth a follow-up visual pass before writing any layout-sensitive post-processing.
