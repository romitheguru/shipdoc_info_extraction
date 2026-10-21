"""Group page images into documents. Works on any split, labelled or not (pages are `<doc_id>_p<N>.png|jpg`)."""
import glob, os, re
from collections import defaultdict

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PAGE = re.compile(r"(?P<doc>.+)_p(?P<n>\d+)\.(?:png|jpe?g)$", re.I)


def documents(split, root=ROOT):
    """{doc_id: [page paths in page order]} for data/<split>/images."""
    docs = defaultdict(list)
    for path in glob.glob(os.path.join(root, "data", split, "images", "*")):
        if m := PAGE.match(os.path.basename(path)):
            docs[m["doc"]].append((int(m["n"]), path))
    return {d: [p for _, p in sorted(pages)] for d, pages in sorted(docs.items())}


def is_scan(path):
    """A .jpg page is a scan (CLAUDE.md, note 04)."""
    return path.lower().endswith((".jpg", ".jpeg"))
