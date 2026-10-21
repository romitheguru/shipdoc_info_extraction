"""End-to-end prediction: page images -> submission JSON + review flags.

    uv run --group bakeoff python -m shipdoc.predict --split dev --out runs/dev.json
    uv run --group bakeoff python -m shipdoc.predict --split dev --ids eval/bakeoff.json --out runs/bakeoff.json
    uv run --group bakeoff python -m shipdoc.predict --split test --out test_predictions.json
    uv run --group hf python -m shipdoc.predict --backend hf --split test --out test_predictions.json   # no Mac

Per doc: classify page 1 -> extract with that type's prompt -> assemble (invoice column roles) ->
normalise. Raw model outputs are cached in runs/cache/<backend>-<model>-<prompt hash>/<doc_id>.json, so a run
resumes after interruption and a prompt change starts a fresh cache. `--backend stub` needs no model
(every value null) and checks the plumbing. The output is validated against schema.json before writing.
"""
import argparse, hashlib, json, os, sys, time

from shipdoc import prompts
from shipdoc.extract import assemble
from shipdoc.flags import not_in_ocr, ocr_text
from shipdoc.pages import ROOT, documents
from shipdoc.postprocess import normalise
from shipdoc.schema import errors

MAX_TOKENS = {"classify": 5, "invoice": 4096, "waybill": 600}
PROMPT_HASH = hashlib.sha1((prompts.CLASSIFY + prompts.INVOICE + prompts.WAYBILL).encode()).hexdigest()[:8]


class Stub:
    name = "stub"

    def generate(self, prompt, images, max_tokens):
        return ("invoice" if prompt == prompts.CLASSIFY else "{}"), {}


def make_backend(name, model):
    if name == "stub":
        return Stub()
    from shipdoc.backends import BACKENDS
    return BACKENDS[name](model)


def extract_doc(backend, pages):
    """Model calls for one doc -> cache record."""
    label, s1 = backend.generate(prompts.CLASSIFY, pages[:1], MAX_TOKENS["classify"])
    doc_type = "waybill" if "waybill" in label.lower() else "invoice"
    text, s2 = backend.generate(prompts.INVOICE if doc_type == "invoice" else prompts.WAYBILL, pages, MAX_TOKENS[doc_type])
    return {"doc_type": doc_type, "classify_raw": label, "raw": text, "classify_stats": s1, "stats": s2}


def to_prediction(rec, ocr=None):
    """Cache record (+ the doc's OCR text for the verifier) -> (submission doc, review flags)."""
    raw, flags = assemble(rec["doc_type"], rec["raw"])
    # column repairs fix values rather than mark doubt (2.6% precision on the bake-off, note 12): not review flags
    flags = {k: v for k, v in flags.items() if not v.startswith("repaired")}
    doc, more = normalise(raw)
    if rec.get("stats", {}).get("finish_reason") == "length":
        flags["doc"] = "output truncated at max_tokens"
    flags.update(more)
    if ocr is not None:
        flags.update(not_in_ocr(doc, ocr, raw["header"].get("invoice_date_raw")))
    return doc, flags


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", required=True, help="data/<split>/images, e.g. dev or test")
    ap.add_argument("--out", required=True)
    ap.add_argument("--backend", choices=["mlx", "hf", "stub"], default="mlx", help="mlx: Apple Silicon; hf: transformers on CUDA/CPU")
    ap.add_argument("--model", default="mlx-community/Qwen3-VL-8B-Instruct-4bit")
    ap.add_argument("--ids", help="JSON list of doc_ids to run (e.g. eval/bakeoff.json)")
    ap.add_argument("--limit", type=int)
    ap.add_argument("--cache", help="raw-output cache dir (default: derived from backend, model and prompt hash)")
    ap.add_argument("--ocr-cache", help="per-page OCR JSON dir for the not_in_ocr review flag (verifier)")
    a = ap.parse_args(argv)

    docs = documents(a.split)
    if a.ids:
        keep = set(json.load(open(a.ids)))
        docs = {d: p for d, p in docs.items() if d in keep}
    docs = dict(list(docs.items())[: a.limit])
    if not docs:
        raise SystemExit(f"no pages found for split {a.split!r}")

    cache = a.cache or os.path.join(ROOT, "runs", "cache", f"{a.backend}-{a.model.split('/')[-1]}-{PROMPT_HASH}")
    os.makedirs(cache, exist_ok=True)
    backend, preds, flags, t0 = None, {}, {}, time.time()
    for i, (d, pages) in enumerate(docs.items()):
        path = os.path.join(cache, d + ".json")
        if os.path.exists(path):
            rec = json.load(open(path))
        else:
            backend = backend or make_backend(a.backend, a.model)
            rec = extract_doc(backend, pages)
            json.dump(rec, open(path, "w"), indent=1)
            s = rec["stats"]
            print(f"{i + 1}/{len(docs)} {d} {rec['doc_type']} {s.get('secs')}s peak {s.get('peak_gb')} GB "
                  f"(total {time.time() - t0:.0f}s)", file=sys.stderr, flush=True)
        preds[d], f = to_prediction(rec, ocr_text(pages, a.ocr_cache) if a.ocr_cache else None)
        if f:
            flags[d] = f

    if problems := errors(preds):
        raise SystemExit("schema check failed:\n" + "\n".join(problems[:20]))
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    json.dump(preds, open(a.out, "w"), indent=1)
    flags_path = os.path.splitext(a.out)[0] + "_review_flags.json"
    json.dump(flags, open(flags_path, "w"), indent=1)
    print(f"wrote {a.out} ({len(preds)} docs) and {flags_path} ({len(flags)} flagged docs); cache {cache}", file=sys.stderr)


if __name__ == "__main__":
    main()
