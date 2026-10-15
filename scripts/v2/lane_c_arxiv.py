"""Lane C (V2): extraction-independent check of the function-word shift using arXiv abstracts.

For a seeded random sample of papers per cohort, look up the paper on arXiv by exact title (arXiv API,
one request every 4 s) and compare the abstract as the authors typed it into arXiv's metadata form
with the abstract region extracted from the dataset's `clean` text of the same paper. The arXiv
abstract never passes through a PDF text layer, so if the dataset's low "of"/"in"/"we" rates are an
extraction artifact the arXiv abstracts should not show them.

The arXiv abstract is the latest arXiv version's, which may differ from the dataset's PDF version.
Each pair therefore records a text-similarity score; exact-wording pairs are analysed separately.
No abstract text is written to results/; matched ids, dates and counts only.

Usage: python3 scripts/v2/lane_c_arxiv.py --n 120 --out results/v2/function_words/arxiv_abstracts.csv
"""
from __future__ import annotations

import argparse
import difflib
import os
import random
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lane_c_fetch import fetch  # noqa: E402
from lane_c_count import regions, measure, TOK  # noqa: E402

COHORTS = ["iclr-2024", "iclr-2025", "iclr-2026", "iclr-2027", "icml-2026", "icml-2023", "colm-2026"]
NS = {"a": "http://www.w3.org/2005/Atom"}
API = "https://export.arxiv.org/api/query?"
CACHE = os.path.expanduser("~/.cache/lane_c_arxiv")


def norm(t: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", t.lower()).split())


def query(title: str) -> list[dict]:
    os.makedirs(CACHE, exist_ok=True)
    key = os.path.join(CACHE, re.sub(r"[^a-z0-9]", "_", norm(title))[:150] + ".xml")
    if os.path.exists(key):
        xml = open(key, encoding="utf-8").read()
    else:
        stop = {"the", "of", "in", "and", "a", "an", "for", "on", "with", "to", "is", "are", "via", "by",
                "from", "at", "as", "or", "its", "be", "we", "can", "do", "does", "not", "into", "how"}
        words = [w for w in norm(title).split() if len(w) > 1 and w not in stop][:10]
        q = " AND ".join(f"ti:{w}" for w in words)
        url = API + urllib.parse.urlencode({"search_query": q, "max_results": 5})
        for attempt in range(4):
            try:
                xml = urllib.request.urlopen(url, timeout=60).read().decode("utf-8")
                break
            except Exception:
                time.sleep(90 * (attempt + 1))  # arXiv answers 429 when pushed
        else:
            return []
        time.sleep(4.0)
        open(key, "w", encoding="utf-8").write(xml)
    out = []
    for e in ET.fromstring(xml).findall("a:entry", NS):
        t = e.findtext("a:title", "", NS)
        out.append({"arxiv_id": e.findtext("a:id", "", NS).rsplit("/", 1)[-1],
                    "arxiv_title": " ".join(t.split()),
                    "arxiv_abstract": " ".join(e.findtext("a:summary", "", NS).split()),
                    "published": e.findtext("a:published", "", NS)[:10],
                    "updated": e.findtext("a:updated", "", NS)[:10]})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=120)
    ap.add_argument("--seed", type=int, default=20261015)
    ap.add_argument("--cohorts", nargs="*", default=COHORTS)
    ap.add_argument("--out", default="results/v2/function_words/arxiv_abstracts.csv")
    a = ap.parse_args()
    rows = []
    for stem in a.cohorts:
        pf = pq.ParquetFile(fetch(f"clean/{stem}.parquet"))  # streamed: ICLR 2027 text does not fit in memory
        meta = []
        for b in pf.iter_batches(batch_size=1024, columns=["paper_id", "title", "text"]):
            for pid, title, text in zip(*(b.column(i).to_pylist() for i in range(3))):
                if title and len(norm(title)) >= 20 and len(text or "") >= 2000:
                    meta.append({"paper_id": pid, "title": title})
        meta.sort(key=lambda r: r["paper_id"])
        rng = random.Random(f"{a.seed}-{stem}")
        sample = rng.sample(meta, min(a.n, len(meta)))
        want = {r["paper_id"] for r in sample}
        texts = {}
        for b in pf.iter_batches(batch_size=1024, columns=["paper_id", "text"]):
            for pid, text in zip(b.column(0).to_pylist(), b.column(1).to_pylist()):
                if pid in want:
                    texts[pid] = text
        for r in sample:
            r["text"] = texts[r["paper_id"]]
        for i, r in enumerate(sample):
            ds_abs = regions(r["text"])["abstract"]
            hits = [h for h in query(r["title"]) if norm(h["arxiv_title"]) == norm(r["title"])]
            row = {"cohort": stem, "paper_id": r["paper_id"], "found_abstract": ds_abs is not None,
                   "arxiv_match": bool(hits)}
            if hits and ds_abs:
                h = hits[0]
                da, xa = " ".join(ds_abs.split()), h["arxiv_abstract"]
                sim = difflib.SequenceMatcher(None, [w.lower() for w in TOK.findall(da)],
                                              [w.lower() for w in TOK.findall(xa)], autojunk=False).ratio()
                row.update(arxiv_id=h["arxiv_id"], published=h["published"], updated=h["updated"],
                           similarity=round(sim, 4))
                for tag, txt in (("ds", da), ("ax", xa)):
                    m = measure(txt)
                    for k in ("tokens", "of", "in", "we", "and", "the", "a", "to", "for", "on", "with",
                              "is", "by", "that", "our", "this"):
                        row[f"{tag}_{k}"] = m[k]
            rows.append(row)
            if i % 20 == 0:
                print(stem, i, sum(x.get("arxiv_match", False) for x in rows if x["cohort"] == stem), flush=True)
        pd.DataFrame(rows).to_csv(a.out, index=False)
    pd.DataFrame(rows).to_csv(a.out, index=False)


if __name__ == "__main__":
    main()
