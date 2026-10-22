# 06: Token, memory and runtime budget

Script: `analysis-notes/scripts/06_token_budget.py`. It uses the real Qwen2.5-VL-7B tokenizer and config from the HF Hub, and Qwen2.5-VL's resize rule (14 px patches merged 2×2, so one token per 28×28 px).

## TL;DR
- **One page at native resolution costs 2,772 image tokens.** A whole document costs 3.5k tokens at the median and 10.5k at most (3 pages plus a 30-row JSON answer). This fits easily in Qwen2.5-VL's context.
- **Output is the slow part:** 379 JSON tokens at the median and 1.9k at most. A compact row format nearly halves that (202 median, 1.2k max).
- **A 7B VLM fits the 24 GB inference limit at native resolution:** about 16.6 GB of bf16 weights plus about 0.6 GB of KV cache at 10.5k tokens. **Fine-tuning at native resolution does not fit in 24 GB without QLoRA** and needs a larger GPU (an estimate; see below).
- **Downscaling is the main lever, but the text is already small.** At 0.75× scale a page costs 1,551 tokens, but glyphs shrink to about 8 px. Whether that still reads O vs 0 is an empirical question for note 09, not something to assume.

## Image tokens per page (Qwen2.5-VL)
| scale | resized | tokens/page | median glyph height |
|---|---|---|---|
| 1.00 | 1232×1764 | 2,772 | ~11 px |
| 0.85 | 1064×1484 | 2,014 | ~9 px |
| 0.75 | 924×1316 | 1,551 | ~8 px |
| 0.60 | 756×1064 | 1,026 | ~7 px |
| 0.50 | 616×868 | 682 | ~5.5 px |

Docs have 1 page (348), 2 pages (133) or 3 pages (19). The test set is 280 pages, which is about **776k image tokens** at native resolution.

## Output tokens per doc
| format | p50 | p95 | max |
|---|---|---|---|
| full schema JSON | 379 | 1,586 | 1,902 |
| compact (`a\|b\|c` per row) | 202 | 917 | 1,217 |

- A row costs about 49 JSON tokens and a part number about 9.
- Digits tokenise one per token, which suits exact copying.
- Compact output roughly halves decoding time. It needs a parser, but no information is lost because the field order is fixed by the schema.

## Memory (Qwen2.5-VL-7B: 8.3B params, 28 layers, 4 KV heads × 128 dims)
- **Inference, bf16:**
  - weights ≈ 16.6 GB
  - KV cache ≈ 57 KB/token, so ≈ 0.6 GB at 10.5k tokens
  - vision-encoder activations for a 2.8k-token page fit comfortably

  This fits the 24 GB inference limit with headroom. A 4-bit build (~5–6 GB) would also run locally on this Mac (24 GB unified memory), which is useful for zero-shot exploration in note 09.
- **Training (estimate, to verify):**
  - LoRA on a bf16 base at 4–10k sequence length with gradient checkpointing probably needs **40–80 GB** (A100 or H100 class).
  - QLoRA brings that to roughly **20–24 GB** (one 24 GB card), at lower speed.
  - Training data is 400 train docs ≈ 1.4M image tokens per epoch: small. 2–3 epochs is hours, not days, on one GPU.

## Runtime (rough estimates, to measure in 09)
- At about 30–50 tokens/s of decoding for a 7B model on one 24 GB GPU, a median doc takes about 10 s and a 30-row doc 40–60 s.
- The whole test set takes **30–60 min single-stream**, and several times less with batched serving (e.g. vLLM). That's acceptable.
- On this Mac with a 4-bit MLX build, expect a few minutes per 30-row doc. That's fine for spot checks but slow for full dev sweeps.

## Implications
1. **Default to native resolution with the whole document in one context.** It fits, and the column semantics carry across pages (note 03).
2. **Use the compact output format** if decode time becomes the bottleneck. Measure the accuracy impact in 09.
3. **Model-size ceiling:** 7–8B VLMs in bf16 are the largest that run comfortably in 24 GB at this context size. Larger models (30B+) would need 4-bit quantisation, which hurts exact character copying. Note 08's OCR check shows whether a smaller pipeline is viable instead.
4. **Training compute is the open question.** Fine-tuning at native resolution doesn't fit the local 24 GB machine without QLoRA. Zero-shot (note 09) decides whether it's needed at all.
