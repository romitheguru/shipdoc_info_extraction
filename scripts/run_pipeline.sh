#!/bin/zsh
# Frozen pipeline (prompt v1, 8B 4-bit): test first, then dev; verifier pages after each.
cd "$(dirname $0)/.."
M=mlx-community/Qwen3-VL-8B-Instruct-4bit
V=bakeoff/cache/ocr_paddleocr_vl
run() { uv run --no-sync --group bakeoff python -m "$@"; }
run shipdoc.predict --split test --model $M --out runs/test_noflags.json > runs/test.log 2>&1; echo "test extract $? $(date)"
run bakeoff.ocrvl_run --split test > runs/ocr_test.log 2>&1; echo "ocr test $? $(date)"
run shipdoc.predict --split test --model $M --ocr-cache $V --out test_predictions.json >> runs/test.log 2>&1; echo "test final $? $(date)"
run shipdoc.predict --split dev --model $M --out runs/dev_noflags.json > runs/dev.log 2>&1; echo "dev extract $? $(date)"
run bakeoff.ocrvl_run --set dev > runs/ocr_dev.log 2>&1; echo "ocr dev $? $(date)"
run shipdoc.predict --split dev --model $M --ocr-cache $V --out runs/dev.json >> runs/dev.log 2>&1; echo "dev final $? $(date)"
