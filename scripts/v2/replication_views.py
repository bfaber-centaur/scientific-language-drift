"""Lane B (V2 replication): build count_ngrams-format "views" from one V2 count run with composite strata.

Usage:
    python3 scripts/v2/replication_views.py SRC OUT VIEW [--ns 1 2 3]

SRC is a count_ngrams.py output directory made with --flags results/v2/replication/flags_v2.csv.gz,
whose strata are "<version>|<member>|<id group>" (scripts/v2/replication_flags.py). OUT receives the
files scripts/longitudinal.py and scripts/make_tables.py read (ngrams_n{n}.parquet,
ngrams_n{n}_by_stratum.parquet with strata collapsed to the version, totals.csv,
totals_by_stratum.csv, run.json), restricted to the records the view selects:

    v1repro   V1 records only, ICLR 2025 restricted to the 0-P id stratum. This is V1's population and
              V1's definitions; it must reproduce the V1 tables (results/full/body) exactly.
    v2def     every V2 record, V1's definitions unchanged (ICLR 2025 still restricted to 0-P).
              v2def - v1repro = the effect of the added records alone.
    v2main    every V2 record, ICLR 2025 = the whole year minus the 140 title-slug ids (now that the
              year is 99.5% complete, the 0-P restriction is no longer needed). v2main - v2def = the
              one methodological change (a sensitivity analysis, not a redefinition).
    add2024   v1repro plus the records added to 2024 only (waterfall step)
    add2026   v1repro plus the records added to 2024 and 2026 (waterfall step)
    published / under_review stratum views of the above come for free: longitudinal.py reads the
    collapsed by-stratum table.
    member:v1 / member:added  any year, one membership only (all id strata except title-slug).

Counts are exact for every n-gram kept in SRC (df >= min_df in at least one year of the full run),
which is a superset of what each view would keep on its own, so top-k tables and change tables, which
need df >= 20, are unaffected. distinct_ngrams in totals.csv counts kept n-grams only.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil

import duckdb
import pandas as pd

VIEWS = {
    # (sql predicate on year, member, idg) where idg is the third stratum field
    "v1repro": "member = 'v1' AND (year <> 2025 OR idg = '0-P')",
    "v2def": "(year <> 2025 OR idg = '0-P')",
    "v2main": "(year <> 2025 OR idg <> 'nonstandard_id')",
    "add2024": "(member = 'v1' OR year = 2024) AND (year <> 2025 OR idg = '0-P')",
    "add2026": "(member = 'v1' OR year IN (2024, 2026)) AND (year <> 2025 OR idg = '0-P')",
    "member:v1": "member = 'v1' AND idg <> 'nonstandard_id'",
    "member:added": "member = 'added' AND idg <> 'nonstandard_id'",
}

SPLIT = """split_part(stratum, '|', 1) AS version, split_part(stratum, '|', 2) AS member,
           split_part(stratum, '|', 3) AS idg"""


def build(src: str, out: str, view: str, ns=(1, 2, 3), tmp: str | None = None) -> None:
    pred = VIEWS[view]
    os.makedirs(out, exist_ok=True)
    con = duckdb.connect()
    con.execute(f"SET temp_directory='{tmp or os.path.join(out, '_duck')}'")
    con.execute("SET memory_limit='8GB'")
    con.execute("SET preserve_insertion_order=false")
    docs = os.path.join(src, "docs.parquet")
    con.execute(f"CREATE TABLE d AS SELECT *, {SPLIT} FROM '{docs}'")
    con.execute(f"CREATE TABLE dv AS SELECT * FROM d WHERE {pred}")
    tot, tots = [], []
    for n in ns:
        f = os.path.join(src, f"ngrams_n{n}_by_stratum.parquet")
        if not os.path.exists(f):
            continue
        con.execute(f"""CREATE OR REPLACE TABLE s AS
            SELECT year, version, ngram, SUM(count)::BIGINT AS count, SUM(df)::BIGINT AS df
            FROM (SELECT year, ngram, count, df, {SPLIT} FROM '{f}') WHERE {pred}
            GROUP BY year, version, ngram""")
        con.execute(f"""CREATE OR REPLACE TABLE ts AS
            SELECT year, version AS stratum, {n} AS n, COUNT(*) AS docs, SUM(tokens) AS tokens,
                   SUM(positions_{n}) AS positions FROM dv GROUP BY year, version""")
        con.execute(f"""COPY (SELECT s.year, s.version AS stratum, s.ngram, s.count, s.df, ts.docs, ts.positions
            FROM s JOIN ts ON s.year = ts.year AND s.version = ts.stratum
            ORDER BY s.year, stratum, s.count DESC, s.ngram)
            TO '{os.path.join(out, f"ngrams_n{n}_by_stratum.parquet")}' (FORMAT parquet)""")
        con.execute("""CREATE OR REPLACE TABLE g AS SELECT year, ngram, SUM(count)::BIGINT AS count,
            SUM(df)::BIGINT AS df FROM s GROUP BY year, ngram HAVING SUM(count) > 0""")
        con.execute(f"""CREATE OR REPLACE TABLE t AS SELECT year, {n} AS n, COUNT(*) AS docs,
            SUM(tokens) AS tokens, SUM(positions_{n}) AS positions FROM dv GROUP BY year""")
        con.execute(f"""COPY (SELECT g.year, g.ngram, g.count, g.df, t.docs, t.positions,
                   1e6 * g.count / t.positions AS per_million, g.df / t.docs AS prevalence
            FROM g JOIN t USING (year) ORDER BY g.year, g.count DESC, g.ngram)
            TO '{os.path.join(out, f"ngrams_n{n}.parquet")}' (FORMAT parquet)""")
        tot.append(con.execute("""SELECT t.*, (SELECT COUNT(*) FROM g WHERE g.year = t.year) AS distinct_ngrams
            FROM t ORDER BY year""").df())
        tots.append(con.execute("SELECT * FROM ts ORDER BY year, stratum").df())
    pd.concat(tot).to_csv(os.path.join(out, "totals.csv"), index=False)
    pd.concat(tots).to_csv(os.path.join(out, "totals_by_stratum.csv"), index=False)
    run = json.load(open(os.path.join(src, "run.json")))
    run.update({"view": view, "view_predicate": pred, "view_source": os.path.abspath(src),
                "docs": int(con.execute("SELECT COUNT(*) FROM dv").fetchone()[0])})
    run["docs_in_sample"] = run["docs"]
    run["ns"] = [n for n in ns if os.path.exists(os.path.join(src, f"ngrams_n{n}_by_stratum.parquet"))]
    json.dump(run, open(os.path.join(out, "run.json"), "w"), indent=2)
    con.execute(f"COPY (SELECT doc_id, venue, year, stratum FROM dv) TO '{os.path.join(out, 'docs.parquet')}' (FORMAT parquet)")
    shutil.rmtree(os.path.join(out, "_duck"), ignore_errors=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("view", choices=sorted(VIEWS))
    ap.add_argument("--ns", type=int, nargs="+", default=[1, 2, 3])
    a = ap.parse_args()
    build(a.src, a.out, a.view, a.ns)
    print("wrote", a.out)


if __name__ == "__main__":
    main()
