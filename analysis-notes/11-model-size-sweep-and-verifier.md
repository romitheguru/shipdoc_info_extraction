# 11: Model size sweep and verifier choice (Mac, MLX)

Code:
- `bakeoff/sweep.sh` runs the sweep, one model at a time.
- `bakeoff/sweep_report.py` builds the table.
- `bakeoff/ocrvl_run.py` runs PaddleOCR-VL.
- `shipdoc/flags.py` and `eval/flags.py` produce and score the review flags.

Everything runs on the 40-doc bake-off set (note 08), on a MacBook Pro M5 Pro with 24 GB unified memory, using the bake-off prompt from note 09 unchanged.

## A2: extractor size
| Model (MLX) | OVERALL | digital | scanned | row F1 | docs exact | false fills | supplier PN exact dig/scan | s/doc p50 | p95 | peak GB |
|---|---|---|---|---|---|---|---|---|---|---|
| Qwen3-VL-2B 8-bit | 55.5 | 57.8 | 53.7 | 34.6 | 20.0% | **2/15** | 72.1 / 33.2 | 6.0 | 22.9 | 4.5 |
| Qwen3-VL-4B 8-bit | 84.0 | 88.9 | 80.1 | 87.1 | 47.5% | 0/15 | 97.3 / 88.6 | 10.6 | 49.7 | 7.1 |
| Qwen3-VL-8B 4-bit | 90.5 | 94.0 | 87.6 | 91.3 | 70.0% | 0/15 | 98.4 / 90.0 | 10.2 | 49.2 | 7.9 |
| Qwen3-VL-8B 8-bit | 89.4 | 97.3 | 82.9 | 87.1 | 72.5% | 0/15 | 98.9 / 90.4 | 16.4 | 75.7 | 11.9 |

**Determinism and timing:**
- Re-running 8B 8-bit gave identical outputs on all 40 docs, so greedy decoding is deterministic.
- Note 09's timings (median 18 s, outliers of 34–53 min) were inflated by a parallel OCR job. The clean figures are a 16.4 s median and a 76 s p95.

**Findings:**
- **2B is out.** It fills illegible fields (2 false fills), misreads two-thirds of scanned part numbers, produced one unparseable output and scores 82.5 on waybills. It can't serve as a router or waybill fast path either.
- **4B is out** at −5.4 OVERALL. Its headers are fine (99.1%), but whole-table column errors on 4 more invoices bring docs exact down to 47.5%.
- **8B 4-bit's OVERALL lead is one document.** It mapped dev_0037's columns correctly (29/30 rows) where 8-bit failed (0/30), a single column decision.
- **8B 4-bit has a real character-fidelity loss.** On digital dev_0033 it read the `PO` prefix as `P0` in 9 of 20 rows (`P04503319053`); 8-bit read all 20 correctly. This is the quantisation risk note 10 predicted. Both models misread `12OU` as `120U` (dev_0069).
- **Memory:** 8-bit peaks at 11.9 GB, inside the ~12 GB budget; 4-bit at 7.9 GB.

**Decision (A4, provisional until B3; superseded by note 12, which switched to 8B 4-bit):**
- **Extractor: Qwen3-VL-8B 8-bit.** Character fidelity comes first (principle 1: one wrong character costs about −19 OVERALL, note 07). Its cost is 1.6× slower, about 55 vs 35 min for the 200 test docs.
- **8B 4-bit is the documented throughput option.** B3 runs both with the column-role prompt. If 4-bit still leads once column mapping no longer decides the result, switch.
- **No router model.** doc_type comes from a short classification call to the same model.

The fold-4 caveat: dev_0033 is Lumex (fold 4). Choosing a model on the agreed bake-off set is allowed, but no prompt change may be made in response to this error (PLAN.md clean hold-out rule).

## A3: second reader (verifier) for the review flag
PaddleOCR-VL (MLX 8-bit, `OCR:` prompt, whole page) against PP-OCRv5 server (note 09).

**Reading accuracy, gold value found verbatim:**

| | PP-OCRv5 (dig / scan) | PaddleOCR-VL (dig / scan) |
|---|---|---|
| supplier_part_number | 95.1 / 86.0 | 91.3 / 87.8 |
| customer_part_number | 100 / 100 | 100 / 88.8 |
| purchase_order | 100 / 96.5 | 100 / 91.2 |
| quantity | 100 / 98.7 | 100 / 90.8 |
| speed, memory | CPU, slow (minutes per page when contended) | 3.3 s/page median, 2.3 GB peak |

PaddleOCR-VL reads worse and sometimes **invents values**: gold `CP-172494` appears as `CP-168427`, and part numbers lose characters (`UO/094/TO` → `UO/945/T`). So it would be a poor primary reader. Whole-page input is outside its usual setup, which pairs it with a layout detector and element crops; that setup wasn't tested.

**As a verifier**, the question is whether it disagrees with the extractor when the extractor is wrong. The table uses the `not_in_ocr` flag on the 8B 8-bit outputs and excludes the 2 column-swap docs, since an OCR text check can't see a column mapping by design.

| Verifier | doc precision | doc recall | value precision | value recall | values flagged |
|---|---|---|---|---|---|
| PP-OCRv5 | 58.3% | 77.8% | 26.5% | 72.2% (13/18) | 49 |
| **PaddleOCR-VL** | **64.3%** | **100%** | **28.1%** | **88.9% (16/18)** | 57 |
| either disagrees | 56.2% | 100% | 20.9% | 100% (18/18) | 86 |
| both disagree | 87.5% | 77.8% | 55.6% | 55.6% (10/18) | 18 |

The pattern holds for the 8B 4-bit outputs too: PaddleOCR-VL gives 93% value recall, against 83% for PP-OCRv5.

PaddleOCR-VL beats PP-OCRv5 as a verifier despite reading worse, because its mistakes are less correlated with the extractor's. Combining the two gives a two-tier flag: "both disagree" is a high-precision tier (87.5% doc precision), "either disagrees" catches every error.

**Decision:**
- **The verifier is PaddleOCR-VL.** It catches more errors, is fast on the Mac, needs only 1.1 GB of weights and runs on the same MLX stack.
- **PP-OCRv5 is optional** as a second tier for a "high-confidence review" flag. It's left out by default because it is slow on CPU.

**Caveat:** only 18 wrong values (9 docs) in this comparison, so each one is about 5 points of value recall.

## B6 baseline: what the flag doesn't catch yet
- **Column-mapping errors** (dev_0032, dev_0037: 35 wrong rows) are invisible to any OCR text check. The column-role flags from B3 (duplicate or missing roles, unknown headers) are the planned signal and are measured with B3.
- **Lookalike-character pattern rejected.** A rule flagging O/0 or I/1 inside a run of the other character class caught 0 of 18 errors, and it matches 2.1% of correct gold IDs.
