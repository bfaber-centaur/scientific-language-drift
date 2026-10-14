"""Adversarial checks of docs/findings.md (Agent D). Aggregates only; no paper text is written.

    python3 scripts/qa_findings.py --out DIR [--per-year 1000] [--n27 3000] [--workers 3]
    python3 scripts/qa_findings.py --show-statements 40      # print AI-use statements for hand audit (stdout only)

Per sampled ICLR paper (main body, statement sections cut, same tokenizer as the pipeline):
  * llm_topic      abstract (first 2500 chars) mentions "language model" / "llm"
  * finding 2      presence of delve, underscores, intricate, pivotal, showcasing, realm (exact tokens)
  * finding 3      exact-bigram AND prefix-match (as in resubmission_test.py) presence of markers;
                   co-occurrence of the four 2027 markers
  * finding 4      stopword share and "of the" per million restricted to segments of >= 15 tokens
  * statement leak paragraph just BEFORE an AI-use heading that already talks about LLM/AI use
Only papers in ~/work/full_body/docs.parquet (not off-sample) are drawn.
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
from mlngrams.sections import HEADING, strip_statements  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402

WORDS = ["delve", "underscores", "intricate", "pivotal", "showcasing", "realm"]
MARK27 = ["test whether", "held fixed", "results support", "percentage points"]
PHR = ["we propose", "a novel", "notably", "leverage", "underscores"] + MARK27
_LLM = re.compile(r"language model|\bllms?\b|\bvlms?\b|\bgpt|chatbot|large multimodal", re.I)
_AIH = re.compile(r"\bai\b|llm|language model", re.I)
_USE = re.compile(r"\b(llms?|large language models?|chatgpt|gpt-\d|claude|gemini|ai (tools?|assistants?))\b.{0,80}\b(used|use|assist|polish|writing|grammar)", re.I)


def measure(args):
    year, text = args
    body = strip_statements(main_body(text))[0]
    segs = tokenize(body)
    toks = [w for s in segs for w in s]
    if len(toks) < 500:
        return None
    tokset = set(toks)
    bis = set(ngrams_of(segs, 2))
    flat = " " + " ".join(" ".join(s) for s in segs) + " "
    k = text.lower().find("abstract")
    abst = text[max(k, 0): max(k, 0) + 2500]
    long = [s for s in segs if len(s) >= 15]
    lt = [w for s in long for w in s]
    lb = list(ngrams_of(long, 2))
    m = {"year": year, "tokens": len(toks), "llm_topic": bool(_LLM.search(abst)),
         "stop_all": sum(w in STOPWORDS for w in toks) / len(toks),
         "stop_long": sum(w in STOPWORDS for w in lt) / max(1, len(lt)),
         "ofthe_long_pm": 1e6 * lb.count("of the") / max(1, len(lb)),
         "long_share": len(lt) / len(toks)}
    for w in WORDS:
        m[w] = w in tokset
    for p in PHR:
        m["x_" + p] = (p in bis) if " " in p else (p in tokset)
        m["p_" + p] = f" {p}" in flat
    # statement leak: paragraph right before an AI-use heading already discusses LLM use
    leak = False
    for h in HEADING.finditer(text):
        if _AIH.search(h.group(0)):
            prev = text[max(0, h.start() - 600): h.start()]
            leak = bool(_USE.search(prev))
            break
    m["leak_before_heading"] = leak
    return m


def sample_texts(year, n, allowed, seed):
    path = fetch("omissions", "iclr", year)
    ids = [i for i in pq.read_table(path, columns=["paper_id"]).column(0).to_pylist() if i in allowed]
    rng = np.random.default_rng(seed)
    pick = set(rng.choice(ids, size=min(n, len(ids)), replace=False).tolist())
    rows = []
    for b in pq.ParquetFile(path).iter_batches(batch_size=200, columns=["paper_id", "text"]):
        rows += [(r["paper_id"], r["text"]) for r in b.to_pylist() if r["paper_id"] in pick and r["text"]]
    return rows


def show_statements(k):
    sys.path.insert(0, os.path.dirname(__file__))
    from ai_disclosure_strata import classify, statement  # noqa
    pf = pq.ParquetFile(fetch("omissions", "iclr", 2027))
    rng = np.random.default_rng(7)
    pick = set(rng.choice(pf.metadata.num_rows, size=400, replace=False).tolist())
    i, shown = 0, 0
    for b in pf.iter_batches(batch_size=500, columns=["text"]):
        for r in b.to_pylist():
            if i in pick and shown < k:
                s = statement(r["text"] or "")
                if s:
                    print(f"[{shown}] {classify(s).upper()} :: {' '.join(s.split())[:420]}")
                    shown += 1
            i += 1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out")
    ap.add_argument("--per-year", type=int, default=1000)
    ap.add_argument("--n27", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--show-statements", type=int, default=0)
    a = ap.parse_args()
    if a.show_statements:
        return show_statements(a.show_statements)
    docs = pd.read_parquet(os.path.expanduser("~/work/full_body/docs.parquet"))
    docs = docs[~docs.stratum.str.contains("offsample")]
    jobs = []
    for y in (2017, 2021, 2023, 2024, 2025, 2026, 2027):
        allowed = set(docs[docs.year == y].doc_id)
        n = a.n27 if y == 2027 else a.per_year
        jobs += [(y, t) for _, t in sample_texts(y, n, allowed, y)]
    with ProcessPoolExecutor(a.workers) as ex:
        res = [r for r in ex.map(measure, jobs, chunksize=20) if r]
    d = pd.DataFrame(res)
    os.makedirs(a.out, exist_ok=True)
    d.to_parquet(os.path.join(a.out, "qa_findings_perdoc.parquet"), index=False)  # flags only, no text
    pd.set_option("display.width", 250)
    print("papers:", d.groupby("year").size().to_dict())
    print("\n== F2: word prevalence (%) by LLM-topic abstract ==")
    print((100 * d.groupby(["llm_topic", "year"])[WORDS].mean()).round(1).unstack(0).to_string())
    print("LLM-topic share by year:", d.groupby("year").llm_topic.mean().round(3).to_dict())
    print("\n== F3: exact vs prefix measures (%) ==")
    cols = [c for c in d if c.startswith(("x_", "p_"))]
    print((100 * d.groupby("year")[cols].mean()).round(1).T.to_string())
    print("\n== F3: 2027 markers by topic (%) ==")
    print((100 * d[d.year >= 2026].groupby(["year", "llm_topic"])[["x_" + m for m in MARK27] + ["x_we propose", "x_a novel"]].mean()).round(1).to_string())
    d["n27"] = d[["x_" + m for m in MARK27]].sum(1)
    for y in (2026, 2027):
        g = d[d.year == y]
        p = g[["x_" + m for m in MARK27]].mean()
        obs = g.n27.value_counts(normalize=True).sort_index().round(3).to_dict()
        # expected share with >=3 markers under independence
        from itertools import combinations
        exp3 = 0.0
        for kk in (3, 4):
            for c in combinations(range(4), kk):
                exp3 += np.prod([p.iloc[i] if i in c else 1 - p.iloc[i] for i in range(4)])
        print(f"{y}: distribution of #markers {obs}; >=3 observed {(g.n27 >= 3).mean():.3f} vs independent {exp3:.3f}")
    print("\n== F4: stopword share / 'of the' pm, all tokens vs segments >= 15 tokens ==")
    print(d.groupby("year")[["stop_all", "stop_long", "ofthe_long_pm", "long_share"]].mean().round(4).to_string())
    print("\n== statement leak (2027): AI-use prose in the 600 chars before the heading:",
          round(d[d.year == 2027].leak_before_heading.mean(), 3))


if __name__ == "__main__":
    main()
