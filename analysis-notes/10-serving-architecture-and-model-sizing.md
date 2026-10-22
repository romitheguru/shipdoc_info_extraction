# 10: Serving architecture and model sizing

The bake-off (note 09) chose a zero-shot VLM, but it ran one document at a time on a Mac. This note sets the design targets for a real deployment and the shortlist for a model size sweep. Numbers marked *est.* are back-of-envelope estimates to be replaced by measurements in step 2b.

## Assumptions (the brief gives no volume or latency target)
| | Assumption | Why it matters |
|---|---|---|
| Volume | 10k docs/day, 5× peaks → ~0.6 docs/s at peak | Throughput, not single-request latency, sets the hardware cost |
| Latency | Seconds per doc, not minutes | Back-office pipeline, not interactive |
| Hardware | One 24 GB GPU (brief), **weights ≤ ~12 GB** (my rule) | The other half holds KV cache, so many docs run concurrently. A model that only *fits* 24 GB serves one doc at a time |

## Memory budget (*est.*)
| Model | Weights |
|---|---|
| Qwen3-VL-8B BF16 | ~17 GB (over budget; accuracy reference only) |
| Qwen3-VL-8B FP8 | ~9 GB |
| Qwen3-VL-8B 4-bit (AWQ) | ~6 GB |
| Qwen3-VL-4B BF16 | ~9 GB |
| Qwen3-VL-2B BF16 | ~4.5 GB |
| PaddleOCR-VL (~0.9B) | ~2 GB |

- **KV cache:** ~0.14 MB/token for Qwen3-VL-4B and 8B alike (36 layers × 8 KV heads × 128 dim × K+V × 2 bytes). A doc is 5k–12k tokens (note 06), so ~0.7–1.8 GB in flight. With ~10 GB free that is ~5–14 concurrent docs.
- **Smaller isn't free:** 4B and 8B have the same KV cost per token, so going smaller saves weights and compute, not cache.

## Decisions
1. **Serve with vLLM.** It provides continuous batching, prefix caching (the long instruction prompt is the same for every doc) and JSON-schema-constrained decoding (output is always valid JSON). This replaces the one-at-a-time MLX loop.
2. **One extractor, specialised by prompt and schema, not by weights.** A separate invoice model and waybill model would halve the concurrency budget and add operational overhead. Classification is already 100% (note 09), and the real difference between types is *what to extract*, which a per-type prompt plus JSON schema handles.
3. **Add a second, different reader as a verifier.** A document parser (PaddleOCR-VL first) runs alongside the extractor. Where the two disagree on a value, it gets a needs-review flag. Even classic OCR caught 14 of 24 part-number errors this way (note 09); a modern parser should do better. The parser is never allowed to *overwrite* the extractor's value unless step 2b shows that improves accuracy.
4. **Cascade for latency (optional, only if measured to help).** Easy docs (waybills, digital pages where both readers agree) can be finished by a small model. Only invoices and scans escalate to the larger one.
5. **Pick the smallest extractor within ~1 OVERALL point of the best**, with false fills not worse. Report docs/s, p50/p95 latency and peak VRAM next to accuracy.

## Shortlist for step 2b (all open-weight, all within the weight budget)
| Role | Candidates |
|---|---|
| Extractor | Qwen3-VL-8B FP8, Qwen3-VL-8B AWQ-4bit, Qwen3-VL-4B BF16 (8B BF16 as an accuracy reference) |
| Router / waybill fast path | Qwen3-VL-2B |
| Verifier (parser) | PaddleOCR-VL; dots.ocr as a fallback if PaddleOCR-VL won't serve |

## Update: everything runs locally
All processing, experiments and runs were done locally on my MacBook Pro (M5 Pro, 24 GB unified memory) with MLX; the data is small enough for that. The consequences:
- **The size sweep runs on MLX quantisations** (8-bit and 4-bit) instead of FP8/AWQ, one model at a time.
- **vLLM (decision 1) becomes a production recommendation** in the report, not something measured. Throughput is reported as measured on the Mac.
- **A `transformers` backend is kept** so graders on NVIDIA or CPU can reproduce.
- **The ≤ ~12 GB weight budget still applies**, now because the OS and other apps share the 24 GB.

Leaderboard results for document parsers (e.g. OmniDocBench) measure parsing, not field extraction, so only my own bake-off decides. The main risk to watch is that 4-bit quantisation increases O/0 and I/1 swaps on scans.
