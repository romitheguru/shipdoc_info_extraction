# FourKites take-home: Shipping-Document Extraction

The full brief is `shipment_doc_extraction.pdf`. This file summarises it, so the PDF only needs re-reading when an exact detail is in doubt. AI assistance is allowed for this assignment.

## Task
Read the page images of shipping documents and output structured JSON. Return `null` for any value that is missing or illegible. Each document is classified as `invoice` or `waybill`.

| doc_type | Header fields | Line items |
|---|---|---|
| invoice (~80%) | invoice_number, invoice_date (ISO YYYY-MM-DD), supplier_name, buyer_name, ship_to_name, currency (ISO 4217), total_amount (plain number), awb_number | every table row: supplier_part_number, customer_part_number, purchase_order, quantity |
| waybill (~20%) | carrier, mawb, hawb, origin_airport, destination_airport (IATA), shipper_name, consignee_name, pieces, gross_weight_kg | none (`[]`) |

All values are strings or `null`. The exact format is in `schema.json`, and `sample_submission.json` shows the submission shape: one object keyed by doc_id.

### Rules
- Output **exactly** what is on the page. Don't correct, complete or infer. For example, gold `GHSR61902O6` contains a letter O and must stay that way.
- If a value is missing or illegible, output `null`. A guess scores as wrong and is also counted as a **false fill**.
- Line items can be in any order, but every row counts, including repeated part numbers.
- A PO may be printed per row or once for the whole invoice (see the schema description).

## Data (`data/`)
| split | docs | pages | labels |
|---|---|---|---|
| train | 400 (323 invoices / 77 waybills) | 536 | yes |
| dev | 100 (same suppliers as train) | 135 | yes |
| test | 200 | 280 | no |

- Pages are named `<doc_id>_p<N>.png|jpg`. A `.jpg` page is a scan (rotation, noise, blur, compression); about 40% of pages are scans.
- There are about 20 fictional suppliers, each with its own layout, header wording, date format and part-number style.
- About 40% of invoices are multi-page, and the table header may not repeat on page 2. Tables have 1–30 rows.
- About half the test documents come from **unseen suppliers or layouts**.
- A label JSON has `doc_id`, `doc_type`, `header`, `line_items` and `pages`. It has **no** supplier ID, scan flag or slice tags, so these have to be derived.
- All data is synthetic.

## Scoring (`score.py`, the official scorer, stdlib only)
```
python3 score.py --gold data/dev/labels --pred dev_preds.json [--meta slices.json] [--out report.json]
OVERALL = 0.4*header_field_acc + 0.4*line_item_row_F1 + 0.2*docs_fully_correct
```
- For waybills, the line-item term is replaced by header accuracy.
- A row is correct only if all 4 of its fields match. Rows are matched one-to-one, regardless of order.
- A document is fully correct when doc_type, every header field and exactly the right set of rows all match.
- Normalisation:
  - **names:** case, spacing and punctuation are ignored.
  - **IDs:** only case and whitespace are ignored (`AB-12 != AB12`).
  - **numbers:** compared numerically, with commas ignored.
  - **dates:** must be exact ISO.
  - **currency and airport codes:** case is ignored.
- `--meta` takes a JSON list of `{doc_id, <tag>: bool}` and reports each slice. Slices are built by us: scanned, multi_page, repeated_parts, illegible, seen/unseen supplier.
- The graders focus on **unseen suppliers** and the **false-fill rate**: "90% right and knows its 10% beats 93% right and can't tell."

## Constraints
- Any open-weight model or library is allowed: OCR plus rules, VLMs, fine-tuning.
- Inference must run on **one GPU with at most 24 GB, or on CPU**. **No paid hosted APIs at inference time.**
- No hand-labelling of test images. The suggested effort is about 6–8 hours, and honest analysis is valued over the leaderboard score.

## Deliverables
1. `test_predictions.json`: all 200 test documents.
2. `report.pdf` (2 pages at most) covering:
   - the approach and why it was chosen
   - dev results by slice (scanned/digital, seen/unseen supplier, multi-page, repeated parts, illegible) and the failure modes
   - how a new supplier layout would be handled
   - optionally, a per-field confidence or "needs review" flag with its precision and recall on dev
   - all the links below
3. A public GitHub repo with seeded, documented, end-to-end reproduction from the images.
4. Only if something is trained: a Hugging Face model with a model card (training data, intended use, metrics, limitations).
5. Only if something is trained: a W&B run with train/eval loss, dev OVERALL plus its slice breakdown, and the config.

## Repo conventions
- Python env and packages are managed with **uv** (`pyproject.toml` + `uv.lock`, Python 3.11). Add deps with `uv add` (analysis-only deps go in `uv add --group analysis`) and run everything with `uv run python ...`. Never use pip or requirements.txt.
- Data findings that shape the design are in `analysis-notes/README.md` (an index of notes 01+). Read it before making modelling decisions. Analysis scripts live in `analysis-notes/scripts/`, and generated outputs (slice meta for `score.py --meta`, per-page CSVs) in `analysis-notes/out/`.
- The plan is in `PLAN.md`. Evaluate with `uv run python -m eval.evaluate --pred P.json --set dev|bakeoff|fold:K`, which matches score.py exactly and adds slices. Unseen-supplier numbers come only from `fold:K`, using nothing learned from fold K.
- Put every analysis in `analysis-notes/` as a numbered markdown file: `NN-short-kebab-title.md` (`01-...`, `02-...`). Use the next free number, and never renumber existing notes. Add a row for each new note to the index table in `analysis-notes/README.md`.
- `scripts/statusline.*` is a Claude Code status-line helper and is not part of the assignment.
