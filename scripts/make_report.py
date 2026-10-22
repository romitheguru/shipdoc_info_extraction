"""Dev results -> report/report.html -> report.pdf (2 pages max), plus the tables for analysis-notes/12.

    uv run python scripts/make_report.py --dev runs/dev.json --repo https://github.com/romitheguru/shipdoc_info_extraction

Fills the {{...}} slots of report/template.html: dev slice table (incl. the clean fold-4 unseen slice), review-flag
precision/recall, throughput from the raw-output cache, failure modes (report/failures.html, written by hand after
reading the per-doc errors this script prints). The PDF is printed with a headless Chromium browser.
"""
import argparse, glob, json, os, re, statistics, subprocess, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from eval.evaluate import evaluate, gold_set  # noqa: E402
from eval.flags import report as flag_report  # noqa: E402

BROWSERS = ["/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Chromium.app/Contents/MacOS/Chromium", "chromium", "google-chrome"]
SLICES = [("all", "all"), ("scanned=yes", "scanned"), ("scanned=no", "digital"), ("multi_page=yes", "multi-page"),
          ("repeated_parts=yes", "repeated parts"), ("illegible=yes", "illegible field"), ("waybill=yes", "waybills"),
          ("waybill=no", "invoices")]


def pct(x):
    return f"{100 * x:.1f}"


def row(name, a):
    ff = f"{a['false_fill_rate'] * a['illegible_fields']:.0f}/{a['illegible_fields']}" if a["illegible_fields"] else "–"
    return (f"<tr><td>{name}</td><td>{a['documents']}</td><td><b>{pct(a['OVERALL'])}</b></td><td>{pct(a['header_field_accuracy'])}</td>"
            f"<td>{pct(a['row_f1']) if a['line_item_rows'] else '–'}</td><td>{pct(a['documents_fully_correct'])}</td><td>{ff}</td></tr>")


def results(pred, name):
    dev = evaluate(pred, gold_set(name))
    f4 = evaluate(pred, gold_set(f"{name}/fold:4"))["all"]
    rest = evaluate(pred, {d: g for d, g in gold_set(name).items() if d not in gold_set(f"{name}/fold:4")})["all"]
    head = "<tr><th>slice</th><th>docs</th><th>OVERALL</th><th>header %</th><th>row F1</th><th>docs exact %</th><th>false fills</th></tr>"
    body = [row(label, dev[k]) for k, label in SLICES if k in dev]
    body += [row("<b>unseen</b>: fold 4, clean (no prompt change from these)", f4),
             row("seen: other folds (prompt iterated on errors here)", rest)]
    return dev, f4, f"<table>{head}{''.join(body)}</table>"


def throughput(cache_dirs):
    recs = [json.load(open(f)) for c in cache_dirs for f in glob.glob(os.path.join(c, "*.json"))]
    secs = sorted(r["stats"].get("secs", 0) + r.get("classify_stats", {}).get("secs", 0) for r in recs)
    peak = max(r["stats"].get("peak_gb", 0) for r in recs)
    p95 = secs[int(0.95 * (len(secs) - 1))]
    return (f"over {len(secs)} docs, {statistics.median(secs):.0f} s/doc median, {p95:.0f} s p95, "
            f"{3600 / statistics.mean(secs):.0f} docs/hour on one Mac, {peak:.1f} GB peak for the extractor "
            f"(+ PaddleOCR-VL ~3 s/page, 2.3 GB, run separately)")


def print_pdf(html, pdf):
    for b in BROWSERS:
        try:
            subprocess.run([b, "--headless", "--disable-gpu", "--no-pdf-header-footer", f"--print-to-pdf={pdf}",
                            "file://" + html], check=True, capture_output=True, timeout=120)
            return re.findall(rb"/Type\s*/Page[^s]", open(pdf, "rb").read())
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue
    raise SystemExit("no Chromium-based browser found to print the PDF")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev", default="runs/dev.json")
    ap.add_argument("--set", default="dev", help="gold set to score (bakeoff for a dry run before dev is done)")
    ap.add_argument("--repo", default="https://github.com/romitheguru/shipdoc_info_extraction")
    ap.add_argument("--cache", nargs="+", default=glob.glob(os.path.join(ROOT, "runs/cache/mlx-Qwen3-VL-8B-Instruct-4bit-93a7dfb4")))
    a = ap.parse_args()
    pred = json.load(open(a.dev))
    flags = json.load(open(os.path.splitext(a.dev)[0] + "_review_flags.json"))
    dev, f4, table = results(pred, a.set)
    fl = flag_report(pred, flags, gold_set(a.set))
    tp = throughput(a.cache)

    for d, r in dev["per_doc"].items():  # per-doc errors, to write report/failures.html from
        if not r["exact"]:
            print(d, "header wrong:", r["header_wrong"], f"rows {r['rows_full']}/{r['rows_gold']} (pred {r['rows_pred']})",
                  "FALSE FILL" if r["false_fill"] else "", "flagged" if flags.get(d) else "NOT FLAGGED")
    print(fl)
    print(tp)

    m = [None] + [x for pr in re.findall(r"precision\s+([\d.]+)%\s+recall\s+([\d.]+)%", fl)[:2] for x in pr]
    flag_html = (f"<p>A value is flagged when the independent reader (PaddleOCR-VL) does not find it on the page, or when a "
                 f"slash date could be day- or month-first; a whole document is flagged if the output was truncated. "
                 f"On dev: <b>document level</b> precision {m[1]}%, recall {m[2]}% (a flagged doc is not fully correct); "
                 f"<b>value level</b> precision {m[3]}%, recall {m[4]}% (header fields and predicted rows). "
                 f"Column-mapping errors are invisible to a text check by design, so they are only caught at document level "
                 f"when another value is also flagged.</p><pre>{fl}</pre>")
    failures = open(os.path.join(ROOT, "report/failures.html")).read() if os.path.exists(os.path.join(ROOT, "report/failures.html")) else "<p>(pending)</p>"
    html = open(os.path.join(ROOT, "report/template.html")).read()
    for k, v in {"RESULTS": table, "FLAGS": flag_html, "F4N": str(f4["documents"]), "THROUGHPUT": tp,
                 "FAILURES": failures, "REPO": a.repo}.items():
        html = html.replace("{{" + k + "}}", v)
    out = os.path.join(ROOT, "report/report.html")
    open(out, "w").write(html)
    pages = print_pdf(out, os.path.join(ROOT, "report.pdf"))
    print(f"report.pdf: {len(pages)} pages" + ("  <-- OVER THE 2-PAGE LIMIT" if len(pages) > 2 else ""))
    open(os.path.join(ROOT, "analysis-notes/out/12_dev_tables.html"), "w").write(table + flag_html + f"<p>{tp}</p>")


if __name__ == "__main__":
    main()
