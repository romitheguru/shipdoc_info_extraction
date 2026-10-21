# Shipping-document extraction: zero-shot Qwen3-VL with a second-reader review flag

Page images of an invoice or air waybill go in; the JSON from `schema.json` comes out, plus a separate file of
"needs review" flags. Nothing is trained: one open-weight vision-language model (Qwen3-VL-8B-Instruct, 4-bit) reads all
pages of a document with a per-type prompt, deterministic code normalises the values, and a second, independent
reader (PaddleOCR-VL) flags values it can't find on the page.

- Report: [`report.pdf`](report.pdf) (2 pages)
- Test predictions: [`test_predictions.json`](test_predictions.json) and [`test_predictions_review_flags.json`](test_predictions_review_flags.json)
- Every analysis behind a decision: [`analysis-notes/`](analysis-notes/README.md) (numbered notes 01–12)
- No Hugging Face model or W&B run: nothing is trained (see the report for why).

## Pipeline
```
pages ─► classify page 1 (invoice | waybill) ─► extract: Qwen3-VL-8B, per-type prompt, all pages in one call
      ─► assemble (invoice column roles + two generic repairs) ─► normalise (ISO dates, IATA, numbers) ─► predictions
                                                       │
      PaddleOCR-VL reads every page ─► "value not on the page" disagreement ─► review flags (separate file)
```
| Code | What it does |
|---|---|
| `shipdoc/prompts.py` | the three prompts (classify, invoice, waybill); no supplier names, prefixes or positions |
| `shipdoc/backends.py` | `mlx` (Apple Silicon, used for all reported numbers) and `hf` (transformers, CUDA or CPU) |
| `shipdoc/extract.py` | JSON parsing, column roles → rows, the two column repairs |
| `shipdoc/postprocess.py` | dates, numbers, currency and IATA normalisation; verbatim IDs |
| `shipdoc/flags.py` | review flags from the second reader |
| `shipdoc/predict.py` | the CLI; caches raw model output per doc so runs resume |
| `eval/` | scorer-identical evaluation with slices (`eval.evaluate`), leave-supplier-out folds, flag precision/recall (`eval.flags`) |
| `bakeoff/` | the model comparisons from notes 09 and 11, and the PaddleOCR-VL page reader (`ocrvl_run.py`) |

## Reproduce
Requirements: [uv](https://docs.astral.sh/uv/), Python 3.11 (uv installs it), and the assignment's `data/` folder
(train/dev/test images and labels) copied into the repo root; it is not committed. All numbers in the report come from a
MacBook Pro (M5 Pro, 24 GB unified memory) with MLX. Model weights download from Hugging Face on first use
(Qwen3-VL-8B 4-bit ≈ 5 GB, PaddleOCR-VL 8-bit ≈ 1 GB).

```bash
uv sync --group bakeoff                                  # MLX + PaddleOCR stack (Apple Silicon)
uv run python -m unittest discover tests                  # 29 tests: post-processing, assembly, flags, schema

# 1. extract (one model call to classify + one to extract per doc; ~30 s/doc on the M5 Pro)
uv run --group bakeoff python -m shipdoc.predict --split dev  --out runs/dev_noflags.json
uv run --group bakeoff python -m shipdoc.predict --split test --out runs/test_noflags.json
# 2. second reader for the review flags (~3 s/page)
uv run --group bakeoff python -m bakeoff.ocrvl_run --set dev
uv run --group bakeoff python -m bakeoff.ocrvl_run --split test
# 3. predictions + flags (re-uses the cached model outputs, so this takes seconds)
uv run --group bakeoff python -m shipdoc.predict --split dev  --ocr-cache bakeoff/cache/ocr_paddleocr_vl --out runs/dev.json
uv run --group bakeoff python -m shipdoc.predict --split test --ocr-cache bakeoff/cache/ocr_paddleocr_vl --out test_predictions.json
# 4. score
python3 score.py --gold data/dev/labels --pred runs/dev.json                 # official scorer
uv run python -m eval.evaluate --pred runs/dev.json --set dev                # same numbers + slices
uv run python -m eval.evaluate --pred runs/dev.json --set dev/fold:4         # clean unseen-supplier slice (see below)
uv run python -m eval.flags --pred runs/dev.json --set dev                   # review-flag precision / recall
uv run python scripts/make_report.py --dev runs/dev.json                     # report.pdf from the dev results
```
`scripts/run_pipeline.sh` runs steps 1–3 (test, then dev). Without a Mac, use the transformers backend
(`uv sync --group hf`, then `--backend hf` on `shipdoc.predict`; BF16 weights `Qwen/Qwen3-VL-8B-Instruct`, needs
~18 GB of GPU memory). That path is implemented but was **not run** for this submission, so its numbers may differ
slightly from the MLX ones (different kernels and quantisation).

**Determinism.** Decoding is greedy (temperature 0) and the HF backend seeds torch with 0. Re-running the MLX model
gave byte-identical outputs on all 40 bake-off docs (note 11). Models: `mlx-community/Qwen3-VL-8B-Instruct-4bit`,
`mlx-community/PaddleOCR-VL-8bit`; package versions are pinned in `uv.lock`.

## Honest evaluation
- Dev contains only suppliers seen in train, but nothing here is trained, so every supplier is unseen *by the model*.
  The risk is the human one: prompts were written after looking at dev errors.
- **Fold 4** (`eval/folds.json`: Brenara, Kastara, Kastitek, Lumex, carriers Orbis and Silverline) was kept clean: no
  prompt or rule change was made in response to an error on those docs, and no rule names a supplier, prefix or
  layout position. `--set dev/fold:4` (the fold-4 docs of dev) is the unseen-supplier estimate in the report.

## Original package
| File | What it is |
|---|---|
| `shipment_doc_extraction.pdf` | the task, rules, scoring and deliverables |
| `data/train`, `data/dev`, `data/test` | page images (and labels for train/dev) |
| `schema.json`, `sample_submission.json` | submission format |
| `score.py` | the official scorer |
