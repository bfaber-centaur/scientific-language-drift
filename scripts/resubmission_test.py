"""Paired test: does the same paper's prose change when it is resubmitted?

Usage: python3 scripts/resubmission_test.py

Uses the cross-year near-duplicate pairs from results/duplicates_iclr.csv (mostly
rejected papers resubmitted the next year; found by recon.py). For each pair,
measures both versions' main body (statement sections cut, same tokenizer):
stopword share, "of the" per million bigram positions, and the presence of
marker phrases. If the ICLR 2027 shift were only a change in WHO submits,
papers resubmitted into 2027 would keep their earlier style; if it is revision
(by authors or their tools), their 2027 versions move with the cohort.
Control: pairs resubmitted between earlier years (2024->2025, 2025->2026).

Writes results/resubmission_pairs.csv (per pair, ids and measures only) and
results/resubmission_summary.csv (per transition: mean before/after, mean paired
difference with a bootstrap 95% CI over pairs).
"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.count import ngrams_of  # noqa: E402
from mlngrams.filters import STOPWORDS  # noqa: E402
from mlngrams.load import fetch, main_body  # noqa: E402
from mlngrams.sections import strip_statements  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..")
PHRASES = ["we propose", "a novel", "in this paper", "state-of-the-art", "leverage", "notably",
           "underscores", "delve", "crucial", "test whether", "held fixed", "results support"]
TRANSITIONS = [(2024, 2025), (2025, 2026), (2025, 2027), (2026, 2027)]


def measures(text: str) -> dict:
    segs = tokenize(strip_statements(main_body(text))[0])
    toks = [w for s in segs for w in s]
    bis = list(ngrams_of(segs, 2))
    flat = " " + " ".join(" ".join(s) for s in segs) + " "
    m = {
        "tokens": len(toks),
        "stop_share": sum(w in STOPWORDS for w in toks) / max(1, len(toks)),
        "of_the_pm": 1e6 * bis.count("of the") / max(1, len(bis)),
    }
    for p in PHRASES:
        m[p] = f" {p}" in flat  # prefix match: "leverage" also counts "leverages"
    return m


def load_texts(year: int, ids: set[str]) -> dict[str, str]:
    out = {}
    pf = pq.ParquetFile(fetch("omissions", "iclr", year))
    for b in pf.iter_batches(batch_size=500, columns=["paper_id", "text"]):
        for r in b.to_pylist():
            if r["paper_id"] in ids:
                out[r["paper_id"]] = r["text"]
    return out


def boot_ci(x: np.ndarray, reps: int = 2000, seed: int = 0) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    means = [rng.choice(x, size=len(x)).mean() for _ in range(reps)]
    return float(np.percentile(means, 2.5)), float(np.percentile(means, 97.5))


def main():
    d = pd.read_csv(os.path.join(ROOT, "results", "duplicates_iclr.csv"))
    d = d[d.year_a != d.year_b]
    rows = []
    for ya, yb in TRANSITIONS:
        p = d[(d.year_a == ya) & (d.year_b == yb)].drop_duplicates(["paper_id_a", "paper_id_b"])
        ta = load_texts(ya, set(p.paper_id_a))
        tb = load_texts(yb, set(p.paper_id_b))
        for r in p.itertuples():
            if r.paper_id_a not in ta or r.paper_id_b not in tb:
                continue
            ma, mb = measures(ta[r.paper_id_a]), measures(tb[r.paper_id_b])
            if min(ma["tokens"], mb["tokens"]) < 500:
                continue
            row = {"transition": f"{ya}->{yb}", "paper_id_a": r.paper_id_a, "paper_id_b": r.paper_id_b}
            row.update({f"{k}_a": v for k, v in ma.items()})
            row.update({f"{k}_b": v for k, v in mb.items()})
            rows.append(row)
        print(ya, yb, "pairs", sum(x["transition"] == f"{ya}->{yb}" for x in rows), flush=True)
    pairs = pd.DataFrame(rows)
    pairs.to_csv(os.path.join(ROOT, "results", "resubmission_pairs.csv"), index=False)
    summ = []
    for t, g in pairs.groupby("transition"):
        for k in ["stop_share", "of_the_pm"] + PHRASES:
            a, b = g[f"{k}_a"].astype(float).to_numpy(), g[f"{k}_b"].astype(float).to_numpy()
            lo, hi = boot_ci(b - a)
            summ.append({"transition": t, "pairs": len(g), "measure": k, "mean_a": a.mean(),
                         "mean_b": b.mean(), "mean_diff": (b - a).mean(), "ci_lo": lo, "ci_hi": hi})
    s = pd.DataFrame(summ)
    s.to_csv(os.path.join(ROOT, "results", "resubmission_summary.csv"), index=False, float_format="%.4g")
    print(s.to_string(index=False, float_format=lambda v: f"{v:.3f}"))


if __name__ == "__main__":
    main()
