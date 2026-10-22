"""V3: per-paper stylistic features from corpus-linguistics methods, plus grouped unigram counts for keyness.

Text: omissions config at V3_REVISION, body only (before the first reference-list marker), template
statement sections cut (mlngrams.sections), tokenized with mlngrams.tokenize (v1.3). Features are rates
per 1,000 tokens unless named otherwise:

  hedge, booster, attitude, self_mention, engagement   Hyland (2005) interpersonal metadiscourse,
                                                       fixed single- and multi-word lists below
  hype                                                 promotional adjectives/adverbs in the spirit of
                                                       Millar, Batalo & Budgell (2022, JAMA Netw Open)
  llm_marker                                           words with excess use after 2023 in Kobak et
                                                       al. (2025, Sci Adv) and this repo's V1/V2 risers
  nominal                                              -tion/-ment/-ness/-ity/-ance/-ence nouns (>= 7
                                                       letters), Biber's informational/compressed style
  passive                                              be-form + (adverb) + participle, approximate
  mtld                                                 McCarthy & Jarvis (2010) MTLD, threshold 0.72,
                                                       mean of forward and backward passes
  mattr                                                moving-average TTR, 500-token window (Covington
                                                       & McFall 2010)
  word_len, sent_len                                   mean letters per word token; tokens per sentence
                                                       (sentences end at . ! ? before whitespace + a
                                                       capital letter, after citations and markers go)

The omissions text has no venue header, so version is not measured here. For ICLR the decision is the
proxy: accepted papers are camera-ready versions (revised after review), rejected, withdrawn and
desk-rejected papers are submission versions (checked on ICLR 2019 and 2024 against
scripts/v2/version_mix.py; docs/v3-exploration.md).

Usage: python3 scripts/v3/style_features.py --jobs 4 [--venues iclr:2017-2027 icml:2026 ...]
Writes data/v3/style/<venue>-<year>.parquet (per paper) and data/v3/style/counts_<venue>-<year>.parquet
(unigram token counts by decision group; decision from data/v3/review_meta.parquet, ICLR only).
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.load import V3_REVISION, fetch, main_body  # noqa: E402
from mlngrams.sections import strip_statements  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
OUT = os.path.join(ROOT, "data", "v3", "style")
FEATURES_VERSION = "v1"


def _set(s):
    return frozenset(s.split())


HEDGE = _set("may might could perhaps possibly possible likely unlikely probably suggest suggests suggested "
             "suggesting appear appears appeared seem seems seemed indicate indicates approximately roughly "
             "somewhat relatively potentially presumably generally typically largely partially partly arguably "
             "plausibly plausible apparently mostly usually often tend tends speculate assume assumed")
HEDGE_MW = ("to some extent", "in general", "in most cases", "it is possible", "we believe", "we hypothesize",
            "is likely to", "are likely to")
BOOSTER = _set("clearly obviously certainly definitely indeed undoubtedly demonstrate demonstrates demonstrated "
               "prove proves proved always never evidently conclusively establish establishes established "
               "substantially consistently strongly significantly dramatically decisively")
BOOSTER_MW = ("show that", "shows that", "of course", "in fact", "it is clear", "we find that", "without doubt")
ATTITUDE = _set("interestingly surprisingly importantly unfortunately remarkably notably striking strikingly "
                "unexpectedly unexpected surprising interesting important desirable appropriate inappropriate "
                "fortunately curiously crucially")
SELF = _set("we our ours us i my me")
ENGAGE = _set("you your consider recall note imagine suppose")
ENGAGE_MW = ("note that", "let us", "one can", "one may", "it is worth noting", "it should be noted")
HYPE = _set("novel unprecedented groundbreaking innovative remarkable outstanding exceptional superior crucial "
            "critical essential pivotal vital robust promising powerful compelling comprehensive extensive "
            "impressive substantial seamless seamlessly transformative paramount revolutionary state-of-the-art "
            "cutting-edge strong significant excellent effective efficient")
LLM = _set("delve delves delving underscore underscores underscoring intricate intricacies meticulous meticulously "
           "showcase showcases showcasing pivotal realm tapestry commendable notably leverage leverages leveraging "
           "seamless seamlessly nuanced multifaceted holistic crucial crucially comprehensive foster fosters "
           "garner garnered paving elucidate elucidates bolster bolsters encompass encompasses")
BE = _set("is are was were be been being")
IRREG = _set("shown given chosen taken done made seen written drawn known found built kept held set left run "
             "put brought thought led hidden")
NOMINAL = re.compile(r"^[a-z]{3,}(?:tion|tions|ment|ments|ness|nesses|ity|ities|ance|ances|ence|ences)$")
NOT_NOMINAL = _set("experiment experiments element elements environment environments moment moments comment "
                   "comments segment segments document documents government instance instances sentence "
                   "sentences evidence science sciences reference references difference differences sequence "
                   "sequences distance distances audience")
SENT_END = re.compile(r"[.!?]\s+(?=[A-Z])")
MARKER = re.compile(r"⟦[^⟧]{0,80}⟧")
CITE = re.compile(r"\((?:[^()]{0,200}?(?:19|20)\d\d[a-z]?)(?:[^()]{0,200})\)|\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")
ABBR = re.compile(r"\b(?:e\.g|i\.e|et al|Fig|Figs|Eq|Eqs|Sec|Tab|vs|cf|resp|approx|Ref|Refs|Thm|Alg|App)\.", re.I)


def mtld_pass(toks, thr=0.72):
    factors, types, n = 0.0, set(), 0
    for t in toks:
        n += 1
        types.add(t)
        if len(types) / n <= thr:
            factors += 1
            types, n = set(), 0
    if n:
        factors += (1 - len(types) / n) / (1 - thr)
    return len(toks) / factors if factors else float("nan")


def mattr(toks, w=500):
    if len(toks) < w:
        return len(set(toks)) / len(toks) if toks else float("nan")
    c = Counter(toks[:w])
    tot = len(c)
    for i in range(w, len(toks)):
        a, b = toks[i], toks[i - w]
        c[a] += 1
        if c[a] == 1:
            tot += 1
        c[b] -= 1
        if c[b] == 0:
            tot -= 1
            del c[b]
        if i % 50 == 0:  # sample every 50 positions
            _acc.append(tot / w)
    return None


_acc: list = []


def mattr_mean(toks, w=500):
    _acc.clear()
    r = mattr(toks, w)
    if r is not None:
        return r
    return sum(_acc) / len(_acc) if _acc else float("nan")


def features(text: str) -> tuple[dict, list[str]]:
    body, _ = strip_statements(main_body(text))
    segs = tokenize(body)
    toks = [t for s in segs for t in s if t != "<num>"]
    n = len(toks)
    f = {"tokens": n}
    if n < 500:
        return f, toks
    joined = " " + " ".join(" ".join(s) for s in segs) + " "
    cnt = Counter(toks)
    per = 1000.0 / n

    def rate(words, mw=()):
        return (sum(cnt[w] for w in words) + sum(joined.count(" " + p + " ") for p in mw)) * per

    f.update(hedge=rate(HEDGE, HEDGE_MW), booster=rate(BOOSTER, BOOSTER_MW), attitude=rate(ATTITUDE),
             self_mention=rate(SELF), engagement=rate(ENGAGE, ENGAGE_MW), hype=rate(HYPE), llm_marker=rate(LLM),
             nominal=sum(c for w, c in cnt.items() if NOMINAL.match(w) and w not in NOT_NOMINAL) * per)
    pas = 0
    for s in segs:
        for i in range(len(s) - 1):
            if s[i] in BE:
                j = i + 1
                if s[j].endswith("ly") and j + 1 < len(s):
                    j += 1
                w = s[j]
                if (w.endswith("ed") and len(w) > 4) or w in IRREG:
                    pas += 1
    f["passive"] = pas * per
    f["mtld"] = (mtld_pass(toks) + mtld_pass(toks[::-1])) / 2
    f["mattr"] = mattr_mean(toks)
    f["word_len"] = sum(len(t) for t in toks) / n
    prose = ABBR.sub("x", CITE.sub(" ", MARKER.sub(" ", body)))
    sents = len(SENT_END.findall(prose)) + 1
    f["sent_len"] = n / sents
    for w in ("we", "our", "novel", "propose", "delve", "notably", "however", "the", "of", "that", "which"):
        f["w_" + w] = cnt[w] * per
    return f, toks


def run(job):
    venue, year, decisions = job
    path = fetch("omissions", venue, year, V3_REVISION)
    rows, groups = [], {}
    pf = pq.ParquetFile(path)
    seen = set()
    for batch in pf.iter_batches(batch_size=128, columns=["paper_id", "text_sha256", "text"]):
        for r in batch.to_pylist():
            if r["text_sha256"] in seen:
                continue
            seen.add(r["text_sha256"])
            f, toks = features(r["text"] or "")
            f.update(doc_id=r["paper_id"], venue=venue, year=year)
            rows.append(f)
            if f["tokens"] >= 500:
                g = decisions.get(r["paper_id"], "none")
                groups.setdefault(g, Counter()).update(toks)
    pd.DataFrame(rows).to_parquet(os.path.join(OUT, f"{venue}-{year}.parquet"), index=False)
    cr = [{"decision": d, "token": t, "n": c} for d, cc in groups.items() for t, c in cc.items()
          if c >= 3]
    pd.DataFrame(cr).to_parquet(os.path.join(OUT, f"counts_{venue}-{year}.parquet"), index=False)
    return venue, year, len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--venues", nargs="+", default=["iclr:2017-2027", "icml:2026", "icml:2024",
                                                        "neurips:2025", "neurips:2023"])
    a = ap.parse_args()
    os.makedirs(OUT, exist_ok=True)
    meta = pd.read_parquet(os.path.join(ROOT, "data", "v3", "review_meta.parquet"), columns=["doc_id", "decision"])
    dec = dict(zip(meta.doc_id, meta.decision))
    jobs = []
    for spec in a.venues:
        v, yrs = spec.split(":")
        lo, _, hi = yrs.partition("-")
        for y in range(int(lo), int(hi or lo) + 1):
            if not os.path.exists(os.path.join(OUT, f"{v}-{y}.parquet")):
                jobs.append((v, y, dec if v == "iclr" else {}))
    jobs.sort(key=lambda j: -j[1] if j[0] == "iclr" else 0)  # big ICLR years first
    with ProcessPoolExecutor(a.jobs) as ex:
        for res in ex.map(run, jobs):
            print(*res, flush=True)


if __name__ == "__main__":
    main()
