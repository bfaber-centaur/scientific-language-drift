"""N-gram counting with explicit denominators.

Definitions (see README.md "Normalization"):
  * tokens(group)       = total tokens in all documents of the group.
  * positions_n(group)  = total n-gram positions = sum over segments of
                          max(0, len(segment) - n + 1). This is the denominator
                          for per-million rates of n-grams of order n.
  * count(g, x)         = occurrences of n-gram x in group g.
  * per_million(g, x)   = 1e6 * count(g, x) / positions_n(g).
  * docs(g)             = number of (deduplicated) documents in the group.
  * df(g, x)            = number of documents in g containing x at least once.
  * prevalence(g, x)    = df(g, x) / docs(g).
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

import pandas as pd

from .tokenize import TokenizerConfig, tokenize


def ngrams_of(segs: list[list[str]], n: int) -> Iterable[str]:
    for toks in segs:
        for i in range(len(toks) - n + 1):
            yield " ".join(toks[i : i + n])


def doc_counts(text: str, n: int, cfg: TokenizerConfig = TokenizerConfig()) -> tuple[Counter, int, int]:
    """Return (ngram Counter, token count, n-gram position count) for one document."""
    segs = tokenize(text, cfg)
    c = Counter(ngrams_of(segs, n))
    ntok = sum(len(s) for s in segs)
    return c, ntok, sum(c.values())


@dataclass
class GroupAccumulator:
    n: int
    count: Counter = field(default_factory=Counter)
    df: Counter = field(default_factory=Counter)
    docs: int = 0
    tokens: int = 0
    positions: int = 0

    def add(self, c: Counter, ntok: int, npos: int) -> None:
        self.count.update(c)
        self.df.update(c.keys())
        self.docs += 1
        self.tokens += ntok
        self.positions += npos

    def to_frame(self, group: str, min_df: int = 1) -> pd.DataFrame:
        """Table of n-grams with df >= min_df. Totals are NOT pruned."""
        keys = [k for k, d in self.df.items() if d >= min_df]
        df = pd.DataFrame(
            {
                "group": group,
                "ngram": keys,
                "count": [self.count[k] for k in keys],
                "df": [self.df[k] for k in keys],
            }
        )
        df["n"] = self.n
        df["docs"] = self.docs
        df["positions"] = self.positions
        df["per_million"] = 1e6 * df["count"] / max(self.positions, 1)
        df["prevalence"] = df["df"] / max(self.docs, 1)
        return df.sort_values("count", ascending=False, kind="stable").reset_index(drop=True)

    def totals(self, group: str) -> dict:
        return {
            "group": group,
            "n": self.n,
            "docs": self.docs,
            "tokens": self.tokens,
            "positions": self.positions,
            "distinct_ngrams": len(self.count),
        }
