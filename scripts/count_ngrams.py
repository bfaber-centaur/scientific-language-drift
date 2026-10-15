"""Count word n-grams per (venue, year) with explicit denominators.

Usage:
    python3 scripts/count_ngrams.py --years 2018 2020 2024 2026 --out data/pilot
    python3 scripts/count_ngrams.py --years 2017-2027 --out data/full
Options: --config omissions|clean, --body-only (drop text after the first
reference-list marker, i.e. appendices), --keep-statements (do not cut template
statement sections, see mlngrams.sections), --min-df, --workers.

Outputs in --out:
    docs.parquet          one row per counted paper: ids, year, tokens, positions per n
                          (no text). Exact duplicates (same text_sha256) are skipped
                          and listed in duplicates.csv.
    totals.csv            docs / tokens / positions / distinct n-grams per (year, n)
    totals_by_stratum.csv the same per (year, stratum, n)
    ngrams_n{n}_by_stratum.parquet  year, stratum, ngram, count, df, docs, positions
                          for the same n-grams as ngrams_n{n}.parquet
    ngrams_n{n}.parquet   year, ngram, count, df, docs, positions, per_million, prevalence
                          for every n-gram with df >= min_df in AT LEAST ONE year; its
                          rows for the other years are exact (unpruned), and a missing
                          (year, ngram) row means a true count of 0.
    run.json              arguments, dataset revision, tokenizer and filter versions

Strata and exclusions come from results/paper_flags_iclr.csv (scripts/paper_flags.py), or from
a V2 flags file with a `stratum` column (scripts/v2/replication_flags.py), whose strata are used
as given (V2 views are built from them by scripts/v2/replication_views.py):
stratum = version (published | under_review | unknown), with suffix "|offsample" for
papers whose in_sample flag is False (biased part of ICLR 2025). Year-level tables
and totals use in-sample papers only; stratified tables keep every stratum. Papers
with a non-empty `exclude` flag (short, template) are skipped and listed in
duplicates.csv with that reason. --flags none disables flags (stratum "all").

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

from mlngrams import filters, sections, tokenize  # noqa: E402
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
    docs, body_only, keep_statements = args
    counts = {n: Counter() for n in NS}
    dfs = {n: Counter() for n in NS}
    rows = []
    for d in docs:
        text = d["text"]
        removed = 0
        if not keep_statements:
            text, removed = sections.strip_statements(text)
        if body_only:
            text = main_body(text)
        segs = tokenize.tokenize(text)
        row = {k: d[k] for k in ("doc_id", "venue", "year", "pdf_sha256", "text_sha256")}
        row["chars"] = len(text)
        row["statement_chars"] = removed
        row["stratum"] = d.get("stratum", "all")
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


def chunks_by_stratum(it, size):
    """Chunks whose documents all share one stratum."""
    bufs: dict[str, list] = {}
    for x in it:
        b = bufs.setdefault(x["stratum"], [])
        b.append(x)
        if len(b) == size:
            yield bufs.pop(x["stratum"])
    yield from (b for b in bufs.values() if b)


def bounded_map(ex, fn, jobs, window):
    """Like ex.map, but only `window` chunks are in flight, so texts are not all read up front."""
    from collections import deque

    pending = deque()
    for job in jobs:
        pending.append(ex.submit(fn, job))
        if len(pending) >= window:
            yield pending.popleft().result()
    while pending:
        yield pending.popleft().result()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--venue", default="iclr")
    ap.add_argument("--years", nargs="+", required=True)
    ap.add_argument("--config", default="omissions")
    ap.add_argument("--body-only", action="store_true")
    ap.add_argument("--keep-statements", action="store_true")
    ap.add_argument("--min-df", type=int, default=3)
    ap.add_argument("--chunk", type=int, default=400)
    ap.add_argument("--workers", type=int, default=os.cpu_count())
    ap.add_argument("--out", required=True)
    ap.add_argument("--ns", type=int, nargs="+", default=list(NS), help="n-gram orders to merge and write")
    ap.add_argument("--merge-only", action="store_true",
                    help="skip counting; merge existing --out/_parts and docs.parquet (after a failed merge)")
    ap.add_argument("--flags", default=os.path.join(os.path.dirname(__file__), "..", "results", "paper_flags_iclr.csv"))
    a = ap.parse_args()
    years = parse_years(a.years)
    os.makedirs(a.out, exist_ok=True)
    part_dir = os.path.join(a.out, "_parts")
    if a.merge_only:
        for n in a.ns:
            for suffix in ("", "_by_stratum"):
                f = os.path.join(a.out, f"ngrams_n{n}{suffix}.parquet")
                if os.path.exists(f):
                    os.remove(f)
    else:
        for f in os.listdir(a.out):  # never leave outputs of an earlier run next to this one
            if f.endswith((".parquet", ".csv", ".json")):
                os.remove(os.path.join(a.out, f))
        shutil.rmtree(part_dir, ignore_errors=True)
        os.makedirs(part_dir)

    flags = {}
    if a.flags != "none" and os.path.exists(a.flags):
        f = pd.read_csv(a.flags, keep_default_na=False)
        if "venue" in f.columns:  # V2 flags cover every venue (scripts/v2/replication_flags.py)
            f = f[f.venue == a.venue]
        flags = {(int(r.year), r.doc_id): r for r in f.itertuples()}

    seen: dict[str, str] = {}
    dups = []
    doc_rows = []
    t0 = time.time()

    def unique_docs(year):
        for d in iter_docs(a.config, a.venue, year):
            h = d["text_sha256"]
            fl = flags.get((year, d["doc_id"]))
            if fl is not None and fl.exclude:
                dups.append({"doc_id": d["doc_id"], "year": year, "reason": fl.exclude, "same_as": ""})
                continue
            if not flags:
                d["stratum"] = "all"
            elif fl is None:
                d["stratum"] = "unknown"
            elif hasattr(fl, "stratum"):  # V2 flags carry a precomputed composite stratum
                d["stratum"] = fl.stratum
            else:
                d["stratum"] = fl.version + ("" if str(fl.in_sample) == "True" else "|offsample")
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
        for year in [] if a.merge_only else years:
            jobs = ((c, a.body_only, a.keep_statements) for c in chunks_by_stratum(unique_docs(year), a.chunk))
            for rows, counts, dfs in bounded_map(ex, count_chunk, jobs, 2 * a.workers):
                doc_rows += rows
                for n in NS:
                    pd.DataFrame(
                        {
                            "year": year,
                            "stratum": rows[0]["stratum"],
                            "ngram": list(counts[n].keys()),
                            "count": list(counts[n].values()),
                            "df": [dfs[n][k] for k in counts[n]],
                        }
                    ).to_parquet(os.path.join(part_dir, f"n{n}_{part:05d}.parquet"), index=False)
                part += 1
            print(f"{year}: done, {len(doc_rows)} docs total, {time.time() - t0:.0f}s", flush=True)

    if a.merge_only:
        docs = pd.read_parquet(os.path.join(a.out, "docs.parquet"))
        dups = pd.read_csv(os.path.join(a.out, "duplicates.csv")).to_dict("records")
    else:
        docs = pd.DataFrame(doc_rows)
        docs.to_parquet(os.path.join(a.out, "docs.parquet"), index=False)
        pd.DataFrame(dups, columns=["doc_id", "year", "reason", "same_as"]).to_csv(
            os.path.join(a.out, "duplicates.csv"), index=False
        )

    import duckdb

    con = duckdb.connect()
    con.execute(f"SET temp_directory='{os.path.join(a.out, '_duck')}'")
    con.execute("SET memory_limit='8GB'")
    con.execute("SET preserve_insertion_order=false")
    con.register("docs_all", docs)
    con.execute("CREATE TABLE docs AS SELECT * FROM docs_all WHERE stratum NOT LIKE '%|offsample'")
    tot_rows, strat_rows = [], []
    for n in a.ns:
        con.execute(
            f"""
            CREATE OR REPLACE TABLE gs AS
            SELECT year, stratum, ngram, SUM(count)::BIGINT AS count, SUM(df)::BIGINT AS df
            FROM read_parquet('{part_dir}/n{n}_*.parquet') GROUP BY year, stratum, ngram
            """
        )
        con.execute(
            """
            CREATE OR REPLACE TABLE g AS
            SELECT year, ngram, SUM(count)::BIGINT AS count, SUM(df)::BIGINT AS df
            FROM gs WHERE stratum NOT LIKE '%|offsample' GROUP BY year, ngram
            """
        )
        con.execute(f"CREATE OR REPLACE TABLE keep AS SELECT DISTINCT ngram FROM g WHERE df >= {a.min_df}")
        strat_rows.append(
            con.execute(
                f"""
                SELECT year, stratum, {n} AS n, COUNT(*) AS docs, SUM(tokens) AS tokens,
                       SUM(positions_{n}) AS positions
                FROM docs_all GROUP BY year, stratum ORDER BY year, stratum
                """
            ).df()
        )
        con.execute(
            f"""
            COPY (
              SELECT gs.year, gs.stratum, gs.ngram, gs.count, gs.df, t.docs, t.positions
              FROM gs JOIN (SELECT year, stratum, COUNT(*) AS docs, SUM(positions_{n}) AS positions
                            FROM docs_all GROUP BY year, stratum) t USING (year, stratum)
              WHERE gs.ngram IN (SELECT ngram FROM keep)
              ORDER BY gs.year, gs.stratum, gs.count DESC, gs.ngram
            ) TO '{os.path.join(a.out, f"ngrams_n{n}_by_stratum.parquet")}' (FORMAT parquet)
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
              WHERE g.ngram IN (SELECT ngram FROM keep)
              ORDER BY g.year, g.count DESC, g.ngram
            ) TO '{os.path.join(a.out, f"ngrams_n{n}.parquet")}' (FORMAT parquet)
            """
        )
        print(f"n={n}: merged, {time.time() - t0:.0f}s", flush=True)
    pd.concat(tot_rows).to_csv(os.path.join(a.out, "totals.csv"), index=False)
    pd.concat(strat_rows).to_csv(os.path.join(a.out, "totals_by_stratum.csv"), index=False)
    shutil.rmtree(part_dir)
    shutil.rmtree(os.path.join(a.out, "_duck"), ignore_errors=True)
    json.dump(
        {
            "venue": a.venue,
            "years": years,
            "config": a.config,
            "body_only": a.body_only,
            "keep_statements": a.keep_statements,
            "sections": sections.SECTIONS_VERSION,
            "min_df": a.min_df,
            "ns": a.ns,
            "flags": a.flags if flags else "none",
            "revision": REVISION,
            "tokenizer": tokenize.TOKENIZER_VERSION,
            "filter": filters.FILTER_VERSION,
            "docs": len(docs),
            "docs_in_sample": int(con.execute("SELECT COUNT(*) FROM docs").fetchone()[0]),
            "skipped": len(dups),
            "seconds": round(time.time() - t0),
        },
        open(os.path.join(a.out, "run.json"), "w"),
        indent=2,
    )


if __name__ == "__main__":
    main()
