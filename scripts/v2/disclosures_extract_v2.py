"""Lane D (V2): recover AI-use disclosures in every V2 venue-year from 2023 on, and flag in-text
AI-writing-use sentences in papers that have no disclosure section.

Uses the frozen V1.5 extractor (mlngrams.disclosures v1) and classifier (mlngrams.disclosure_classify
v2) unchanged, with the same clean/suspect tiers as scripts/disclosures/extract.py, so ICLR 2027 rows
must reproduce V1.5 exactly. New per-paper columns:
    in_body        heading before the first references marker
    inline_n       sentences anywhere in the paper (outside the recovered section) that pair an AI-tool
                   term with a writing/assistance term (_INLINE); a candidate count, not a label
    inline_example first such sentence, truncated to 25 words (kept only in data/, git-ignored)

Usage:
    python3 scripts/v2/disclosures_extract_v2.py --out data/v2/disclosures [--files iclr-2026 icml-2026]

Output (git-ignored; holds disclosure text): <out>/<venue>-<year>.parquet, <out>/run.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from multiprocessing import Pool

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.disclosure_classify import CLASSIFIER_VERSION, classify  # noqa: E402
from mlngrams.disclosures import EXTRACTOR_VERSION, clean, extract, looks_like_bibliography  # noqa: E402
from mlngrams.load import V2_REVISION, fetch  # noqa: E402
from mlngrams.sections import HEADING  # noqa: E402

REF = "⟦references omitted⟧"
FILES = (
    [f"iclr-{y}" for y in (2023, 2024, 2025, 2026, 2027)]
    + [f"icml-{y}" for y in (2023, 2024, 2025, 2026)]
    + [f"neurips-{y}" for y in (2023, 2024, 2025)]
    + [f"colm-{y}" for y in (2024, 2025, 2026)]
    + [f"tmlr-{y}" for y in (2024, 2025, 2026)]
    + ["corl-2025", "emnlp-2023"]
)
_AI_TOOL = r"(?:chatgpt|gpt-?\d[\w.-]*|gpt|claude|gemini|copilot|grammarly|deepl|llms?|large language models?|generative ai|gen-?ai|ai[- ](?:tools?|assistants?|assistance|assisted)|writing assistants?)"
_WRITE = r"(?:writing|polish\w*|proofread\w*|grammar\w*|spelling|language editing|edit(?:ing|ed) the (?:text|paper|manuscript)|readability|wording|phrasing|rephras\w*|paraphras\w*|manuscript|the paper'?s? (?:text|writing)|this (?:paper|manuscript|work)'?s? (?:text|writing|presentation))"
_SENT = re.compile(r"[^.!?\n]*(?:\n(?!\n)[^.!?\n]*)*[.!?]")
_INLINE = re.compile(r"\b" + _AI_TOOL + r"\b.{0,160}?\b" + _WRITE + r"\b|\b" + _WRITE + r"\b.{0,160}?\b" + _AI_TOOL + r"\b", re.I | re.S)
_SELF = re.compile(r"\b(?:we|us|our|the authors?|this (?:paper|manuscript|work|submission|article)|the (?:paper|manuscript|draft))\b", re.I)
_TOC = re.compile(r"(?:\. ?){8,}")
_USE_CUE = re.compile(r"\b(?:used?|using|employed|leveraged|assist\w*|help\w*|aid(?:ed)?|support\w*|utili[sz]ed)\b", re.I)


def group(labels: set[str]) -> str:
    """Lane C analysis groups, as scripts/disclosures/eval_groups.group."""
    if labels == {"none"}:
        return "none"
    if not labels or labels == {"ambiguous"}:
        return "unknown"
    if labels == {"polish"}:
        return "polish_only"
    if "drafting" in labels:
        return "drafting"
    return "other_use"


def inline_hits(text: str) -> list[str]:
    out = []
    for m in _SENT.finditer(text):
        s = m.group(0)
        if len(s) > 600:
            continue
        if _INLINE.search(s) and _USE_CUE.search(s) and _SELF.search(s):
            out.append(" ".join(s.split()))
    return out


def analyse(args):
    venue, year, pid, title, sha, t = args
    t = t or ""
    row = {"venue": venue, "year": year, "doc_id": pid, "pdf_sha256": sha, "title": title, "paper_chars": len(t)}
    ref = t.find(REF)
    d = extract(t)
    off, toc_skips = 0, 0
    # V2 addition: camera-ready appendices often have a table of contents whose "LLM usage ... 23"
    # entry is the first heading candidate; skip dot-leader bodies and take the next candidate.
    while d is not None and _TOC.search(d.text[:400]) and toc_skips < 3:
        toc_skips += 1
        off += d.end
        d = extract(t[off:])
    if d is not None and off:
        d = type(d)(d.heading, d.form, d.text, d.start + off, d.body_start + off, d.end + off, d.end_reason, d.n_candidates)
    row["toc_skips"] = toc_skips
    rest = t
    if d is None:
        row["found"] = False
    else:
        line_start = t.rfind("\n", 0, d.start) + 1
        bib = looks_like_bibliography(d.text)
        suspect = d.form in ("heading_after", "headless") or d.end_reason in ("max_chars", "end_of_text") or bib
        tc = clean(d.text)
        c = classify(tc)
        row.update(
            found=True, form=d.form, heading=d.heading, end_reason=d.end_reason, n_candidates=d.n_candidates,
            text=d.text, text_clean=tc, n_chars=len(tc), n_words=len(tc.split()), rel_pos=d.start / max(1, len(t)),
            in_body=(ref < 0 or d.start < ref), cut_by_v2=bool(HEADING.match(t, line_start)) and d.form == "line",
            bibliography_residue=bib, tier="suspect" if suspect else "clean",
            cls_labels=";".join(sorted(c["labels"])), cls_group=group(c["labels"]),
            cls_writing_unspecified=c["writing_unspecified"],
        )
        rest = t[:d.start] + t[d.end:]
    hits = inline_hits(rest)
    row["inline_n"] = len(hits)
    row["inline_example"] = " ".join(hits[0].split()[:25]) if hits else None
    return row


def iter_rows(venue, year):
    pf = pq.ParquetFile(fetch("omissions", venue, year, revision=V2_REVISION))
    for b in pf.iter_batches(batch_size=128, columns=["paper_id", "title", "pdf_sha256", "text"]):
        for r in b.to_pylist():
            yield venue, year, r["paper_id"], r["title"], r["pdf_sha256"], r["text"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "v2", "disclosures"))
    ap.add_argument("--files", nargs="*", default=FILES)
    ap.add_argument("--procs", type=int, default=2)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    with Pool(a.procs) as pool:
        for f in a.files:
            venue, year = f.rsplit("-", 1)
            rows = list(pool.imap(analyse, iter_rows(venue, int(year)), chunksize=16))
            df = pd.DataFrame(rows)
            df.to_parquet(os.path.join(a.out, f"{f}.parquet"), index=False)
            print(f, len(df), "found", int(df.found.sum()), "inline", int((df.inline_n > 0).sum()), flush=True)
    with open(os.path.join(a.out, "run.json"), "w") as fh:
        json.dump({"revision": V2_REVISION, "config": "omissions", "extractor": EXTRACTOR_VERSION,
                   "classifier": CLASSIFIER_VERSION, "files": a.files}, fh, indent=1)


if __name__ == "__main__":
    main()
