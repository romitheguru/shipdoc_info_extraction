# 07: What each kind of error costs under the official scorer

Script: `analysis-notes/scripts/07_score_sensitivity.py`. It takes the 500 train+dev gold docs, applies one simulated failure at a time, and scores them with `score.py`'s own functions. It also writes the slice meta files `analysis-notes/out/meta_{train,dev}.json` for `score.py --meta`.

## Results
| Scenario (applied to every doc it fits) | OVERALL | Δ | header acc | row F1 | docs exact |
|---|---|---|---|---|---|
| perfect | 100.00 | – | 100 | 100 | 100 |
| right doc_type only (all null, no rows) | 1.87 | −98.1 | 4.7 | 0 | 0 |
| perfect header, no rows | 44.00 | −56.0 | 100 | 0 | 20.0 |
| perfect rows, header all null | 41.87 | −58.1 | 4.7 | 100 | 0 |
| **PO hallucinated where there is no PO column** | 77.30 | **−22.7** | 100 | 60.3 | 65.8 |
| **1 lookalike-char error in 1 row per invoice** | 80.75 | **−19.3** | 100 | 91.9 | 20.0 |
| cust PN ↔ PO columns swapped (docs with both) | 83.37 | −16.6 | 100 | 69.7 | 77.4 |
| page-2+ rows dropped (approx.) | 87.48 | −12.5 | 100 | 83.6 | 70.2 |
| `5,000` read as 5.000 in 10% of 4-digit quantities | 90.25 | −9.8 | 100 | 93.8 | 63.6 |
| lookalike-char error in 5% of rows | 90.81 | −9.2 | 100 | 94.5 | 65.0 |
| every null header field guessed (false fill) | 90.93 | −9.1 | 95.3 | 100 | 64.0 |
| ship_to copied from Sold To | 92.04 | −8.0 | 96.1 | 100 | 68.0 |
| airport as `AMS AMSTERDAM` | 94.05 | −6.0 | 95.1 | 100 | 80.0 |
| repeated part numbers de-duplicated | 94.92 | −5.1 | 100 | 95.5 | 83.6 |
| ambiguous dates set to null (abstain) | 95.67 | −4.3 | 97.9 | 100 | 82.6 |
| ambiguous dates all read the wrong way (DD/MM ↔ MM/DD) | 95.97 | −4.0 | 98.0 | 100 | 83.8 |

## What this shows
1. **Row exactness dominates.** One wrong character in one row of each invoice costs 19 points, more than wiping out every date or every null. Row F1 barely moves, but the "fully correct" term collapses: docs exact falls from 100% to 20%, because only the waybills survive. Ambiguous dates swapped give the same reading as the original when day equals month, which is why abstaining costs slightly more than guessing wrong. **Part-number character accuracy is the number to optimise and measure.**
2. **Column-semantics errors are the costliest structural mistake.** Filling a PO where there's no PO column, or swapping customer PN and PO, invalidates *every* row of the affected docs (−17 to −23). Note 03 shows these are exactly the cases unseen layouts will stress.
3. **Nulling a legible value scores the same as a wrong value.** Abstaining on ambiguous dates (−4.3) is *slightly worse* than guessing wrong every time (−4.0), and a 50/50 guess would cost only about −2. **For fields whose gold is not null, null never helps the score.** Use null only for "illegible or absent". For uncertainty, give the best guess and **raise a review flag**, which is the uncertainty signal the brief rewards.
4. **False fills are cheap in OVERALL but expensive in perception.** Guessing every null field costs 9 points, but the false-fill rate jumps to 100%, and the graders single that metric out. The null policy from note 05 matters more than its score weight suggests.
5. **Small formatting slips are worth handling deterministically:**
   - airport city: −6
   - ship_to copied from the buyer: −8
   - thousands separator misread as a decimal: −10 at 10%

   These are cheap post-processing or prompt fixes, not modelling problems.
6. **Waybills cushion the score.** Their line-item term reuses header accuracy, so "perfect header, no rows" still scores 44. Waybills are about 20% of docs and the easiest part, so get them to ~100% early.

## Slice meta (for `score.py --meta`)
| tag | train | dev |
|---|---|---|
| scanned | 150 | 43 |
| multi_page | 124 | 28 |
| repeated_parts | 65 | 17 |
| illegible (note 05 definition) | 40 | 8 |
| waybill | 77 | 23 |

There is no `unseen` tag yet. It needs the leave-supplier-out split, which comes next.
