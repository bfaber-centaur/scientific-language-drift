"""Lane A, step 1: per-paper decomposition of each PDF into main body, reference zone and
post-reference material (ids, lengths and appendix section headings only; no paper text).

Usage:
    python3 scripts/appendix_scan.py --out data/appendix            # ICLR 2017-2027 + other venues
    python3 scripts/appendix_scan.py --venues iclr --years 2018 --out data/appx_demo

Regions (omissions config, pages separated by \\f; see docs/appendix-growth.md):
    body     text before the first ⟦references omitted⟧ marker (the study's main_body()).
    refzone  text between the first and the last references marker. The dataset writes one
             marker per reference-list page, so this is non-reference residue on reference pages.
    post     text after the last references marker: what the earlier study called "appendix share".
Lengths: characters of omissions text (prose; tables, equations and figures are markers),
tokenizer v1.3 tokens (src/mlngrams/tokenize.py, the same tokens the n-gram study counts),
and pages at half-page resolution (from \\f positions and the pages holding reference markers). Omission markers are counted per region as a
measure of non-prose content (tables, display equations, figures).

Post-region content checks:
    stmt_*      ethics / reproducibility / LLM / acknowledgment sections (sections.HEADING)
    checklist   NeurIPS-style paper checklist, from its first question (or "Paper Checklist"
                heading) to its last answer's justification (checklist_end); NeurIPS 2025 places it
                between the references and the appendix
    refres      bibliography residue: post_refres_lines counts bibliography-like lines anywhere in the
                post region (diagnostic; includes in-text citations); post_refres_chars is the leading
                block of reference entries left after the last marker (removed from the appendix).
                Bibliography-like lines are also counted in the last 3,000 characters of the body.
Appendix before references: sections lettered A, B, C (each >= 200 chars) after the first fifth
of the body (body_appx_*); main body and appendix are then re-split in the analysis.
Appendix headings: top-level appendix sections are lettered (A, B, C, ...). A candidate is a
line "A" followed by a heading line, or a single line "A TITLE" / "Appendix A: Title"; a candidate
is accepted only if its letter is the next expected letter (one skip allowed), which rejects
sentences that start with "A". Each accepted section's characters/tokens are recorded with its
title so composition can be measured (scripts/appendix_analyze.py classifies titles).

Outputs (git-ignored, under --out):
    papers.parquet    one row per paper
    sections.parquet  one row per accepted post-reference section: top level (num = 0) and its
                      second-level subsections "A.1" (num >= 1); title, chars, tokens, markers
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import re
import sys
from multiprocessing import Pool

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.load import REVISION, fetch  # noqa: E402
from mlngrams.sections import HEADING as STMT_HEADING, strip_statements  # noqa: E402
from mlngrams.tokenize import TOKENIZER_VERSION, tokenize  # noqa: E402

SCAN_VERSION = "v1"
REF = "⟦references omitted⟧"
VENUES = {
    "iclr": list(range(2017, 2028)),
    "neurips": [2021, 2022, 2023, 2024, 2025],
    "tmlr": [2022, 2023, 2024, 2025, 2026],
    "colm": [2024, 2025],
    "corl": [2021, 2022, 2023, 2024],
    "icml": [2025],
    "emnlp": [2023],
}
MARKER = re.compile(r"⟦([a-z ]+?)(?: omitted)?⟧")
MARKER_KINDS = {"equation": "eq", "math": "math", "figure": "fig", "table": "tab", "numbers": "num"}
# Lettered appendix headings.
_LETTER_ONLY = re.compile(r"^(?:APPENDIX\s+|Appendix\s+)?([A-Z])[.:]?$")
_LETTER_TITLE = re.compile(r"^(?:APPENDIX\s+|Appendix\s+)?([A-Z])(?:[.:)]|\s+[-–—:]?)\s*([A-Z][^\n]{2,90})$")
_SUB = re.compile(r"^[A-Z]\.\d+(?:\.\d+)*\.?(?:\s+\S.*)?$")
_CHECKLIST = re.compile(r"^[ \t]*(?:[A-Z]?\d*\.?\s*)?(?:neurips |iclr |colm )?paper checklist\s*$", re.I | re.M)
# Bibliography-entry signals on one line.
_REF_LINE = re.compile(
    r"(?:\b(?:19|20)\d\d[a-z]?\.(?:\s|$)|arxiv(?: preprint)?|in proceedings|proceedings of|"
    r"advances in neural information|conference on|journal of|pp\.\s*\d|URL\s+https?://|doi:|"
    r"\bet al\.,? (?:19|20)\d\d)", re.I)


def heading_title_ok(s: str) -> bool:
    """A plausible heading line: short, no trailing period, mostly capitalised words."""
    s = s.strip()
    if not (2 <= len(s) <= 90) or s.endswith((".", ",", ";")):
        return False
    if not re.search(r"[A-Za-z]{2}", s):
        return False
    if s.upper() == s:
        return True
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", s)
    small = {"a", "an", "and", "the", "of", "for", "in", "on", "to", "with", "by", "vs", "via", "from", "at", "or"}
    caps = sum(w[0].isupper() for w in words if w.lower() not in small)
    big = sum(1 for w in words if w.lower() not in small)
    return big > 0 and caps / big >= 0.6 and len(words) <= 12


def heading_title_loose(s: str) -> bool:
    """Title line after a letter that stands alone on its line (a strong heading signal), so
    sentence-case titles are accepted: short, starts with a capital, no trailing period."""
    s = s.strip()
    return 2 <= len(s) <= 90 and s[0].isupper() and not s.endswith((".", ",", ";")) and bool(re.search(r"[A-Za-z]{2}", s))


def find_sections(post: str):
    """Accepted top-level lettered sections, skipping an appendix table of contents. An entry is
    contents-like if it is under TOC_CHARS characters, contains dot leaders, or its title ends in
    a page number; a run of three or more such entries starting at the first or second accepted
    entry is a contents list, and detection restarts after it."""
    base = 0
    for _ in range(3):
        secs = _find_sections(post[base:])
        ends = [s[2] for s in secs[1:]] + [len(post) - base]

        def tocish(k):
            seg = post[base + secs[k][2]: base + ends[k]]
            return (len(seg) < TOC_CHARS or ". . ." in seg or ". . ." in secs[k][1]
                    or re.search(r"\s\d{1,3}$", secs[k][1]) is not None)
        cut = None
        for start in (0, 1):
            k = start
            while k < len(secs) and tocish(k):
                k += 1
            if k - start >= 3:
                cut = k
                break
        if cut is None:
            return [(a, b, c + base) for a, b, c in secs]
        # restart after the contents list; if every accepted entry was contents-like, the real
        # headings were rejected as out of order, so restart just after the last entry's heading
        base += ends[cut - 1] if cut < len(secs) else secs[cut - 1][2] + 1
    return []


TOC_CHARS = 80


def _find_sections(post: str):
    lines = post.split("\n")
    offs, o = [], 0
    for ln in lines:
        offs.append(o)
        o += len(ln) + 1
    out, expect = [], ord("A")
    i = 0
    while i < len(lines):
        s = lines[i].strip()
        cand = None
        m = _LETTER_ONLY.match(s)
        if m:
            j = i + 1
            while j < len(lines) and not lines[j].strip():
                j += 1
            if j < len(lines) and heading_title_loose(lines[j]) and not _SUB.match(lines[j].strip()):
                cand = (m.group(1), lines[j].strip())
        else:
            m = _LETTER_TITLE.match(s)
            if m and heading_title_ok(m.group(2)):
                cand = (m.group(1), m.group(2).strip())
        if cand and ord(cand[0]) in (expect, expect + 1):
            out.append((cand[0], cand[1], offs[i]))
            expect = ord(cand[0]) + 1
        i += 1
    return out


_SUB_ONLY = re.compile(r"^([A-Z])\.(\d+)\.?$")
_SUB_TITLE = re.compile(r"^([A-Z])\.(\d+)\.?\s+([A-Z][^\n]{2,90})$")


def find_subsections(seg: str, letter: str):
    """Second-level sections "A.1 TITLE" inside one lettered section: list of (num, title, start)."""
    lines = seg.split("\n")
    out, o, last = [], 0, 0
    for i, ln in enumerate(lines):
        s = ln.strip()
        cand = None
        m = _SUB_ONLY.match(s)
        if m and i + 1 < len(lines) and heading_title_ok(lines[i + 1]):
            cand = (m.group(1), int(m.group(2)), lines[i + 1].strip())
        else:
            m = _SUB_TITLE.match(s)
            if m and heading_title_ok(m.group(3)):
                cand = (m.group(1), int(m.group(2)), m.group(3).strip())
        if cand and cand[0] == letter and last < cand[1] <= last + 2:
            out.append((cand[1], cand[2], o))
            last = cand[1]
        o += len(ln) + 1
    return out


_CK_QUESTION = re.compile(r"do the main claims made in the abstract and introduction", re.I)
_CK_ANSWER = re.compile(r"^[ \t]*Answer:\s*\[(?:Yes|No|NA|N/A)\]", re.M)


def checklist_start(post: str):
    """Offset where a NeurIPS-style paper checklist starts (it runs to the end of the PDF), or None.
    Its heading is not always extracted, so the anchor is the first checklist question, or the first
    of three or more "Answer: [Yes|No|NA]" lines when the questions were not extracted; the start
    moves back over up to three preceding short lines ("Checklist", "1. For all authors...",
    "1. Claims"). A "Paper Checklist" heading line is used when present."""
    m = _CHECKLIST.search(post)
    q = _CK_QUESTION.search(post)
    answers = [a.start() for a in _CK_ANSWER.finditer(post)]
    if len(answers) >= 3 and (q is None or answers[0] < q.start()):
        q = _CK_ANSWER.search(post)  # questions not extracted (NeurIPS 2024+): first answer line
    if q is None:
        return m.start() if m else None
    start = post.rfind("\n", 0, q.start()) + 1
    for _ in range(3):
        prev = post.rfind("\n", 0, max(0, start - 1)) + 1
        if start == 0 or len(post[prev:start].strip()) > 60:
            break
        start = prev
    return min(start, m.start()) if m else start


def checklist_end(post: str, start: int) -> int:
    """End of the checklist that starts at `start`. NeurIPS 2025 puts the checklist between the
    references and the appendix, so it does not always run to the end: it ends at the first lettered
    appendix heading after the last "Answer: [...]" line, or CK_TAIL characters after that line
    (its justification), whichever comes first; with no answer lines, at the end of the post region."""
    answers = [a.start() for a in _CK_ANSWER.finditer(post, start)]
    if not answers:
        return len(post)
    a = answers[-1]
    secs = find_sections(post[a:])
    nxt = a + secs[0][2] if secs else len(post)
    return min(nxt, a + CK_TAIL, len(post))


CK_TAIL = 500


def leading_refres(post: str) -> int:
    """Characters of bibliography residue at the start of the post region: reference entries the
    omissions config left after its last marker. The block runs from the start to the last
    bibliography-like line before three consecutive non-bibliography lines (> 20 chars) or the
    first lettered heading. Bibliography-like lines elsewhere (in-text citations) are not removed."""
    first_sec = secs[0][2] if (secs := find_sections(post)) else len(post)
    o, end, miss = 0, 0, 0
    for ln in post.split("\n"):
        if o >= first_sec:
            break
        s = ln.strip()
        if len(s) > 20:
            if _REF_LINE.search(s):
                end, miss = o + len(ln), 0
            else:
                miss += 1
                if miss >= 3:
                    break
        o += len(ln) + 1
    return end


def ntok(text: str) -> int:
    return sum(len(seg) for seg in tokenize(text)) if text else 0


def markers(text: str) -> dict:
    c = {v: 0 for v in MARKER_KINDS.values()}
    for m in MARKER.finditer(text):
        k = MARKER_KINDS.get(m.group(1).split()[0])
        if k:
            c[k] += 1
    return c


HALF = 300  # characters of prose on a reference page that count as half a page


def page_no(ff: list[int], pos: int) -> int:
    """1-based page number of character offset pos."""
    return bisect.bisect_right(ff, pos - 1) + 1


def analyse(args):
    venue, year, doc_id, text = args
    t = text or ""
    n = len(t)
    ff = [m.start() for m in re.finditer("\f", t)]
    first, last = t.find(REF), t.rfind(REF)
    r = {"venue": venue, "year": year, "doc_id": doc_id, "chars": n, "pages": len(ff) + 1,
         "n_ref_markers": t.count(REF), "has_ref": first >= 0}
    if first < 0:
        body, refzone, post = t, "", ""
        r["body_pages"], r["ref_pages"], r["post_pages"] = len(ff) + 1.0, 0.0, 0.0
    else:
        body = t[:first]
        post_start = last + len(REF)
        refzone = t[first + len(REF):last].replace(REF, "")
        post = t[post_start:]
        # Reference pages lose their text to markers, so offsets say nothing about how much of a
        # page the list filled: pages are counted at half-page resolution (docs/appendix-growth.md).
        pf, pl = page_no(ff, first), page_no(ff, last)
        before = len(t[(ff[pf - 2] + 1) if pf > 1 else 0:first].strip())
        after = len(t[post_start:ff[pl - 1] if pl <= len(ff) else n].strip())
        r["body_pages"] = (pf - 1) + (0.5 if before > HALF else 0.0)
        r["post_pages"] = (len(ff) + 1 - pl) + (0.5 if after > HALF else 0.0)
        r["ref_pages"] = len(ff) + 1 - r["body_pages"] - r["post_pages"]
    body_ns, body_stmt = strip_statements(body)
    r.update(body_chars=len(body), body_stmt_chars=body_stmt, refzone_chars=len(refzone.strip()),
             post_chars=len(post))
    r["body_tokens"] = ntok(body)
    r["body_tokens_nostmt"] = ntok(body_ns)
    r["refzone_tokens"] = ntok(refzone)
    r["post_tokens"] = ntok(post)
    for reg, txt in (("body", body), ("post", post)):
        for k, v in markers(txt).items():
            r[f"{reg}_{k}"] = v
    # post-region content checks
    post_ns, post_stmt = strip_statements(post)
    r["post_stmt_chars"] = post_stmt
    r["post_stmt_n"] = len(STMT_HEADING.findall(post))
    ck = checklist_start(post)
    ck_end = checklist_end(post, ck) if ck is not None else None
    r["post_checklist_chars"] = ck_end - ck if ck is not None else 0
    r["post_checklist_at_end"] = ck is not None and ck_end >= len(post) - 50
    post_off = (last + len(REF)) if first >= 0 else n
    r["post_checklist_pages"] = (page_no(ff, post_off + ck_end) - page_no(ff, post_off + ck) + 0.5) if ck is not None else 0.0
    lines = [ln.strip() for ln in post.split("\n") if len(ln.strip()) > 20]
    r["post_lines"] = len(lines)
    tail = [ln.strip() for ln in body[-3000:].split("\n") if len(ln.strip()) > 20]
    r["body_tail_lines"] = len(tail)
    r["body_tail_refres_lines"] = sum(bool(_REF_LINE.search(ln)) for ln in tail)
    r["post_refres_lines"] = sum(bool(_REF_LINE.search(ln)) for ln in lines)
    r["post_refres_chars"] = leading_refres(post)
    # appendix placed before the references: lettered sections after the first fifth of the body
    half = len(body) // 5
    bsecs = find_sections(body[half:])
    starts = [x[2] for x in bsecs] + [len(body) - half]
    if ([x[0] for x in bsecs[:3]] == ["A", "B", "C"]
            and all(starts[k + 1] - starts[k] >= 200 for k in range(3))):
        r["body_appx_chars"] = len(body) - (half + bsecs[0][2])
        r["body_appx_tokens"] = ntok(body[half + bsecs[0][2]:])
        r["body_appx_n_sections"] = len(bsecs)
        r["body_appx_pages"] = page_no(ff, len(body)) - page_no(ff, half + bsecs[0][2]) + 0.5
    else:
        r["body_appx_chars"], r["body_appx_tokens"], r["body_appx_n_sections"], r["body_appx_pages"] = 0, 0, 0, 0.0
    r["body_appendix_heading"] = bool(re.search(r"^\s*(?:APPENDIX|Appendix|APPENDICES|Appendices)\s*[A-Z]?\s*$",
                                                body[len(body) // 2:], re.M))
    r["post_appendix_word"] = bool(re.search(r"^\s*(?:APPENDIX|Appendix|APPENDICES|Appendices|SUPPLEMENTARY MATERIAL|Supplementary Material)\b",
                                             post[:3000], re.M))
    secs = find_sections(post)
    r["post_n_sections"] = len(secs)
    r["post_presection_chars"] = secs[0][2] if secs else len(post)
    srows = []
    for k, (letter, title, start) in enumerate(secs):
        end = secs[k + 1][2] if k + 1 < len(secs) else len(post)
        if ck is not None and start <= ck < end:  # checklist inside this section: cut it off
            end = ck
        if ck is not None and ck <= start < ck_end:  # heading inside the checklist (not an appendix)
            continue
        seg = post[start:end]
        row = {"venue": venue, "year": year, "doc_id": doc_id, "letter": letter, "num": 0,
               "title": title[:120], "chars": len(seg), "tokens": ntok(seg),
               **{f"n_{k2}": v for k2, v in markers(seg).items()}}
        srows.append(row)
        subs = find_subsections(seg, letter)
        for q, (num, st, s0) in enumerate(subs):
            s1 = subs[q + 1][2] if q + 1 < len(subs) else len(seg)
            sub = seg[s0:s1]
            srows.append({"venue": venue, "year": year, "doc_id": doc_id, "letter": letter, "num": num,
                          "title": st[:120], "chars": len(sub), "tokens": ntok(sub),
                          **{f"n_{k2}": v for k2, v in markers(sub).items()}})
    return r, srows


def iter_rows(venue, year):
    pf = pq.ParquetFile(fetch("omissions", venue, year))
    for b in pf.iter_batches(batch_size=128, columns=["paper_id", "text"]):
        for row in b.to_pylist():
            yield venue, year, row["paper_id"], row["text"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venues", nargs="*", default=list(VENUES))
    ap.add_argument("--years", nargs="*", type=int)
    ap.add_argument("--out", required=True)
    ap.add_argument("--procs", type=int, default=4)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    papers, sections = [], []
    with Pool(a.procs) as pool:
        for venue in a.venues:
            for year in VENUES[venue]:
                if a.years and year not in a.years:
                    continue
                k = 0
                for r, s in pool.imap(analyse, iter_rows(venue, year), chunksize=16):
                    papers.append(r)
                    sections.extend(s)
                    k += 1
                print(f"{venue} {year}: {k} papers", flush=True)
    pd.DataFrame(papers).to_parquet(os.path.join(a.out, "papers.parquet"), index=False)
    pd.DataFrame(sections).to_parquet(os.path.join(a.out, "sections.parquet"), index=False)
    with open(os.path.join(a.out, "run.json"), "w") as f:
        json.dump({"revision": REVISION, "config": "omissions", "scan_version": SCAN_VERSION,
                   "tokenizer": TOKENIZER_VERSION, "venues": a.venues, "years": a.years}, f, indent=1)


if __name__ == "__main__":
    main()
