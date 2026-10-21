"""Run PP-OCRv5 (PaddleOCR 3.x, CPU) on pages and cache tokens, boxes and confidences as JSON.

    uv run --group bakeoff python -m bakeoff.ocr_run --set bakeoff [--model server|mobile]

Cache: bakeoff/cache/ocr_<model>/<page stem>.json = {"texts": [...], "scores": [...], "boxes": [[x0,y0,x1,y1], ...]}
"""
import argparse, json, os, sys, time

from eval.data import ROOT, page_paths
from eval.evaluate import gold_set

CACHE = os.path.join(ROOT, "bakeoff", "cache")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="bakeoff")
    ap.add_argument("--model", default="server", choices=["server", "mobile"])
    a = ap.parse_args()
    from paddleocr import PaddleOCR
    ocr = PaddleOCR(text_detection_model_name=f"PP-OCRv5_{a.model}_det", text_recognition_model_name=f"PP-OCRv5_{a.model}_rec",
                    use_doc_orientation_classify=False, use_doc_unwarping=False, use_textline_orientation=False)
    out_dir = os.path.join(CACHE, f"ocr_{a.model}")
    os.makedirs(out_dir, exist_ok=True)
    pages = [p for d in gold_set(a.set) for p in page_paths(d)]
    t0 = time.time()
    for i, p in enumerate(pages):
        dst = os.path.join(out_dir, os.path.splitext(os.path.basename(p))[0] + ".json")
        if os.path.exists(dst):
            continue
        r = ocr.predict(p)[0]
        json.dump({"texts": list(r["rec_texts"]), "scores": [round(float(s), 4) for s in r["rec_scores"]],
                   "boxes": [[int(v) for v in b] for b in r["rec_boxes"]]}, open(dst, "w"))
        print(f"{i + 1}/{len(pages)} {os.path.basename(p)} {time.time() - t0:.0f}s", file=sys.stderr, flush=True)


if __name__ == "__main__":
    main()
