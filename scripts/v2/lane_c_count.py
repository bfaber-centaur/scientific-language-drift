"""Lane C (V2): independent per-paper function-word counter.

Does not import mlngrams. Reads the `clean` config (positioned-clean-v2: review line numbers, running
headers and page numbers removed, wrapped hyphenation joined) at the V2 pin, file by file, and writes one
row per (paper, region) with alphabetic-token counts. No paper text is written out.

Tokens: maximal runs of ASCII letters, lowercased ([A-Za-z]+). Digits, symbols and non-ASCII letters are
not tokens, so review line numbers, table values and maths symbols cannot dilute the denominator.

Regions (line-anchored headings in the clean text; a region that is not found is missing, never zero):
  abstract  text after an "Abstract" heading line and before the introduction heading, 300-6,000 chars
  intro600  the first 600 tokens after the introduction heading (fixed window: no section-2 boundary)
  body      from the introduction heading to the first references heading after it
  prose     lines of `body` with >= 12 tokens and >= 85% of non-space characters in letters
            (a running-prose filter: drops tables, equations, captions-as-fragments, headings)
  all       the whole text

Per region: tokens, counts of the WORDS list, of the BIGRAMS list, and a few construction counts
(sentence count, ", and", sentence-initial "We", passive be+ed, hyphenated compounds such as
"target-domain", possessive 's, "the X of", em dashes). Usage:
  python3 scripts/v2/lane_c_count.py --files iclr-2024 icml-2026 ... --out data/v2/lane_c/counts
"""
from __future__ import annotations

import argparse
import glob
import os
import re
import sys
from collections import Counter
from multiprocessing import Pool

import pandas as pd
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from lane_c_fetch import V2, fetch, expected  # noqa: E402

WORDS = ["of", "in", "we", "and", "the", "a", "an", "to", "is", "are", "for", "on", "with", "that",
         "by", "this", "our", "as", "it", "be", "which", "from", "can", "these", "its", "their",
         "while", "via", "across", "using", "us", "i"]
BIGRAMS = [("of", "the"), ("in", "the"), ("we", "propose"), ("we", "show"), ("in", "this"),
           ("and", "the"), ("to", "the"), ("on", "the"), ("number", "of"), ("set", "of"),
           ("can", "be"), ("such", "as"), ("as", "well"), ("and", "a")]
BIGRAM_SET = set(BIGRAMS)

TOK = re.compile(r"[A-Za-z]+")
ABS_H = re.compile(r"^[ \t]*(?:a\s?b\s?s\s?t\s?r\s?a\s?c\s?t)[ \t]*[.:—-]?[ \t]*$", re.I | re.M)
ABS_INLINE = re.compile(r"^[ \t]*abstract[ \t]*[.:—-][ \t]*\S", re.I | re.M)  # "Abstract. We ..." (ICML/ACL)
INTRO_H = re.compile(r"^[ \t]*(?:(?:1|I)[ \t]*\.?[ \t]*\n?[ \t]*)?introduction[ \t]*\.?[ \t]*$", re.I | re.M)
REF_H = re.compile(r"^[ \t]*(?:\d+[ \t]*\.?[ \t]*)?(?:references|bibliography|reference)[ \t]*$", re.I | re.M)
SENT = re.compile(r"[.!?](?=\s+[A-Z])")
COMMA_AND = re.compile(r",\s+and\b")
WE_INIT = re.compile(r"(?:^|[.!?]\s+)We\b", re.M)
HYPH = re.compile(r"\b[A-Za-z]+(?:-[A-Za-z]+)+\b")  # compound modifiers written with a hyphen, no spaces
POSS = re.compile(r"[A-Za-z][\u2019']s\b")  # possessive / contracted 's
THE_X_OF = re.compile(r"\b[Tt]he [a-z]+ of\b")
PASSIVE = re.compile(r"\b(?:is|are|was|were|be|been|being)\s+(?:\w+ly\s+)?[a-z]+ed\b")


def regions(text: str) -> dict[str, str | None]:
    out: dict[str, str | None] = {"all": text, "abstract": None, "intro600": None, "body": None,
                                  "prose": None}
    im = INTRO_H.search(text)
    if im is None:
        return out
    istart = im.end()
    am = None
    for m in ABS_H.finditer(text, 0, im.start()):
        am = m  # last abstract heading before the introduction
    if am is not None:
        a = text[am.end():im.start()]
        if 300 <= len(a) <= 6000:
            out["abstract"] = a
    else:
        m2 = None
        for m in ABS_INLINE.finditer(text, 0, im.start()):
            m2 = m
        if m2 is not None:
            a = text[m2.start():im.start()]
            a = re.sub(r"^[ \t]*abstract[ \t]*[.:—-]", "", a, flags=re.I)
            if 300 <= len(a) <= 6000:
                out["abstract"] = a
    rm = REF_H.search(text, istart)
    body = text[istart:rm.start()] if rm else None
    if body is not None and len(body) >= 2000:
        out["body"] = body
        lines = []
        for ln in body.split("\n"):
            nonspace = re.sub(r"\s", "", ln)
            if not nonspace:
                continue
            letters = sum(c.isalpha() for c in nonspace)
            if letters / len(nonspace) >= 0.85 and len(TOK.findall(ln)) >= 12:
                lines.append(ln)
        out["prose"] = "\n".join(lines) if lines else None
    # intro600: fixed window measured in tokens from the introduction heading
    toks = list(TOK.finditer(text, istart))
    if len(toks) >= 300:
        end = toks[min(599, len(toks) - 1)].end()
        out["intro600"] = text[istart:end]
    return out


def measure(text: str) -> dict:
    toks = [t.lower() for t in TOK.findall(text)]
    c = Counter(toks)
    row = {"tokens": len(toks)}
    for w in WORDS:
        row[w] = c.get(w, 0)
    bc = Counter(b for b in zip(toks, toks[1:]) if b in BIGRAM_SET)
    for b in BIGRAMS:
        row["_".join(b)] = bc.get(b, 0)
    row["sentences"] = len(SENT.findall(text)) + 1
    row["comma_and"] = len(COMMA_AND.findall(text))
    row["we_initial"] = len(WE_INIT.findall(text))
    row["passive"] = len(PASSIVE.findall(text))
    row["hyph_compound"] = len(HYPH.findall(text))
    row["possessive"] = len(POSS.findall(text))
    row["the_x_of"] = len(THE_X_OF.findall(text))
    row["em_dash"] = text.count("\u2014")
    row["chars_alpha_tok"] = sum(len(t) for t in toks)
    return row


def doc_rows(rec: dict) -> list[dict]:
    text = rec["text"] or ""
    base = {k: rec[k] for k in ("paper_id", "conference", "year", "pdf_sha256", "text_sha256")}
    base["text_chars"] = len(text)
    out = []
    for name, seg in regions(text).items():
        if seg is None:
            continue
        r = dict(base, region=name)
        r.update(measure(seg))
        out.append(r)
    return out


def run_file(stem: str, outdir: str) -> str:
    dst = os.path.join(outdir, f"{stem}.csv.gz")
    if os.path.exists(dst):
        return dst
    path = fetch(f"clean/{stem}.parquet")
    pf = pq.ParquetFile(path)
    rows = []
    cols = ["paper_id", "conference", "year", "pdf_sha256", "text_sha256", "text"]
    with Pool(4) as pool:
        for batch in pf.iter_batches(batch_size=256, columns=cols):
            for rs in pool.imap(doc_rows, batch.to_pylist(), chunksize=8):
                rows.extend(rs)
    df = pd.DataFrame(rows)
    df.to_csv(dst + ".tmp", index=False, compression="gzip")
    os.replace(dst + ".tmp", dst)
    return dst


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--files", nargs="*")
    ap.add_argument("--out", default="data/v2/lane_c/counts")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    stems = a.files or sorted(p.split("/")[1].removesuffix(".parquet")
                              for p in expected(V2) if p.startswith("clean/"))
    for s in stems:
        print(s, run_file(s, a.out), flush=True)
