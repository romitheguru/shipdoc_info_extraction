# 09: Bake-off: OCR-first vs zero-shot VLM (40 dev docs, on the Mac)

Code: `bakeoff/` (`ocr_run.py`, `ocr_recall.py`, `vlm_run.py`, `postprocess.py`). Predictions and the report are in `bakeoff/preds/`.

Set: the bake-off set from note 08, which is 40 dev docs covering all 18 suppliers, of which 22 are scanned and 13 multi-page. Every supplier is unseen for a zero-shot method.

## Candidates actually run
- **OCR: PP-OCRv5 server** (PaddleOCR 3.4, CPU). I measured how often each gold value appears verbatim among its tokens. This is an **upper bound** for candidates A and C: a value OCR never produces can't be extracted, however good the mapping.
- **B: Qwen3-VL-8B-Instruct, 8-bit MLX, zero-shot.** All pages of a document go in one call, with the generic prompt in `bakeoff/vlm_run.py` (no supplier names). Its output goes through deterministic post-processing (dates, numbers, IATA codes) and is then scored by the harness.
- **Not run: PaddleOCR-VL (candidate A as specified).** Its reading accuracy belongs to the same OCR family; it is untested here and can be checked later (note 11 does this).

## Headline
| | digital | scanned |
|---|---|---|
| **Supplier part number read exactly: OCR** (upper bound) | 95.1% | 86.0% |
| **Supplier part number read exactly: VLM** (excluding the 2 column-swap docs) | **98.9%** | **92.3%** |
| invoices whose every row is possible at all: OCR | 60% | 47% |
| invoices fully correct: VLM (actual) | 89% | 59% |

**VLM full score on the 40 docs:**
- OVERALL **89.35**
- header **100%**: all 17 header fields correct in every doc, including names, dates via post-processing, totals, AWB and all waybill fields
- **false fills 0 of 15** illegible fields; it obeyed "null even if partly visible" and ignored the page-2 banner
- row F1 87.1, docs exact 72.5%
- waybills 100%
- by scan: digital OVERALL 97.3, scanned 82.9

**Decision: B wins.** The VLM reads part numbers more accurately than OCR can *at best*, and it solves the headers and the null policy with no rules. C (OCR plus an LLM for mapping) is capped by OCR's lower character accuracy, so it is dropped.

## Where the VLM loses points (all 11 imperfect invoices)
1. **Column meaning: 2 docs, the costliest failure.**
   - dev_0032 (a "TAX INVOICE"): `Your Part No.` was taken as the supplier part number, so 0 of 5 rows are right.
   - dev_0037 (3-page scan): the `PO No.` column was put into `customer_part_number`, so 0 of 30 rows are right.

   This is exactly the risk note 03 predicted.
2. **Lookalike characters on scans: 9 docs, about 1–4 rows each.** The confusions are O↔0, I↔1, S↔8, Z↔2 and V↔^ (`NGTT-8746-Z0G` read as `…ZOG`, `GLT/28551/S5S` as `…858`, `LH-25860-12OU` as `…120U` three times). Two digital docs also have one error each, both the O/0 in `GHSR61902O6`.
3. **No dropped, merged or duplicated rows.** Predicted row counts equal gold in all 32 invoices, multi-page and repeated parts included.

## A review-flag signal is available
"OCR doesn't contain the VLM's part number verbatim" catches **14 of 24** wrong VLM part numbers while flagging **33 of 388** correct ones (8.5%). The other 10 errors are lookalike misreads that OCR shares. OCR confidence alone is worse: a threshold of 0.98 catches 41 of 50 OCR misses but flags 20% of correct values.

## Runtime (Mac, 8-bit)
- Median 18 s per doc; ~30-row multi-page docs take 50–85 s.
- Two docs took 34–53 min. They produced the same output length as an 85 s doc, so this was environmental (the OCR job was competing for CPU and memory), not runaway generation.
- Needs re-timing without the parallel OCR job before projecting the test run (note 11 does this).

## What to do next (step 3)
1. **Make the column decision explicit.** Have the model first output the table's column headers with a role for each (`supplier_pn | customer_pn | po | qty | other`), then the rows. This makes the column decision visible and checkable, and lets a header-role sanity check catch swaps.
2. **Give the model more pixels per character on scans.** Try 1.5× upscaling (glyphs are ~11 px; at 32 px per token the model gets about 3 glyph heights per token). Measure on the scanned slice.
3. **Review flag:** VLM-OCR disagreement on IDs, plus an ambiguous-date flag from post-processing, plus a check for columns whose meaning is uncertain.
4. **Confirm on the folds and across model sizes and quantisations** (note 11).

## Caveats
- n = 40, so ±1 doc is ±2.5 points on "docs exact".
- The prompt was written by someone who has seen all suppliers' headers (note 08 caveat). It names no supplier, but its examples of header wording come from train.
- OCR `total_amount` on scans (23.5% found) is probably an artefact of how my matcher splits tokens; this is unverified and doesn't affect the decision.
