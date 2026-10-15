"""Lane D (v1.5 review): what is the text after the first references marker?

Usage: python3 scripts/review_v15_boundary.py [--venue iclr] [--years 2017 2027] [--sample 400] [--seed 15]
       [--excerpts N]

Independent of Lane A's code. For a seeded random sample of papers per year it
splits the omissions text at the first and last `⟦references omitted⟧` marker and
measures, per paper:

  pre / mid / post  characters before the first marker, between first and last
                    marker (reference-page residue, page headers, interleaved
                    text), and after the last marker
  ref_page / pages  page (form feed count) of the first marker, total pages
  refish_mid/post   share of non-empty lines in that span that look like
                    bibliography entries (year in parentheses or "20xx." plus
                    "arXiv|Proceedings|In |Conference|Journal|URL|doi"), i.e.
                    reference text that the omission step missed
  post_head         the first heading-like line after the last marker, bucketed:
                    appendix (A / A.1 / APPENDIX / SUPPLEMENTARY), checklist
                    (NeurIPS/paper checklist), statement (ethics, reproducibility,
                    AI/LLM use, impact, acknowledgments), none, other
  app_before_refs   an appendix heading occurs *before* the first marker
                    (appendix placed before references: post-ref share undercounts)
  multi_block       the markers form two or more blocks separated by >= 3000
                    chars of other text (e.g. a second bibliography for the appendix)

Writes results/review/boundary_<venue>.csv (per-year summary) and, with
--excerpts, prints short (<= 160 char) excerpts with paper ids for manual checks.
No paper text is written to disk.
"""
from __future__ import annotations

import argparse
import os
import random
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.load import fetch  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
REF = "⟦references omitted⟧"
_REFLINE = re.compile(
    r"(\(\d{4}[a-z]?\)|\b(19|20)\d{2}[a-z]?\.)[^\n]*|"
    r"(arxiv|proceedings|in advances|conference on|journal of|url https?:|doi\b|preprint)", re.I)
_REFLINE2 = re.compile(r"arxiv|proceedings|advances in|conference|journal|preprint|url|doi|pp\.|vol\.", re.I)
_HEAD = re.compile(r"^[ \t]*(?:[A-Z](?:\.\d+)*\.?|\d+(?:\.\d+)*\.?)?[ \t]*[A-Z][^\n]{1,80}$", re.M)
_APP = re.compile(r"^[ \t]*(?:appendix|appendices|supplementary|supplemental)\b|^[ \t]*[A-H](?:\.\d+)?\.?[ \t]+[A-Z]", re.I | re.M)
# a whole heading line: "APPENDIX", "A Appendix", "Appendix A: Proofs", "Supplementary Material" (<= 60 chars, no
# sentence punctuation at the end), so wrapped body sentences that begin with "Appendix B shows" do not count
_APP_STRICT = re.compile(r"^[ \t]*(?:[A-H]\.?[ \t]+)?(?:appendix|appendices|supplementary material)\b(?:[ \t]+[A-Z0-9](?:\.\d+)*)?"
                         r"(?:[ \t]*[:.\-–][ \t]*[A-Z][^\n.]{0,50})?[ \t]*$", re.I | re.M)
_CHECK = re.compile(r"checklist", re.I)
_STMT = re.compile(r"ethic|reproducib|\bai\b|llm|language model|impact|acknowledg|author contrib", re.I)


def is_refish(line: str) -> bool:
    return bool(re.search(r"\(\d{4}[a-z]?\)|\b(19|20)\d{2}[a-z]?\b", line)) and bool(_REFLINE2.search(line))


def refish_share(span: str) -> float:
    lines = [ln for ln in span.split("\n") if len(ln.strip()) > 20]
    if not lines:
        return float("nan")
    return sum(is_refish(ln) for ln in lines) / len(lines)


_LETTER = re.compile(r"^[ \t]*[A-H](?:\.\d+)*\.?[ \t]*$")


def refish_chars(span: str) -> int:
    return sum(len(ln) for ln in span.split("\n") if len(ln.strip()) > 20 and is_refish(ln))


def bucket_head(span: str) -> tuple[str, str]:
    for m in _HEAD.finditer(span[:4000]):
        line = m.group(0).strip()
        if len(line) < 3 or line.startswith("⟦"):
            continue
        prev = span[:m.start()].rstrip("\n").rsplit("\n", 1)[-1]
        if _CHECK.search(line):
            return "checklist", line
        if _APP.match(line) or _LETTER.match(prev):
            return "appendix", line
        if _STMT.search(line):
            return "statement", line
        return "other", line
    return "none", ""


def analyse(pid: str, t: str) -> dict:
    n = len(t)
    first, last = t.find(REF), t.rfind(REF)
    rec = {"paper_id": pid, "chars": n, "pages": t.count("\x0c") + 1, "has_ref": first >= 0}
    if first < 0:
        return rec
    lastend = last + len(REF)
    mid, post = t[first + len(REF):last], t[lastend:]
    # blocks of markers separated by >= 3000 chars of other text
    pos = [m.start() for m in re.finditer(re.escape(REF), t)]
    blocks = 1 + sum(1 for a, b in zip(pos, pos[1:]) if b - a - len(REF) >= 3000)
    head, line = bucket_head(post)
    rec.update(
        pre=first, mid=len(mid.replace(REF, "")), post=len(post),
        n_markers=len(pos), multi_block=blocks >= 2,
        ref_page=t[:first].count("\x0c") + 1,
        refish_chars_post=refish_chars(post),
        refish_mid=refish_share(mid.replace(REF, "")), refish_post=refish_share(post[:6000]),
        post_head=head, post_head_line=line[:80],
        app_before_refs=bool(_APP_STRICT.search(t[:first])),
        share_first=1 - first / n, share_last=len(post) / n,
    )
    return rec


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="iclr")
    ap.add_argument("--years", type=int, nargs="+", default=[2017, 2020, 2023, 2025, 2026, 2027])
    ap.add_argument("--sample", type=int, default=400)
    ap.add_argument("--seed", type=int, default=15)
    ap.add_argument("--excerpts", type=int, default=0)
    a = ap.parse_args()
    rows, summ = [], []
    for y in a.years:
        pf = pq.ParquetFile(fetch("omissions", a.venue, y))
        n = pf.metadata.num_rows
        rng = random.Random(f"{a.seed}-{a.venue}-{y}")
        keep = set(rng.sample(range(n), min(a.sample, n)))
        i = 0
        recs, texts = [], {}
        for b in pf.iter_batches(batch_size=256, columns=["paper_id", "text"]):
            for r in b.to_pylist():
                if i in keep:
                    recs.append(analyse(r["paper_id"], r["text"] or ""))
                    if a.excerpts:
                        texts[r["paper_id"]] = r["text"] or ""
                i += 1
        df = pd.DataFrame(recs)
        df["year"] = y
        rows.append(df)
        d = df[df.has_ref]
        summ.append({
            "venue": a.venue, "year": y, "n": len(df), "has_ref": df.has_ref.mean(),
            "share_first_med": d.share_first.median(), "share_last_med": d.share_last.median(),
            "mid_chars_med": d.mid.median(), "mid_share_of_postfirst": (d.mid.sum() / (d.mid.sum() + d.post.sum())),
            "multi_block": d.multi_block.mean(), "app_before_refs": d.app_before_refs.mean(),
            "refish_mid_med": d.refish_mid.median(), "refish_post_med": d.refish_post.median(),
            "refish_post_gt30": (d.refish_post > 0.3).mean(),
        "refish_chars_share_of_post": d.refish_chars_post.sum() / max(1, d.post.sum()),
            **{f"head_{k}": (d.post_head == k).mean() for k in ["appendix", "checklist", "statement", "other", "none"]},
            "ref_page_med": d.ref_page.median(), "pages_med": d.pages.median(),
        })
        if a.excerpts:
            ex = random.Random(a.seed).sample(list(d.paper_id), min(a.excerpts, len(d)))
            for pid in ex:
                t = texts[pid]
                f, l = t.find(REF), t.rfind(REF) + len(REF)
                r = d[d.paper_id == pid].iloc[0]
                print(f"--- {a.venue}{y} {pid} pages={r.pages} refpage={r.ref_page} share_first={r.share_first:.2f} "
                      f"mid={r.mid} post_head={r.post_head}:{r.post_head_line!r} app_before={r.app_before_refs}")
                print("   before:", repr(t[max(0, f - 120):f][-120:]))
                print("   after :", repr(t[l:l + 160]))
    out = os.path.join(ROOT, "results", "review")
    os.makedirs(out, exist_ok=True)
    s = pd.DataFrame(summ)
    s.to_csv(os.path.join(out, f"boundary_{a.venue}.csv"), index=False, float_format="%.3f")
    pd.set_option("display.width", 250)
    print(s.T.to_string())


if __name__ == "__main__":
    main()
