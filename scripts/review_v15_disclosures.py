"""Lane D (v1.5 review): independent audit of ICLR 2027 AI-use statement extraction and removal.

Usage: python3 scripts/review_v15_disclosures.py [--year 2027] [--sample 0] [--seed 15] [--excerpts N]

Independent of Lane B/C code. Over the omissions text of every (or a seeded sample
of) ICLR 2027 paper it records, per paper:

  n_ai_heads      heading-like lines that mention AI/LLM/language model together with
                  use/usage/statement/disclosure/declaration/assistance (broad net)
  n_matched       of those, lines the v2 remover (mlngrams.sections.HEADING) matches
  missed_heads    the broad-net headings v2 misses (variants that would leak)
  where           position of the first AI heading: body (before the first references
                  marker) / post (after it) / none
  stmt_chars      length of the section v2 cuts for the AI heading; capped flags a cut
                  that hit MAX_CHARS (likely overran into following text)
  leak_body       sentences left in main_body() after strip_statements() that look like
                  disclosure prose: (LLM|AI tool|language model|ChatGPT|GPT-4|Claude|Gemini)
                  within the same sentence as (writing|polish|grammar|proofread|assist|
                  responsib|disclos|edit|draft)
  overrun         the cut section contains a figure/table/equation marker or caption line
                  (the section end was not detected; non-disclosure text is cut with it)
  sig_body/sig_all  hits of high-precision template signatures ("responsibility for the
                  final content", "we have not used generative AI", ...) left in the cleaned
                  main body / anywhere in the paper
  inline_nohead   leak_body > 0 and no AI heading anywhere (statement written as a
                  paragraph without heading, e.g. inside acknowledgments or checklist)

Writes results/review/disclosure_audit_<year>.csv (one summary row) and
results/review/disclosure_heading_variants_<year>.csv (missed heading variants with
counts; heading lines only, no statement text). Excerpts are printed, not saved.
"""
from __future__ import annotations

import argparse
import collections
import os
import random
import re
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.load import fetch, main_body  # noqa: E402
from mlngrams.sections import HEADING, MAX_CHARS, _NEXT_HEADING, strip_statements  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
REF = "⟦references omitted⟧"
_AI = r"(?:\bai\b|\bllms?\b|language models?|generative|chatgpt|gpt)"
_KIND = r"(?:use|usage|statement|disclosure|declaration|assist|policy|tools?)"
_BROAD = re.compile(
    rf"^[ \t]*(?:[A-Z]?\d*(?:\.\d+)*\.?[ \t]+)?(?=[^\n]{{0,90}}{_AI})(?=[^\n]{{0,90}}{_KIND})[^\n.]{{3,90}}$",
    re.I | re.M)
_SENT = re.compile(r"[^.!?\n]*(?:\n(?!\n)[^.!?\n]*)*[.!?]")
_TOOL = re.compile(r"\bllms?\b|large language model|\bai[- ](?:tools?|assistan|models?|systems?|writing)|generative ai|chatgpt|gpt-4|\bclaude\b|\bgemini\b|copilot", re.I)
_ACT = re.compile(r"writ|polish|grammar|proofread|assist|responsib|disclos|edit(?:ing)?\b|draft|rephras|wording", re.I)
# High-precision signatures of the ICLR 2027 AI-use template (found by sentence census of cut sections)
_SIG = re.compile(r"responsibility for the final content|we have not used generative ai|we (?:have )?used generative ai tools|"
                  r"reviewed all ai-?\\s?assisted work|tasks with required disclosure|required[- ]disclosure tasks", re.I)
_OVERRUN = re.compile(r"⟦(?:figure|table|equation) omitted⟧|^(?:figure|table|algorithm) \\d+[:.]", re.I | re.M)
_TOPIC = re.compile(r"(?:benchmark|evaluat|fine-tun|prompt|train|dataset|model outputs?|our method)", re.I)


def leak_sentences(body: str) -> list[str]:
    out = []
    for m in _SENT.finditer(body):
        s = m.group(0)
        if len(s) > 400:
            continue
        if _TOOL.search(s) and _ACT.search(s):
            # sentences that describe disclosure of *our own* writing process
            if re.search(r"\b(we|authors?|this (?:paper|manuscript|work))\b", s, re.I) and re.search(
                    r"manuscript|paper|writing|grammar|polish|proofread|responsib", s, re.I):
                out.append(" ".join(s.split()))
    return out


def analyse(args):
    pid, t = args
    first = t.find(REF)
    heads = list(_BROAD.finditer(t))
    matched = [h for h in heads if HEADING.fullmatch(h.group(0))]
    missed = [h.group(0).strip()[:90] for h in heads if not HEADING.fullmatch(h.group(0))]
    where = "none"
    stmt_chars, capped, overrun = None, False, False
    if heads:
        h = heads[0]
        where = "body" if first < 0 or h.start() < first else "post"
        hm = next((x for x in HEADING.finditer(t) if x.start() >= h.start() - 2), None)
        if hm is not None and hm.start() <= h.end():
            n = _NEXT_HEADING.search(t, hm.end() + 1)
            end = n.start() if n else len(t)
            stmt_chars = min(end, hm.end() + MAX_CHARS) - hm.end()
            capped = end - hm.end() > MAX_CHARS
            cut = t[hm.end():min(end, hm.end() + MAX_CHARS)]
            overrun = bool(_OVERRUN.search(cut))
    body = strip_statements(main_body(t))[0]
    leaks = leak_sentences(body)
    sig_body = len(_SIG.findall(body))
    sig_all = len(_SIG.findall(t))
    return {
        "paper_id": pid, "n_ai_heads": len(heads), "n_matched": len(matched), "missed_heads": missed,
        "where": where, "stmt_chars": stmt_chars, "capped": capped, "overrun": overrun, "sig_body": sig_body, "sig_all": sig_all, "leak_body": len(leaks),
        "leak_ex": leaks[:2], "inline_nohead": bool(leaks) and not heads,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, default=2027)
    ap.add_argument("--sample", type=int, default=0, help="0 = all papers")
    ap.add_argument("--seed", type=int, default=15)
    ap.add_argument("--excerpts", type=int, default=0)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    a = ap.parse_args()
    pf = pq.ParquetFile(fetch("omissions", "iclr", a.year))
    n = pf.metadata.num_rows
    keep = set(random.Random(f"{a.seed}-{a.year}").sample(range(n), a.sample)) if a.sample else None

    def gen():
        i = 0
        for b in pf.iter_batches(batch_size=256, columns=["paper_id", "text"]):
            for r in b.to_pylist():
                if keep is None or i in keep:
                    yield r["paper_id"], r["text"] or ""
                i += 1

    with ProcessPoolExecutor(a.workers) as ex:
        recs = list(ex.map(analyse, gen(), chunksize=64))
    df = pd.DataFrame(recs)
    var = collections.Counter(re.sub(r"^[A-Z]?\d*(?:\.\d+)*\.?\s+", "", m).lower() for ms in df.missed_heads for m in ms)
    out = os.path.join(ROOT, "results", "review")
    os.makedirs(out, exist_ok=True)
    pd.DataFrame([kv for kv in var.most_common() if kv[1] >= 3], columns=["missed_heading", "papers"]).to_csv(
        os.path.join(out, f"disclosure_heading_variants_{a.year}.csv"), index=False)
    s = {
        "year": a.year, "papers": len(df),
        "any_ai_heading": (df.n_ai_heads > 0).mean(),
        "v2_matched_any": (df.n_matched > 0).mean(),
        "broad_only_no_v2": ((df.n_ai_heads > 0) & (df.n_matched == 0)).mean(),
        "multi_ai_heads": (df.n_ai_heads > 1).mean(),
        "where_body": (df["where"] == "body").mean(), "where_post": (df["where"] == "post").mean(),
        "stmt_chars_med": df.stmt_chars.median(), "stmt_chars_p90": df.stmt_chars.quantile(.9),
        "capped": df.capped.mean(), "overrun_into_figs_tables": df.overrun.mean(),
        "template_sig_any": (df.sig_all > 0).mean(), "template_sig_left_in_body": (df.sig_body > 0).mean(),
        "template_sig_body_share_of_sig_papers": ((df.sig_body > 0) & (df.sig_all > 0)).sum() / max(1, (df.sig_all > 0).sum()),
        "leak_body_any": (df.leak_body > 0).mean(), "inline_nohead": df.inline_nohead.mean(),
    }
    pd.DataFrame([s]).to_csv(os.path.join(out, f"disclosure_audit_{a.year}.csv"), index=False, float_format="%.4f")
    print(pd.Series(s).to_string())
    print("\nmissed heading variants (top 25):")
    for k, v in var.most_common(25):
        print(f"  {v:6d}  {k}")
    if a.excerpts:
        r = random.Random(a.seed)
        lk = df[df.leak_body > 0]
        for _, row in lk.sample(min(a.excerpts, len(lk)), random_state=a.seed).iterrows():
            print(f"--- leak {row.paper_id} heads={row.n_ai_heads} matched={row.n_matched}: {row.leak_ex[0][:200]!r}")
        _ = r


if __name__ == "__main__":
    main()
