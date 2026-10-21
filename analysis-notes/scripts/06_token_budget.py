"""Note 06: input (image) and output (JSON) token budget per document.

    uv run python analysis-notes/scripts/06_token_budget.py

Image tokens use Qwen2.5-VL's smart_resize rule (14 px patches merged 2x2 -> one token per
28x28 px; sides rounded to multiples of 28). Output tokens use the real Qwen2.5-VL tokenizer on
the gold JSON in two serialisations: full schema JSON and a compact row format.
"""
import glob, json, math, os
from statistics import median, quantiles

from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
W, H = 1240, 1754                                        # every page, all splits (note 04)


def qwen_tokens(w, h, factor=28):
    hb, wb = round(h / factor) * factor, round(w / factor) * factor
    return (hb // factor) * (wb // factor), (wb, hb)


def compact(d):
    """One header line + one pipe-separated line per row; nulls as empty fields."""
    h = "|".join("" if v is None else v for v in d["header"].values())
    rows = ["|".join("" if v is None else v for v in r.values()) for r in d["line_items"]]
    return d["doc_type"] + "\n" + h + "\n" + "\n".join(rows)


def pct(vals):
    q = quantiles(vals, n=20)
    return f"p50 {median(vals):>6.0f}  p95 {q[-1]:>6.0f}  max {max(vals):>6.0f}"


def main():
    tok = Tokenizer.from_file(hf_hub_download("Qwen/Qwen2.5-VL-7B-Instruct", "tokenizer.json"))
    print("Image tokens per page (Qwen2.5-VL), by input scale:")
    for s in (1.0, 0.85, 0.75, 0.6, 0.5):
        n, (wb, hb) = qwen_tokens(W * s, H * s)
        print(f"  scale {s:4.2f}  {wb}x{hb}  -> {n:5d} tokens/page   median text height ~{11 * s:4.1f} px")

    docs = [json.load(open(f)) for s in ("train", "dev") for f in sorted(glob.glob(f"{ROOT}/data/{s}/labels/*.json"))]
    full = [len(tok.encode(json.dumps({k: d[k] for k in ("doc_type", "header", "line_items")})).ids) for d in docs]
    comp = [len(tok.encode(compact(d)).ids) for d in docs]
    pages = [len(d["pages"]) for d in docs]
    print(f"\nOutput tokens per doc, full JSON:    {pct(full)}")
    print(f"Output tokens per doc, compact rows: {pct(comp)}")
    worst = max(docs, key=lambda d: len(d["line_items"]))
    print(f"  largest doc {worst['doc_id']}: {len(worst['line_items'])} rows, "
          f"{len(tok.encode(json.dumps(worst)).ids)} JSON tokens")
    per_row = [len(tok.encode(json.dumps(r)).ids) for d in docs for r in d["line_items"]]
    print(f"  tokens per row (JSON): median {median(per_row)}  max {max(per_row)}")
    pn = [r["supplier_part_number"] for d in docs for r in d["line_items"]]
    pn_t = [len(tok.encode(p).ids) for p in pn]
    print(f"  tokens per supplier part number: median {median(pn_t)}  max {max(pn_t)}  "
          f"(e.g. {pn[0]!r} -> {tok.encode(pn[0]).tokens})")

    per_page, _ = qwen_tokens(W, H)
    ctx = [p * per_page + 300 + f for p, f in zip(pages, full)]   # ~300 tokens of prompt
    print(f"\nWhole-document context at native res (pages*{per_page} + prompt + JSON): {pct(ctx)}")
    print(f"Pages per doc: {dict(sorted({p: pages.count(p) for p in set(pages)}.items()))}")
    tst = {}
    for p in glob.glob(f"{ROOT}/data/test/images/*"):
        tst.setdefault(os.path.basename(p).rsplit("_p", 1)[0], 0)
        tst[os.path.basename(p).rsplit("_p", 1)[0]] += 1
    tp = sum(tst.values())
    print(f"Test set: {len(tst)} docs, {tp} pages -> {tp * per_page:,} image tokens; "
          f"output ~{len(tst) * median(full):,.0f} tokens at median JSON size")


if __name__ == "__main__":
    main()
