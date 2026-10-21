"""Stack horizontal bands of page images into one PNG for visual inspection.

    uv run python analysis-notes/scripts/montage.py OUT.png train_0003_p1:0:1050 dev_0010_p2:0:300 [--scale 0.8]

Each spec is <page stem>:<y0>:<y1>; the split and extension are found automatically.
Each band is labelled with its page stem.
"""
import argparse, glob, os

import cv2
import numpy as np

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")


def find(stem):
    hits = glob.glob(f"{ROOT}/data/*/images/{stem}.*")
    if not hits:
        raise SystemExit(f"no image for {stem}")
    return hits[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("specs", nargs="+")
    ap.add_argument("--scale", type=float, default=1.0)
    a = ap.parse_args()
    bands = []
    for spec in a.specs:
        stem, y0, y1 = spec.split(":")
        img = cv2.imread(find(stem), cv2.IMREAD_GRAYSCALE)
        band = img[int(y0):int(y1)]
        tag = np.full((28, band.shape[1]), 255, np.uint8)
        cv2.putText(tag, stem, (6, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        bands += [np.full((6, band.shape[1]), 0, np.uint8), tag, band]
    out = np.vstack(bands)
    if a.scale != 1.0:
        out = cv2.resize(out, None, fx=a.scale, fy=a.scale, interpolation=cv2.INTER_AREA)
    cv2.imwrite(a.out, out)


if __name__ == "__main__":
    main()
