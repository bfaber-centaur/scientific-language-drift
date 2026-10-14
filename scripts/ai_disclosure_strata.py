"""ICLR 2027: prose markers by the paper's own AI-use disclosure (self-reported).

Usage: python3 scripts/ai_disclosure_strata.py [--sample 12000]

ICLR 2027 submissions carry an "AI use statement". This script classifies each
statement with simple, auditable keyword rules (first match wins) and compares
main-body prose markers across classes. The statement itself is cut before the
prose is measured (mlngrams.sections), so it cannot leak into the markers.

Classes (rules applied to the lowercased statement):
    none      a negation of use ("did not use / have not used / no generative ai ...")
              and no positive "we used / were used / was used / to assist"
    drafting  positive use for producing text: "draft", "write/writing" + "paper|
              manuscript|sections|text|parts|portions", "generate text"
    polish    language-only help: grammar, polish, proofread, readability, clarity,
              language editing/refinement, phrasing, wording, typo
    other     any other statement (code, literature search, experiments, ...)
    no_statement
This is self-report, and the rules are crude; misclassification is expected and
the comparison is associational only.

Writes results/ai_disclosure_strata_2027.csv (per class: papers, marker
prevalence, mean stopword share, "of the" per million) and
results/ai_disclosure_rules_sample.csv (class counts only).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.count import ngrams_of  # noqa: E402
from mlngrams.filters import STOPWORDS  # noqa: E402
from mlngrams.load import fetch, main_body  # noqa: E402
from mlngrams.sections import HEADING, _NEXT_HEADING, strip_statements  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
PHRASES = ["we propose", "a novel", "in this paper", "state-of-the-art", "leverage", "notably",
           "underscores", "delve", "furthermore", "crucial", "test whether", "held fixed",
           "results support"]
_AI_HEAD = re.compile(r"\bai\b|llm|language model", re.I)
_NEG = re.compile(r"(did not|do not|have not|has not|were not|was not|no)\s+(use|used|using|rely)?\s*(any\s+)?(generative\s+)?(ai|llms?|large language)")
_POS = re.compile(r"\b(we used|we use|were used|was used|to assist|assisted|we employed|with the help)\b")
_DRAFT = re.compile(r"\bdraft|\bwrit(e|ing|ten)\b[^.]{0,40}\b(paper|manuscript|sections?|text|parts|portions|introduction|related work)|generate[sd]?\s+(the\s+)?text")
_POLISH = re.compile(r"grammar|polish|proofread|readability|clarity|language (editing|refinement|editing)|phrasing|wording|typo")


def statement(text: str) -> str | None:
    for m in HEADING.finditer(text):
        if _AI_HEAD.search(m.group(0)):
            n = _NEXT_HEADING.search(text, m.end() + 1)
            return text[m.end() : (n.start() if n else m.end() + 3000)][:3000].lower()
    return None


def classify(s: str | None) -> str:
    if s is None:
        return "no_statement"
    if _NEG.search(s) and not _POS.search(s):
        return "none"
    if _DRAFT.search(s):
        return "drafting"
    if _POLISH.search(s):
        return "polish"
    return "other"


def measure(text: str) -> dict:
    cls = classify(statement(text))
    segs = tokenize(strip_statements(main_body(text))[0])
    toks = [w for s in segs for w in s]
    bis = list(ngrams_of(segs, 2))
    flat = " " + " ".join(" ".join(s) for s in segs) + " "
    m = {"cls": cls, "tokens": len(toks),
         "stop_share": sum(w in STOPWORDS for w in toks) / max(1, len(toks)),
         "of_the_pm": 1e6 * bis.count("of the") / max(1, len(bis))}
    for p in PHRASES:
        m[p] = f" {p}" in flat
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=12000)
    ap.add_argument("--workers", type=int, default=3)
    a = ap.parse_args()
    pf = pq.ParquetFile(fetch("omissions", "iclr", 2027))
    n = pf.metadata.num_rows
    pick = set(np.random.default_rng(2027).choice(n, size=min(a.sample, n), replace=False).tolist())
    texts, i = [], 0
    for b in pf.iter_batches(batch_size=500, columns=["text"]):
        for r in b.to_pylist():
            if i in pick and r["text"] and len(r["text"]) >= 2000:
                texts.append(r["text"])
            i += 1
    with ProcessPoolExecutor(a.workers) as ex:
        rows = list(ex.map(measure, texts, chunksize=50))
    d = pd.DataFrame(rows)
    d = d[d.tokens >= 500]
    g = d.groupby("cls")
    out = g[["stop_share", "of_the_pm"] + PHRASES].mean()
    out.insert(0, "papers", g.size())
    out.to_csv(os.path.join(ROOT, "results", "ai_disclosure_strata_2027.csv"), float_format="%.4g")
    print(out.round(3).T.to_string())


if __name__ == "__main__":
    main()
