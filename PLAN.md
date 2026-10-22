# Plan: read carefully, map with a model, null only when the value is obscured

The evidence for each decision is in `analysis-notes/` (notes 01–10).

## Principles
1. **Characters are read exactly.** One wrong character in a part number fails the row and the document (note 07: −19 OVERALL for one error per invoice). No string "correction" and no catalogue snapping.
2. **Field meaning comes from a model, not supplier rules.** Train has one header vocabulary, and the column headers collide (`Our` vs `Your Part No.`, `Your Order` = PO). Rules keyed on train wording would score ~100% on dev and fail on unseen suppliers (note 03).
3. **Null only when the value is absent or obscured** (black bar or scribble), even if some characters show through and even if page 2 prints it (note 05). **If readable but uncertain → best guess plus a review flag**, because null on a readable field scores the same as wrong (note 07).
4. **Deterministic post-processing:** ISO dates, bare IATA codes, plain numbers, verbatim IDs (note 02).
5. **Honest evaluation:** leave-supplier-out folds give the `unseen` slice. Dev measures seen suppliers only (notes 01, 02).
6. **No fine-tuning.** 400 docs from 18 suppliers with reused catalogues invite memorisation, and it would add cost and two extra deliverables.
7. **Built for volume, not one doc at a time** (note 10): model weights ≤ ~12 GB of the 24 GB budget, served with batching, with throughput and latency reported next to accuracy.

## Architecture (note 10)
```
pages ─► router (doc_type) ─► extractor: Qwen3-VL, per-type prompt + JSON schema ─► post-processing ─► predictions
                                      │
                    verifier: PaddleOCR-VL ──► disagreement ─► needs-review flags (separate file)
```
One extractor model specialised by prompt, not one model per document type. The verifier only flags; it never overwrites a value unless step 2b shows that helps.

## Clean hold-out rule
**Fold 4** (Brenara, Kastara, Kastitek, Lumex + carriers Orbis, Silverline) is the clean unseen check. Prompt changes may only be driven by errors on docs **outside** fold 4. The fold-4 numbers are reported as the most honest unseen estimate; the 5-fold mean is reported alongside with the caveat that prompt iteration saw the other folds.

## Work units
Done: steps 0–2 (notes 01–09: data analysis, eval harness, Mac bake-off → zero-shot VLM wins).

Each unit is small enough to finish and check in one sitting. "Done when" is the acceptance check.

### Phase A: right-size the model on the Mac (step 2b)
Runs locally with MLX on the M5 Pro (24 GB unified memory, shared with the OS). One model job at a time; weights ≤ ~12 GB.

| # | Unit | Done when | Effort |
|---|---|---|---|
| A1 ✅ | Add timing and peak-memory logging to `bakeoff/vlm_run.py` | Re-running a few docs at 8B 8-bit gives per-doc latency and peak memory | 0.25 h |
| A2 ✅ | Size sweep on the 40 docs, one model at a time: 8B 8-bit (existing 89.4 baseline), 8B 4-bit, 4B 8-bit; 2B on doc_type + waybills only | One table: OVERALL, false fills, part-number exact % (digital/scanned), s/doc p50/p95, peak memory | 1 h (mostly unattended) |
| A3 ✅ | Verifier: try PaddleOCR-VL on the same pages; measure its part-number exact-read rate and the precision/recall of "disagrees with extractor" as a review flag. If it won't run in reasonable time on the Mac, keep the PP-OCRv5 flag | Verifier chosen; kept only if it beats the PP-OCRv5 flag (14/24 caught, 8.5% false flags) | 1 h |
| A4 ✅ (8-bit provisional; B3 switched to 4-bit, note 12) | Write note 11, decide: extractor size and quantisation, whether the 2B fast path and the verifier stay | Note 11 + `PLAN.md` updated | 0.5 h |

**Decision gate after A4:** choose the smallest extractor within ~1 OVERALL point of the best, with false fills no worse.

### Phase B: build the pipeline (`shipdoc/`)
| # | Unit | Done when | Effort |
|---|---|---|---|
| B1 ✅ | Skeleton and CLI: `uv run python -m shipdoc.predict --split dev\|test --out P.json`, page grouping by doc, stdlib schema validation of the output | A stub run writes a file that passes `schema.json` and the scorer | 0.5 h |
| B2 ✅ | Post-processing module moved from `bakeoff/postprocess.py`, with unit tests for dates (incl. ambiguous slash dates), IATA codes, numbers, verbatim IDs | Tests pass; gold header values round-trip unchanged | 0.5 h |
| B3 ✅ v1 + 3 fixes, frozen on 8B 4-bit (note 12) | Extractor: per-type prompts and JSON schemas; invoice prompt states column roles before rows; multi-page tables | Bake-off set ≥ A3's best, both column-swap docs from note 09 fixed or explained | 1 h |
| B4 ✅ classify call | Router (or doc_type from the extractor call, if A4 drops the 2B) | doc_type 100% on dev | 0.25 h |
| B7 🔶 code done, not run (cut for time) | Portable backend: the same model and prompts through Hugging Face `transformers` (CUDA or CPU), selected by a `--backend mlx\|hf` flag, so graders without a Mac can reproduce | Runs 2–3 docs end to end on CPU and matches the MLX output on them | 0.5 h |
| B5 ✂️ cut | Scan upscaling experiment: 1.5× on `.jpg` pages | Kept only if scanned row F1 improves without a latency blow-up | 0.5 h |
| B6 ✅ PaddleOCR-VL not_in_ocr + ambiguous dates; repairs not flagged (note 12) | Review flag: verifier disagreement + ambiguous dates + uncertain column roles → `review_flags.json` | Flag precision/recall measured on dev | 0.75 h |

### Phase C: evaluate honestly
| # | Unit | Done when | Effort |
|---|---|---|---|
| C1 ✅ dev run (no train run: nothing is trained, fold 4 of dev is the unseen slice) | Full dev run and all 500 docs for the folds; slice tables (scanned, multi-page, repeated parts, illegible, seen/unseen) | Numbers from `eval.evaluate` for dev, fold 4 and the 5-fold mean | 0.5 h work + ~2.5 h unattended Mac run |
| C2 ✅ analysis only, no further fix round (frozen) | Error analysis by slice; one round of fixes that generalise (driven by errors outside fold 4 only) | Note 12 with failure modes and before/after | 1 h |
| C3 ✅ from the run caches | Throughput on the Mac: s/doc p50/p95, docs/hour, peak memory, and what that means for the assumed volume (note 10) | A row in note 12 and the report | 0.25 h |

### Phase D: ship
| # | Unit | Done when | Effort |
|---|---|---|---|
| D1 ✅ 200 docs, schema-valid | Test run on the Mac | `test_predictions.json` has 200 docs and passes the schema check | 0.25 h work + ~1 h unattended |
| D2 ✅ README + scripts; local commits | Reproducibility: README with end-to-end commands for both backends, pinned model revisions, seeds, `uv.lock`; first commits | A fresh clone reproduces dev numbers | 0.5 h |
| D3 ✅ | Public GitHub repo (confirmed before publishing) | Repo URL works | 0.1 h |
| D4 ✅ 2 pages, with repo link | `report.pdf`, 2 pages max: approach, slice results, failure modes, new-layout handling, review-flag precision/recall, throughput, links | PDF ≤ 2 pages with all links | 1 h |

**Remaining effort:** about 12 h of hands-on work (A ~2.75 h, B ~4 h, C ~1.75 h, D ~2 h) plus ~4–5 h of unattended model runs. Together with steps 0–2 this is well over the brief's suggested 6–8 h; A2–A3 and B5 are the first to cut if time runs short (fall back to 8B 8-bit + the PP-OCRv5 flag from note 09).

## Freeze (time budget)
After B3 the configuration was frozen to fit the time budget: 8B 4-bit, prompt v1 + fixes. B5, the B7 check, per-fold re-runs and the PP-OCRv5 second tier were cut; the prompt v2 experiment was stopped (slower). Details in note 12.

## Compute
- All processing, experiments and runs were done locally on my MacBook Pro (M5 Pro, 24 GB unified memory) with MLX.
- The memory is shared with the OS and other apps: one model job at a time, weights ≤ ~12 GB, heavy apps closed during long runs. (In note 09, running OCR and the VLM together caused 34–53 min outliers.)
- Graders without a Mac use the `transformers` backend (B7) on a 24 GB GPU or CPU. The report states that official numbers come from MLX.
- The vLLM batching design in note 10 is a production recommendation, reported as untested.
- No paid APIs at inference.

## Known caveat for the report
I looked at all 18 train suppliers while writing notes 01–07. "Held-out" therefore means no learned parameters, few-shot examples or thresholds come from the held-out suppliers; it cannot undo human familiarity. To mitigate this, no rule may reference a supplier name, prefix or layout position, and fold 4 is kept clean of prompt iteration.
