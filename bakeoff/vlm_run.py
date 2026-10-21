"""Candidate B: zero-shot VLM on whole documents (all pages in one call), via MLX on the Mac.

    uv run --group bakeoff python -m bakeoff.vlm_run --set bakeoff --model mlx-community/Qwen3-VL-8B-Instruct-8bit

Raw model output is cached per doc in bakeoff/cache/vlm_<tag>/; predictions go to
bakeoff/preds/vlm_<tag>_<set>.json in the submission format. The prompt is generic: it names
no supplier, prefix or layout position (PLAN.md).
"""
import argparse, json, os, re, sys, time

from bakeoff.ocr_run import CACHE
from bakeoff.postprocess import to_submission
from eval.data import ROOT, page_paths
from eval.evaluate import gold_set

PROMPT = """You are reading the page images of ONE shipping document (all its pages, in order).
It is either a commercial invoice (titles vary: Invoice, Commercial Invoice, Tax Invoice, Packing List)
or an air waybill (title "Air Waybill").

Return ONLY a JSON object, no prose, no markdown:
{"doc_type": "invoice" | "waybill",
 "header": {...},
 "line_items": [...]}

For an invoice, header keys:
  invoice_number, invoice_date_raw (exactly as printed), supplier_name (the seller, from the letterhead),
  buyer_name (Sold To / Bill To / Buyer), ship_to_name (Ship To / Consignee / Deliver To),
  currency (3-letter code), total_amount (the invoice total amount, not the total quantity),
  awb_number (air waybill / AWB number referenced on the invoice).
  line_items: one object per table row, on ALL pages, in order, including rows that repeat a part number:
  {"supplier_part_number": seller's/manufacturer's own part number,
   "customer_part_number": the buyer's part number if the table has such a column, else null,
   "purchase_order": the PO / order number for the row if the table has such a column, else null,
   "quantity": quantity shipped}
  Column headers differ between sellers. Decide by meaning, from the seller's point of view:
  "Our Part No." / "Mfr Part #" / "Item Code" / "Product" = supplier part number;
  "Your Part No." / "Customer P/N" / "Cust. Part" = customer part number;
  "Your Order" / "Customer PO" / "PO No." = purchase order.
  Pages after the first may continue the table without repeating the header row: keep the same columns.
For a waybill, header keys:
  carrier (the company named in the title), mawb, hawb, origin_airport, destination_airport (3-letter IATA code only),
  shipper_name, consignee_name, pieces, gross_weight_kg. line_items: [].

Rules:
- Copy every value exactly as printed, character by character (keep hyphens, slashes, letter O vs digit 0).
- Read each header value ONLY at its labelled position on the first page. Do not take it from anywhere else
  (e.g. a "continued" banner on a later page).
- If a label is absent, or its value is blacked out, scribbled over, smudged or cut off, output null,
  even if a few characters are still visible. Never guess or complete a value.
- Numbers as printed digits (thousands separators allowed)."""


def run(model, processor, config, pages, max_tokens):
    from mlx_vlm import generate
    from mlx_vlm.prompt_utils import apply_chat_template
    prompt = apply_chat_template(processor, config, PROMPT, num_images=len(pages))
    import mlx.core as mx
    mx.reset_peak_memory()
    r = generate(model, processor, prompt, image=pages, max_tokens=max_tokens, temperature=0.0, verbose=False)
    if isinstance(r, str):
        return r, {}
    return r.text, {"prompt_tokens": r.prompt_tokens, "generation_tokens": r.generation_tokens,
                    "peak_gb": round(mx.get_peak_memory() / 1e9, 2), "finish_reason": r.finish_reason}


def parse(text):
    m = re.search(r"\{.*\}", text, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="bakeoff")
    ap.add_argument("--model", default="mlx-community/Qwen3-VL-8B-Instruct-8bit")
    ap.add_argument("--max-tokens", type=int, default=3000)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--tag", help="cache/preds name; defaults to the model name (use a new tag to re-time a model)")
    a = ap.parse_args()
    tag = a.tag or a.model.split("/")[-1]
    cache = os.path.join(CACHE, f"vlm_{tag}")
    os.makedirs(cache, exist_ok=True)
    docs = sorted(gold_set(a.set))[: a.limit]
    model = processor = config = None
    t0 = time.time()
    for i, d in enumerate(docs):
        dst = os.path.join(cache, d + ".json")
        if os.path.exists(dst):
            continue
        if model is None:
            from mlx_vlm import load
            from mlx_vlm.utils import load_config
            model, processor = load(a.model)
            config = load_config(a.model)
        t = time.time()
        text, stats = run(model, processor, config, page_paths(d), a.max_tokens)
        json.dump({"raw": text, "secs": round(time.time() - t, 1), **stats}, open(dst, "w"))
        print(f"{i + 1}/{len(docs)} {d} {time.time() - t:.0f}s peak {stats.get('peak_gb')} GB (total {time.time() - t0:.0f}s)",
              file=sys.stderr, flush=True)

    preds, bad = {}, []
    for d in docs:
        out = parse(json.load(open(os.path.join(cache, d + ".json")))["raw"])
        if out is None:
            bad.append(d)
            continue
        preds[d] = to_submission(out)
    os.makedirs(os.path.join(ROOT, "bakeoff", "preds"), exist_ok=True)
    path = os.path.join(ROOT, "bakeoff", "preds", f"vlm_{tag}_{a.set}.json")
    json.dump(preds, open(path, "w"), indent=1)
    print(f"wrote {path}: {len(preds)} docs, unparseable {bad}")


if __name__ == "__main__":
    main()
