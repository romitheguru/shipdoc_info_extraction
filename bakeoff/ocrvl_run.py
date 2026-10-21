"""PLAN.md A3: PaddleOCR-VL (MLX 8-bit) as an independent second reader, whole page at a time.

    uv run --group bakeoff python -m bakeoff.ocrvl_run --set bakeoff
    uv run --group bakeoff python -m bakeoff.ocrvl_run --split test     # unlabelled split

Writes the same per-page cache format as bakeoff/ocr_run.py (texts, scores), so bakeoff.ocr_recall and
shipdoc.flags.ocr_text work unchanged: bakeoff/cache/ocr_paddleocr_vl/<page stem>.json. PaddleOCR-VL gives
no per-line confidence, so every score is 1.0. Table output (Markdown pipes or HTML cells) is split into
one text per cell. The raw model text and timing are kept alongside.
"""
import argparse, json, os, re, sys, time

from bakeoff.ocr_run import CACHE
from eval.data import page_paths
from eval.evaluate import gold_set
from shipdoc.pages import documents

MODEL = "mlx-community/PaddleOCR-VL-8bit"
PROMPT = "OCR:"


def cells(text):
    """Model text -> list of non-empty pieces: one per line, table cell (| or <td>) or tag-separated run."""
    text = re.sub(r"<[^>]+>", "\n", text)
    return [p.strip() for line in text.splitlines() for p in line.split("|") if p.strip() and not re.fullmatch(r"[-:\s]+", p)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="bakeoff")
    ap.add_argument("--split", help="every page of data/<split>/images instead of a labelled --set")
    ap.add_argument("--max-tokens", type=int, default=4096)
    a = ap.parse_args()
    out_dir = os.path.join(CACHE, "ocr_paddleocr_vl")
    os.makedirs(out_dir, exist_ok=True)
    if a.split:
        pages = [p for d, ps in sorted(documents(a.split).items()) for p in ps]
    else:
        pages = [p for d in sorted(gold_set(a.set)) for p in page_paths(d)]
    model = None
    t0 = time.time()
    for i, p in enumerate(pages):
        dst = os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + ".json")
        if os.path.exists(dst):
            continue
        if model is None:
            import mlx.core as mx
            from mlx_vlm import generate, load
            from mlx_vlm.prompt_utils import apply_chat_template
            from mlx_vlm.utils import load_config
            model, processor = load(MODEL)
            config = load_config(MODEL)
            prompt = apply_chat_template(processor, config, PROMPT, num_images=1)
        mx.reset_peak_memory()
        t = time.time()
        r = generate(model, processor, prompt, image=[p], max_tokens=a.max_tokens, temperature=0.0, verbose=False)
        texts = cells(r.text)
        json.dump({"texts": texts, "scores": [1.0] * len(texts), "raw": r.text, "secs": round(time.time() - t, 1),
                   "generation_tokens": r.generation_tokens, "finish_reason": r.finish_reason,
                   "peak_gb": round(mx.get_peak_memory() / 1e9, 2)}, open(dst, "w"))
        print(f"{i + 1}/{len(pages)} {os.path.basename(p)} {time.time() - t:.0f}s {len(texts)} pieces "
              f"(total {time.time() - t0:.0f}s)", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
