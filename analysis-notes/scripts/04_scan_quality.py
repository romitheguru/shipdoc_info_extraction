"""Note 04: image-quality stats per page (all splits, including unlabelled test images).

    uv run python analysis-notes/scripts/04_scan_quality.py [--out analysis-notes/out/04_page_quality.csv]

Per page: skew angle (projection-profile search), sharpness (variance of Laplacian on text),
background noise (std of the paper), contrast (paper level minus ink level), JPEG quality
(from the quantisation table), and median text height in px (for the resolution budget, note 06).
"""
import argparse, csv, glob, os
from statistics import median, quantiles

import cv2
import numpy as np
from PIL import Image

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def skew(ink):
    """Angle (deg) that maximises the variance of the row-sum profile of the ink mask."""
    small = cv2.resize(ink, None, fx=0.5, fy=0.5, interpolation=cv2.INTER_AREA)
    h, w = small.shape
    c = (w / 2, h / 2)

    def score(a):
        m = cv2.getRotationMatrix2D(c, a, 1.0)
        r = cv2.warpAffine(small, m, (w, h), flags=cv2.INTER_NEAREST)
        return float(np.var(r.sum(1)))

    best = max(np.arange(-5, 5.01, 0.5), key=score)
    best = max(np.arange(best - 0.5, best + 0.51, 0.05), key=score)
    return round(-float(best), 2)


def jpeg_quality(path):
    """Rough IJG quality from the luma quantisation table (None for PNG)."""
    im = Image.open(path)
    q = getattr(im, "quantization", None)
    if not q:
        return None
    base = np.array([16, 11, 10, 16, 24, 40, 51, 61, 12, 12, 14, 19, 26, 58, 60, 55, 14, 13, 16, 24, 40, 57, 69, 56,
                     14, 17, 22, 29, 51, 87, 80, 62, 18, 22, 37, 56, 68, 109, 103, 77, 24, 35, 55, 64, 81, 104, 113, 92,
                     49, 64, 78, 87, 103, 121, 120, 101, 72, 92, 95, 98, 112, 100, 103, 99])
    s = np.mean(np.array(q[0], float)) / np.mean(base) * 100
    return round(200 - s if s <= 100 else 5000 / s) / 2 if s <= 100 else round(5000 / s)


def text_height(ink):
    n, _, st, _ = cv2.connectedComponentsWithStats(ink, connectivity=8)
    hs = [h for x, y, w, h, a in st[1:] if 6 <= h <= 40 and w <= 40 and a >= 15]
    return median(hs) if hs else None


def page_stats(path):
    g = cv2.imread(path, cv2.IMREAD_GRAYSCALE)
    _, otsu = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    ink = (otsu > 0).astype(np.uint8)
    paper = g[ink == 0]
    text = g[ink == 1]
    near_text = cv2.dilate(ink, np.ones((9, 9), np.uint8)) > 0
    lap = cv2.Laplacian(g, cv2.CV_64F)
    return {
        "skew_deg": skew(ink),
        "sharpness": round(float(lap[near_text].var()), 1),
        "paper_level": round(float(np.median(paper)), 1),
        "paper_noise": round(float(paper.std()), 2),
        "contrast": round(float(np.median(paper) - np.median(text)), 1),
        "jpeg_q": jpeg_quality(path),
        "text_h_px": text_height(ink),
        "ink_frac": round(float(ink.mean()), 4),
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=f"{ROOT}/analysis-notes/out/04_page_quality.csv")
    a = ap.parse_args()
    rows = []
    for split in ("train", "dev", "test"):
        for p in sorted(glob.glob(f"{ROOT}/data/{split}/images/*")):
            stem = os.path.basename(p)
            r = {"split": split, "page": stem, "scanned": p.endswith(".jpg")}
            r.update(page_stats(p))
            rows.append(r)
    os.makedirs(os.path.dirname(a.out), exist_ok=True)
    with open(a.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)

    def summ(vals):
        vals = sorted(v for v in vals if v is not None)
        if len(vals) < 4:
            return "n/a"
        q = quantiles(vals, n=20)
        return f"min {vals[0]:>7} p5 {q[0]:>8.2f} p50 {median(vals):>8.2f} p95 {q[-1]:>8.2f} max {vals[-1]:>7}"

    for split in ("train", "dev", "test"):
        for sc in (False, True):
            rs = [r for r in rows if r["split"] == split and r["scanned"] == sc]
            print(f"\n== {split} {'scanned' if sc else 'digital'} pages: {len(rs)}")
            for k in ("skew_deg", "sharpness", "paper_level", "paper_noise", "contrast", "jpeg_q", "text_h_px"):
                vals = [abs(r[k]) if k == "skew_deg" else r[k] for r in rs]
                print(f"  {k + (' (abs)' if k == 'skew_deg' else ''):<16} {summ(vals)}")


if __name__ == "__main__":
    main()
