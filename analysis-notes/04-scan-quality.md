# 04: How bad are the scans?

Script: `analysis-notes/scripts/04_scan_quality.py` covers all 951 pages, including the unlabelled test images (statistics only, nothing labelled). Per-page output is in `analysis-notes/out/04_page_quality.csv`.

## TL;DR
- **Scans are mild.** Rotation is at most 1.6° (median ~0.8°), never 90° or upside-down. JPEG quality is 45–75. Even the blurriest 5% (about 35× softer than digital) are readable by eye at native resolution: I checked part numbers on the 3 worst pages.
- **Test scans match train and dev statistically** on every measure: same skew range, same JPEG quality range, and similar blur, contrast and noise. Test's tail is slightly worse (lowest contrast 65 vs 73, max noise 14.6 vs 12.1). No new kind of degradation shows up.
- **Every page is 1240×1754 (A4 at 150 dpi). Median glyph height is about 11 px**, with 9 px at the 5th percentile. That is small, so downscaling is the real risk, not noise.
- **Decision: no heavy preprocessing.** Deskew is optional and cheap; it's worth an A/B in note 09 but not required. Keep native resolution.

## Numbers (scanned pages; digital pages for contrast)
| | train scan (200 pp) | dev scan (56) | test scan (132) | digital (all) |
|---|---|---|---|---|
| \|skew\| p50 / p95 / max (°) | 0.70 / 1.50 / 1.6 | 0.88 / 1.46 / 1.55 | 0.80 / 1.45 / 1.6 | ≤ 0.1 (none) |
| sharpness p5 / p50 (var. of Laplacian near text) | 759 / 6,396 | 1,174 / 7,589 | 741 / 5,755 | ~26k / ~34k |
| paper grey level p5 / p50 | 223 / 247 | 228 / 249 | 226 / 246 | 255 |
| contrast (paper − ink) p5 / p50 | 82 / 142 | 86 / 150 | 76 / 140 | 216 / 255 |
| JPEG quality min / p50 / max | 45 / 59 / 75 | 45 / 57 / 73 | 45 / 59 / 75 | PNG |
| glyph height p50 (px) | 12 | 12 | 12 | 11 |

- Scanning is per document: all of a doc's pages are scans, or none are.
- The skew estimate comes from a projection-profile search (step 0.05°). Digital pages read as 0.05–0.1°, which is just the step size.

## Implications
1. **Resolution matters more than denoising.** The glyphs are about 11 px tall. At Qwen2.5-VL's native page size (one token per 28×28 px), each token covers about 2.5 glyph heights; see note 06 for the budget trade-off.
2. **Scan errors will be character-level** (O/0, I/1, 5/S, 8/B in part numbers), not missing text. Note 07 shows one such error per invoice costs about 19 OVERALL points, so the scanned slice is where row F1 will drop.
3. **Simple augmentation is enough if we fine-tune:** ±2° rotation, JPEG quality 45–75, Gaussian blur and gray paper. That covers the test distribution.
