# 05: What illegibility looks like, and what gold expects

Montages of every illegible case in train+dev were made with `analysis-notes/scripts/montage.py`. The AWB-line detector is `analysis-notes/scripts/05_awb_line_presence.py`.

## TL;DR
- **Only 3 header fields are ever illegible:** `invoice_number`, `invoice_date` and **`awb_number`**. Note 01 missed the AWB case. Names, currency, totals, row cells and all waybill fields are never illegible in train or dev.
- **There are two obscuring styles, about equally common:**
  - **Solid black redaction bar** (26 cases). Nothing is visible.
  - **Scribble overwrite** (22 cases). The **first 1–3 characters often stay visible** (`20…`, `NB…`, `GL…`), which is exactly what tempts a model to complete the value. Gold is `null`.

  No smudges, fading or cut-offs appear in train or dev, although the brief mentions them. Test may contain them.
- **Gold is `null` even when the value is legible elsewhere.** In all 6 multi-page docs with an illegible page-1 invoice number, the page-2 banner (`PACKING LIST - continued  NB69351810`) prints it cleanly, yet gold is `null` (train_0091, 0128, 0253, 0282, 0283, 0301). The rule is **"legible at its labelled location"**, not "recoverable from the document". A model reading the banner produces a false fill.
- **A null `awb_number` means one of two things:** the line is **absent** (~100 docs, the common case), or the line is printed but **redacted** (13 confirmed, 9 bars and 4 scribbles). Both score as `null`, but only the second belongs in the "illegible" slice.

## Counts (train + dev)
| Field | illegible (label printed, value obscured) | black bar | scribble |
|---|---|---|---|
| invoice_number | 19 | 9 | 10 |
| invoice_date | 16 | 8 | 8 |
| awb_number | ≥ 13 (detector finds only clean 3- or 4-line headers) | 9 | 4 |
| **total** | **≥ 48 docs** (≈ 12% of invoices) | 26 | 22 |

- Each doc has at most one illegible field in every case seen.
- Illegibility hits scanned and digital docs alike, and every supplier.
- The AWB detector counts text lines in the header block, where a 4th line means the AWB label is present. It is confident on 87% of AWB-null docs. On the rest, the header block sits outside the expected band (scan offsets), so some redacted AWBs may be missed.

## Slice definition used from now on
`illegible = invoice_number is null OR invoice_date is null OR (awb_number is null AND the AWB label line is printed)`. This gives 40 train and 8 dev docs (`analysis-notes/out/meta_*.json`, written by the note 07 script).

## Implications
1. **The null policy has three cases:**
   - Label absent → null.
   - Label present with a bar or scribble → null, **even if some characters show through and even if the value appears elsewhere.**
   - Label present and legible → read it.
2. **Training data must include these cases.** If I fine-tune, the ~48 illegible examples (plus the AWB-absent ones) teach the null behaviour. Zero-shot prompts must spell out the rule, especially "don't use the page-2 banner".
3. **Synthetic illegibility is cheap and worth doing.** Drawing bars and scribbles over legible header values in train images multiplies the 48 examples. It could also add smudge, fade and cut-off variants to hedge against test containing styles that train doesn't.
4. **A review flag can be targeted.** Visible ink over a field (a bar or scribble detector) is a strong, cheap signal for the optional "needs review" flag and for checking the model's own nulls.
