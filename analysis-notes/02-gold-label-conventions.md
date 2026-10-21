# 02: How gold turns page text into values

Script: `analysis-notes/scripts/02_gold_conventions.py` (train+dev labels, 500 docs). Each page-to-gold mapping below was checked by eye against the page images viewed for note 03.

## TL;DR
- **Gold is normalised in a few fixed ways, and everything else is copied verbatim.** The output rules are short (table below). The scorer's normalisation already absorbs commas, case and punctuation in names, but it does **not** absorb date formats or airport city names.
- **Each supplier has a ~40-part catalogue.** There are only 719 distinct supplier part numbers across 4,930 rows, and **912 of 924 dev rows (99%) reuse a part from the same supplier's train catalogue.** A fine-tuned model can memorise catalogues and look great on dev while learning nothing that transfers to unseen suppliers.
- **There are only 5 buyers** across all 400 invoices, and only 5 currencies. A model can memorise these too.
- **Ship-to differs from the buyer in 40% of invoices** (160/400). Copying "Sold To" into ship_to is a real error mode.
- **There are no cross-document links.** No invoice `awb_number` matches any waybill `mawb`, there are no duplicate invoice numbers or MAWBs, and no train/dev leakage.

## Page → gold mapping rules
| Field | Page shows | Gold | Scorer forgiving? |
|---|---|---|---|
| invoice_date | `01/23/2026`, `17/02/2026`, `10-MAY-2026`, `September 02, 2026`, `2026-05-04` | `YYYY-MM-DD` | **No.** Must be exact ISO. |
| total_amount | `Total Amount: JPY 259,233.20` | `259233.20` (always 2 decimals, including JPY) | Yes. Compared numerically, commas ignored. |
| quantity | `5,000` | `5000` (integers only) | Yes. Compared numerically. |
| currency | `JPY` (header) | `JPY`; one of USD, EUR, SGD, JPY, CNY | Case only. |
| origin/destination | `AMS AMSTERDAM` | `AMS` | **No.** Must strip the city. |
| carrier | big title `MERIDIAN FREIGHT` | `Meridian Freight` | Yes. Names ignore case and punctuation. |
| supplier_name | letterhead `Talitek Power Systems Pte Ltd` | verbatim, legal suffix included | Yes, for case and punctuation. A dropped suffix (`Pte Ltd`) is still wrong. |
| buyer / ship_to | `Sold To:` / `Ship To:` blocks | verbatim | as above |
| invoice_number, awb_number, mawb, hawb | as printed | verbatim (`AA########`, `###-########`) | Case and spaces only. **A wrong hyphen fails the field.** |
| part numbers, PO, cust PN | as printed, including O/0 and I/1 lookalikes | verbatim | Case and spaces only. |
| gross_weight_kg, pieces | `366.5`, `29` | verbatim | numeric |

No gold value contains whitespace inside an identifier. Name fields keep their legal suffixes (`S.A. de C.V.`, `Co., Ltd`, `Sdn Bhd`, …).

## Value distributions worth knowing
- **Quantities:** 7 round values make up about 88% of rows (100, 250, 500, 1000, 2500, 3000, 5000). The rest are "odd" values like `3,186` or `41`. A model biased toward round numbers will misread the odd ones.
- **Dates:** all in 2026 (Jan–Sep). 23% of dates (87/384) have day ≤ 12, so a slash date with an unknown format is ambiguous about a quarter of the time.
- **Airports:** 14 IATA codes, and origin ≠ destination always.
- **Waybill parties:** shippers and consignees are unique per document and don't overlap with the invoice supplier or buyer pools. Waybills can't be cross-checked against invoices.
- **Customer part numbers** aren't tied to the supplier part number (276 of 280 part numbers appear with several different customer part numbers), so they can't be inferred.
- **Part-number tokenisation:** the Qwen tokenizer splits digits individually (`GHSR274209` → `G, HS, R, 2, 7, 4, 2, 0, 9`), which suits exact copying.

## Implications
1. **Post-processing rules:**
   - Convert dates to ISO (needs the date-format decision from note 03).
   - Strip totals to a plain number.
   - Keep only the 3-letter IATA code for airports.
   - Everything else is copied verbatim; no "cleaning" of identifiers.
2. **Don't snap readings to a known catalogue as a default.** It inflates seen-supplier scores and does nothing for unseen ones. It could be a *seen-supplier-only* fallback with a review flag, but it must be reported honestly in the slices.
3. **Evaluate with suppliers held out.** Because of catalogue reuse, any number measured on dev or seen suppliers is optimistic in a way that can't be fixed after the fact.
