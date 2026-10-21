# Analysis notes

Each analysis done during development is one numbered file here: `NN-short-kebab-title.md`. Take the next free number and never renumber.

| # | Note | Summary |
|---|---|---|
| 01 | [Supplier & layout distribution](01-supplier-layout-distribution.md) | 18 invoice suppliers with fixed layouts and one shuffled waybill template; dev has no unseen suppliers; most nulls are absent fields, not illegible ones |
| 02 | [Gold-label conventions](02-gold-label-conventions.md) | The page→gold output rules (ISO dates, bare IATA codes, plain numbers, verbatim IDs); ~40-part catalogue per supplier with 99% of dev rows reused, so catalogue memorisation is a risk; ship_to ≠ buyer in 40% |
| 03 | [Supplier visual census](03-supplier-visual-census.md) | Layout table for all 18 suppliers; identical header labels in train (a generalisation gap); "Our/Your Part No." column traps; date formats; page-2 header repeat; totals only on the last page |
| 04 | [Scan quality](04-scan-quality.md) | Scans are mild (≤1.6° skew, JPEG q 45–75), test matches train, glyphs ~11 px; keep native resolution, no heavy preprocessing |
| 05 | [Illegibility](05-illegibility.md) | Black bars and scribbles on invoice_number, date and AWB (≥48 docs); gold stays null even when the page-2 banner shows the value; null AWB is usually absent, sometimes redacted |
| 06 | [Token & runtime budget](06-token-and-runtime-budget.md) | 2,772 tokens/page at native res, ≤10.5k per doc, ≤1.9k output; a 7B VLM fits 24 GB for inference, training needs a bigger GPU or QLoRA |
| 07 | [Score sensitivity](07-score-sensitivity.md) | One wrong char per invoice costs −19; column-semantics errors −17 to −23; nulling a legible field never helps, so guess and flag; slice meta files written |
| 08 | [Evaluation setup](08-evaluation-setup.md) | 5 leave-supplier-out folds (the unseen slice), a 40-doc bake-off set covering all 18 suppliers and enriched for hard slices, and a harness verified identical to score.py |
| 09 | [Bake-off: OCR vs VLM](09-bakeoff-ocr-vs-vlm.md) | Zero-shot Qwen3-VL-8B beats OCR on part numbers (98.9/92.3% vs a 95.1/86.0% ceiling); 100% headers, 0 false fills, OVERALL 89.4; losses come from 2 column swaps and lookalike characters on scans; VLM is chosen |
| 10 | [Serving architecture & model sizing](10-serving-architecture-and-model-sizing.md) | Volume/latency assumptions; weights ≤ ~12 GB of 24 GB so KV cache allows ~5–14 concurrent docs; vLLM with batching and JSON-schema decoding; one extractor specialised by prompt, plus a parser as verifier for review flags; shortlist for a GPU size sweep |
| 11 | [Model size sweep & verifier](11-model-size-sweep-and-verifier.md) | 2B/4B out; 8B 4-bit ≈ 8-bit but reads PO as P0 (quantisation), so 8B 8-bit stays (11.9 GB peak, 16 s/doc, deterministic); PaddleOCR-VL reads worse than PP-OCRv5 but is the better verifier (89% vs 72% value recall); OCR flags can't see column swaps |
| 12 | [Final config & dev results](12-final-config-and-dev-results.md) | Column-role prompt v1 + 3 generic fixes; frozen on 8B 4-bit (91.0 bake-off, 0 false fills, 19 s/doc) after v2 proved slower; dev slices, fold-4 unseen estimate, review-flag precision/recall, throughput |
