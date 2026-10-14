"""Count word n-grams per (venue, year) with explicit denominators.

Usage:
    python3 scripts/count_ngrams.py --years 2018 2020 2024 2026 --out data/pilot
    python3 scripts/count_ngrams.py --years 2017-2027 --out data/full
Options: --config omissions|clean, --body-only (drop text after the first
reference-list marker, i.e. appendices), --min-df (pruning of the per-year
tables only; totals are never pruned), --workers.

Outputs in --out:
    docs.parquet          one row per counted paper: ids, year, tokens, positions per n
                          (no text). Exact duplicates (same text_sha256) are skipped
                          and listed in duplicates.csv.
    totals.csv            docs / tokens / positions / distinct n-grams per (year, n)
    ngrams_n{n}.parquet   year, ngram, count, df, docs, positions, per_million, prevalence
                          for n-grams with df >= min_df in that year
    run.json              arguments, dataset revision, tokenizer and filter versions

Exact counting: workers count chunks of papers; partial counts are written as
parquet and merged with DuckDB (which spills to disk), so memory stays bounded.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
from collections import Counter
from concurrent.futures import ProcessPoolExecutor

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pandas as pd  # noqa: E402

from mlngrams import filters, tokenize  # noqa: E402
from mlngrams.count import ngrams_of  # noqa: E402
from mlngrams.load import REVISION, iter_docs, main_body  # noqa: E402

NS = (1, 2, 3)


def parse_years(spec: list[str]) -> list[int]:
    out = []
    for s in spec:
        if "-" in s:
            a, b = map(int, s.split("-"))
            out += list(range(a, b + 1))
        else:
            out.append(int(s))
    return out


def count_chunk(args):
    docs, body_only = args
    counts = {n: Counter() for n in NS}
    dfs = {n: Counter() for n in NS}
    rows = []
    for d in docs:
        text = main_body(d["text"]) if body_only else d["text"]
        segs = tokenize.tokenize(text)
        row = {k: d[k] for k in ("doc_id", "venue", "year", "pdf_sha256", "text_sha256")}
        row["chars"] = len(text)
        row["tokens"] = sum(len(s) for s in segs)
        for n in NS:
            c = Counter(ngrams_of(segs, n))
            counts[n].update(c)
            dfs[n].update(c.keys())
            row[f"positions_{n}"] = sum(c.values())
        rows.append(row)
    return rows, counts, dfs


def chunks(it, size):
    buf = []
    for x in it:
        buf.append(x)
        if len(buf) == size:
            yield buf
            buf = []
    if buf:
        yield buf


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="iclr")
    ap.add_argument("--years", nargs="+", required=True)
    ap.add_argument("--config", default="omissions")
    ap.add_argument("--body-only", action="store_true")
    ap.add_argument("--min-df", type=int, default=3)
    ap.add_argument("--chunk", type=int, default=400)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    years = parse_years(a.years)
    os.makedirs(a.out, exist_ok=True)
    part_dir = os.path.join(a.out, "_parts")
    shutil.rmtree(part_dir, ignore_errors=True)
    os.makedirs(part_dir)

    seen: dict[str, str] = {}
    dups = []
    doc_rows = []
    t0 = time.time()

    def unique_docs(year):
        for d in iter_docs(a.config, a.venue, year):
            h = d["text_sha256"]
            if not d["text"] or not d["text"].strip():
                dups.append({"doc_id": d["doc_id"], "year": year, "reason": "empty_text", "same_as": ""})
                continue
            if h in seen:
                dups.append({"doc_id": d["doc_id"], "year": year, "reason": "duplicate_text", "same_as": seen[h]})
                continue
            seen[h] = d["doc_id"]
            yield d

    part = 0
    with ProcessPoolExecutor(a.workers) as ex:
        for year in years:
            jobs = ((c, a.body_only) for c in chunks(unique_docs(year), a.chunk))
            for rows, counts, dfs in ex.map(count_chunk, jobs):
                doc_rows += rows
                for n in NS:
                    pd.DataFrame(
                        {
                            "year": year,
                            "ngram": list(counts[n].keys()),
                            "count": list(counts[n].values()),
                            "df": [dfs[n][k] for k in counts[n]],
                        }
                    ).to_parquet(os.path.join(part_dir, f"n{n}_{part:05d}.parquet"), index=False)
                part += 1
            print(f"{year}: done, {len(doc_rows)} docs total, {time.time() - t0:.0f}s", flush=True)

    docs = pd.DataFrame(doc_rows)
    docs.to_parquet(os.path.join(a.out, "docs.parquet"), index=False)
    pd.DataFrame(dups, columns=["doc_id", "year", "reason", "same_as"]).to_csv(
        os.path.join(a.out, "duplicates.csv"), index=False
    )

    import duckdb

    con = duckdb.connect()
    con.execute(f"SET temp_directory='{os.path.join(a.out, '_duck')}'")
    con.execute("SET memory_limit='8GB'")
    con.register("docs", docs)
    tot_rows = []
    for n in NS:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE g AS
            SELECT year, ngram, SUM(count)::BIGINT AS count, SUM(df)::BIGINT AS df
            FROM read_parquet('{part_dir}/n{n}_*.parquet') GROUP BY year, ngram
            """
        )
        t = con.execute(
            f"""
            SELECT d.year, {n} AS n, COUNT(*) AS docs, SUM(d.tokens) AS tokens,
                   SUM(d.positions_{n}) AS positions,
                   (SELECT COUNT(*) FROM g WHERE g.year = d.year) AS distinct_ngrams
            FROM docs d GROUP BY d.year ORDER BY d.year
            """
        ).df()
        tot_rows.append(t)
        con.execute(
            f"""
            COPY (
              SELECT g.year, g.ngram, g.count, g.df, t.docs, t.positions,
                     1e6 * g.count / t.positions AS per_million, g.df / t.docs AS prevalence
              FROM g JOIN (SELECT year, COUNT(*) AS docs, SUM(positions_{n}) AS positions
                           FROM docs GROUP BY year) t USING (year)
              WHERE g.df >= {a.min_df}
              ORDER BY g.year, g.count DESC, g.ngram
            ) TO '{os.path.join(a.out, f"ngrams_n{n}.parquet")}' (FORMAT parquet)
            """
        )
        print(f"n={n}: merged, {time.time() - t0:.0f}s", flush=True)
    pd.concat(tot_rows).to_csv(os.path.join(a.out, "totals.csv"), index=False)
    shutil.rmtree(part_dir)
    shutil.rmtree(os.path.join(a.out, "_duck"), ignore_errors=True)
    json.dump(
        {
            "venue": a.venue,
            "years": years,
            "config": a.config,
            "body_only": a.body_only,
            "min_df": a.min_df,
            "revision": REVISION,
            "tokenizer": tokenize.TOKENIZER_VERSION,
            "filter": filters.FILTER_VERSION,
            "docs": len(docs),
            "skipped": len(dups),
            "seconds": round(time.time() - t0),
        },
        open(os.path.join(a.out, "run.json"), "w"),
        indent=2,
    )


if __name__ == "__main__":
    main()
