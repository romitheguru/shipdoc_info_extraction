# 12: Final configuration (B3) and dev results

Code: `shipdoc/` (pipeline), `scripts/run_pipeline.sh` (the frozen run), `eval/evaluate.py` and `eval/flags.py` (scoring).
Bake-off numbers are on the 40-doc set from note 08; the Mac setup is the one from note 11.

## B3: column-role prompt, then the freeze
| Run (bake-off, 40 docs) | OVERALL | row F1 | docs exact | false fills | s/doc p50 | output tokens p50 |
|---|---|---|---|---|---|---|
| bake-off prompt, 8B 8-bit (note 09) | 89.35 | 87.1 | 72.5% | 0/15 | 16.4 | 409 |
| v1 column roles, 8B 8-bit, before the fixes | 82.0 | | | | | |
| v1 + fixes, 8B 8-bit | 90.27 | 92.2 | 67.5% | 1/15 | 30.6 | 757 |
| **v1 + fixes, 8B 4-bit (final)** | **90.99** | **92.5** | **70.0%** | **0/15** | **19.0** | 611 |
| v2 (role-keyed rows, compact JSON), 8B 8-bit | stopped at 16/40: ~38 s/doc, slower than v1 | | | | | |

**v1 prompt** (`shipdoc/prompts.py`): the model names each column's role (supplier/customer part number, PO,
quantity, other) from the seller's point of view before it writes the rows.

**Fixes found on the v1 errors** (all generic; none came from a fold-4 doc):
- **Lone customer column → supplier.** If no column was labelled supplier and exactly one was labelled customer,
  that column is the seller's. "Mfr Part #" was labelled customer on 3 docs.
- **Buyer-word swap.** If the supplier column's header has a buyer word (your, customer, cust, buyer, client) and the
  customer column's header doesn't, the two roles swap (dev_0032).
- **Integer-aware numbers.** European thousands like `2.500` in a quantity column are read as 2500.

**The freeze.** Prompt v2 was meant to cut output tokens (compact JSON) and stop invented values on scribbled dates
(the one 8-bit false fill, dev_0068). It ran slower than v1 (~38 s/doc), so it was stopped for time.
**8B 4-bit with v1 + fixes** was frozen instead. It is the best run measured, with 0 false fills, and it is 1.6× faster
than 8-bit. This reverses note 11's provisional 8-bit choice. The `PO` → `P0` misread that argued for 8-bit happens
with **both** widths under the v1 prompt (9 of 20 rows of dev_0033), so it no longer separates them. The v2 prompt is
kept for reference in `out/12_prompts_v2_not_used.py`.

**Column repairs as flags.** On 4-bit, the "repaired" flag fired 38 times and was right once (2.6% precision): the
repairs fix values rather than mark doubtful ones. They are listed in the flags file as informational, and the
review-flag metrics below are reported with and without them.

## Dev results (100 docs, frozen config)
{{DEV}}

## Throughput (C3)
{{THROUGHPUT}}
