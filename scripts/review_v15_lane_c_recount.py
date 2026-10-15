"""Lane D (v1.5 review): independent recount of Lane C's headline phrase contrasts (ICLR 2027).

Usage: python3 scripts/review_v15_lane_c_recount.py <lane-b-src> <lane-b iclr2027 extract parquet> [--year-base 2026]

Groups come from Lane B's frozen classifier v2 (the object under review); everything else is reviewer code:
body = main_body() with strip_statements() v2 (Lane B's extracted disclosure span is NOT cut here), >= 1000
whitespace tokens, phrase presence by plain regex. Prints per-group n and phrase rates, the same rates within the
cue-free subset (disclosure < 400 chars), and the 2026 all-paper base rate. Writes results/review/lane_c_recount.csv.
"""
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

import pandas as pd
import pyarrow.parquet as pq

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from mlngrams.load import fetch, main_body  # noqa: E402
from mlngrams.sections import strip_statements  # noqa: E402

PH = {"we_propose": r"\bwe propose", "a_novel": r"\ba novel\b", "test_whether": r"\btests? whether",
      "held_fixed": r"\bheld fixed", "extensive_exp": r"\bextensive experiments"}
PHR = {k: re.compile(v, re.I) for k, v in PH.items()}


def feats(args):
    pid, t = args
    b = strip_statements(main_body(t or ""))[0]
    b = " ".join(b.split())
    return {"paper_id": pid, "body_tokens": len(b.split()), **{k: bool(r.search(b)) for k, r in PHR.items()}}


def bodies(year):
    pf = pq.ParquetFile(fetch("omissions", "iclr", year))
    for bt in pf.iter_batches(batch_size=256, columns=["paper_id", "text"]):
        for r in bt.to_pylist():
            yield r["paper_id"], r["text"]


def group(labels):
    # same rule as Lane B scripts/disclosures/eval_groups.py
    if labels == {"none"}:
        return "none"
    if not labels or labels == {"ambiguous"}:
        return "unknown"
    if labels == {"polish"}:
        return "polish_only"
    if "drafting" in labels:
        return "drafting"
    return "other_use"


def main():
    import mlngrams
    mlngrams.__path__.append(os.path.join(sys.argv[1], "mlngrams"))  # Lane B modules absent on the reviewer branch
    from mlngrams.disclosure_classify import classify
    ex = pd.read_parquet(sys.argv[2])
    ex = ex[ex.tier == "clean"]
    ex["group"] = [group(classify(t)["labels"]) for t in ex.text_clean]
    ex["dlen"] = ex.text_clean.str.len()
    with ProcessPoolExecutor() as pool:
        f27 = pd.DataFrame(list(pool.map(feats, bodies(2027), chunksize=64)))
        f26 = pd.DataFrame(list(pool.map(feats, bodies(2026), chunksize=64)))
    d = ex[["doc_id", "group", "dlen"]].merge(f27, left_on="doc_id", right_on="paper_id")
    d = d[d.body_tokens >= 1000]
    rows = []
    for name, sub in [("all", d), ("short_disclosure_lt400", d[d.dlen < 400])]:
        for g, x in sub.groupby("group"):
            rows.append({"subset": name, "group": g, "n": len(x), **{k: round(x[k].mean(), 3) for k in PH}})
    f26 = f26[f26.body_tokens >= 1000]
    rows.append({"subset": "iclr2026_all", "group": "all", "n": len(f26), **{k: round(f26[k].mean(), 3) for k in PH}})
    rows.append({"subset": "iclr2027_all", "group": "all", "n": len(d), **{k: round(d[k].mean(), 3) for k in PH}})
    out = pd.DataFrame(rows)
    out.to_csv(os.path.join(ROOT, "results", "review", "lane_c_recount.csv"), index=False)
    print(out.to_string())


if __name__ == "__main__":
    main()
