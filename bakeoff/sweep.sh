#!/usr/bin/env bash
# Step 2b size sweep (PLAN.md A2): one model at a time on the 40-doc bake-off set, so memory is never shared.
# The 8B 8-bit baseline is re-run under a new tag to get clean timings (note 09's were inflated by a parallel OCR job).
set -euo pipefail
cd "$(dirname "$0")/.."
run() { uv run --group bakeoff python -m bakeoff.vlm_run --set bakeoff "$@"; }
run --model mlx-community/Qwen3-VL-2B-Instruct-8bit
run --model mlx-community/Qwen3-VL-4B-Instruct-8bit
run --model mlx-community/Qwen3-VL-8B-Instruct-4bit
run --model mlx-community/Qwen3-VL-8B-Instruct-8bit --tag Qwen3-VL-8B-Instruct-8bit-retime
