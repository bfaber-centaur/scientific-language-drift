"""Gate 0/1: old/new inventory matrix and record-level change classification.

Consumes the metadata written by scripts/v2/collect_metadata.py (no paper text) and writes
small derived tables to results/v2/inventory/:

    matrix.csv            venue x year: old/new rows, card totals, coverage, file status per config
    record_changes.csv    venue x year: counts of retained / re-extracted / pdf_replaced / added /
                          removed / moved records, per config
    membership.csv.gz     one row per paper_id x venue-year in either revision: status (omissions
                          config; the clean and direct classifications are identical). Hashes are
                          omitted to keep it small; rejoin from collect_metadata output if needed.
    added_vs_retained.csv venue x year: length and omission profile of retained vs added records
    id_prefix_new.csv     ICLR 2024-2026: first-character strata of paper_id, old vs new counts
    duplicates_new.csv    duplicate paper_id / pdf_sha256 / text_sha256 groups in the new revision
    title_coverage.csv    share of rows with a non-null title, per venue-year and revision

Record status (keyed by paper_id within venue-year; pdf_sha256 is the dataset's row key):
    retained      same paper_id, same pdf_sha256, same text_sha256 in the config
    re_extracted  same paper_id, same pdf_sha256, different text_sha256
    pdf_replaced  same paper_id, different pdf_sha256 (a different PDF version)
    added         paper_id only in the new revision
    removed       paper_id only in the old revision
    moved         paper_id present in both revisions but in a different venue-year
"""
from __future__ import annotations

import argparse
import json
import os
import re

import pandas as pd

ROOT = os.path.join(os.path.dirname(__file__), "..", "..")
CONFIGS = ("omissions", "clean", "direct")
CARD_ROW = re.compile(r"^\|\s*(\w+)\s*\|\s*(\d{4})\s*\|\s*([\d,]+) \(([\d.]+)%\)\s*\|\s*([\d,]+)\s*\|", re.M)


def card_table(path: str) -> pd.DataFrame:
    rows = [{"venue": v.lower(), "year": int(y), "card_extracted": int(e.replace(",", "")),
             "card_pct": float(p), "card_total": int(t.replace(",", ""))}
            for v, y, e, p, t in CARD_ROW.findall(open(path).read())]
    return pd.DataFrame(rows)


def load_meta(meta: str, rev7: str, cfg: str) -> pd.DataFrame:
    d = os.path.join(meta, rev7, cfg)
    parts = []
    for f in sorted(os.listdir(d)):
        if f.endswith(".parquet"):
            df = pd.read_parquet(os.path.join(d, f))
            venue, year = f[:-8].rsplit("-", 1)
            df["file_venue"], df["file_year"] = venue, int(year)
            parts.append(df)
    return pd.concat(parts, ignore_index=True)


def classify(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    key = ["file_venue", "file_year", "paper_id"]
    cols = key + ["pdf_sha256", "text_sha256"]
    m = old[cols].merge(new[cols], on=key, how="outer", suffixes=("_old", "_new"), indicator=True)
    st = pd.Series("retained", index=m.index)
    st[m._merge == "left_only"] = "removed"
    st[m._merge == "right_only"] = "added"
    both = m._merge == "both"
    st[both & (m.pdf_sha256_old != m.pdf_sha256_new)] = "pdf_replaced"
    st[both & (m.pdf_sha256_old == m.pdf_sha256_new) & (m.text_sha256_old != m.text_sha256_new)] = "re_extracted"
    m["status"] = st
    # Cross-file moves: an "added" id that was "removed" from another venue-year.
    gone = set(m.loc[m.status == "removed", "paper_id"])
    came = set(m.loc[m.status == "added", "paper_id"])
    moved = gone & came
    m.loc[m.paper_id.isin(moved) & m.status.isin(["added", "removed"]), "status"] = "moved"
    return m.drop(columns="_merge")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", default=os.path.join(ROOT, "data", "v2", "meta"))
    ap.add_argument("--old", default="cb5553e")
    ap.add_argument("--new", default="2c0dd19")
    ap.add_argument("--card-old", required=True, help="dataset README.md at the old revision")
    ap.add_argument("--card-new", required=True, help="dataset README.md at the new revision")
    a = ap.parse_args()
    out = os.path.join(ROOT, "results", "v2", "inventory")
    os.makedirs(out, exist_ok=True)

    files = pd.read_csv(os.path.join(out, "files.csv"))
    files = files[files.path.str.endswith(".parquet")].copy()
    files["config"] = files.path.str.split("/").str[0]
    files["stem"] = files.path.str.split("/").str[1].str.removesuffix(".parquet")
    files["venue"] = files.stem.str.rsplit("-", n=1).str[0]
    files["year"] = files.stem.str.rsplit("-", n=1).str[1].astype(int)
    files["rev7"] = files.revision.str[:7]

    # --- matrix --------------------------------------------------------------------------
    piv = files.pivot_table(index=["venue", "year", "config"], columns="rev7",
                            values=["rows", "blob"], aggfunc="first")
    rows = []
    for (venue, year, cfg), r in piv.iterrows():
        bo, bn = r.get(("blob", a.old)), r.get(("blob", a.new))
        status = ("added" if pd.isna(bo) else "removed" if pd.isna(bn)
                  else "unchanged" if bo == bn else "changed")
        rows.append({"venue": venue, "year": year, "config": cfg, "file_status": status,
                     "rows_old": r.get(("rows", a.old)), "rows_new": r.get(("rows", a.new))})
    mat = pd.DataFrame(rows)
    wide = mat[mat.config == "omissions"].drop(columns="config").copy()
    agree = mat.groupby(["venue", "year"]).agg(
        file_status_all_configs=("file_status", lambda s: "/".join(sorted(set(s)))),
        rows_new_min=("rows_new", "min"), rows_new_max=("rows_new", "max"))
    wide = wide.merge(agree, on=["venue", "year"])
    co, cn = card_table(a.card_old), card_table(a.card_new)
    wide = (wide.merge(co.add_suffix("_old").rename(columns={"venue_old": "venue", "year_old": "year"}),
                       on=["venue", "year"], how="outer")
                .merge(cn.add_suffix("_new").rename(columns={"venue_new": "venue", "year_new": "year"}),
                       on=["venue", "year"], how="outer"))
    wide["rows_old"] = wide.rows_old.fillna(0).astype(int)
    wide["rows_new"] = wide.rows_new.fillna(0).astype(int)
    wide["coverage_old_pct"] = (100 * wide.rows_old / wide.card_total_new).round(1)
    wide["coverage_new_pct"] = (100 * wide.rows_new / wide.card_total_new).round(1)
    wide["file_status"] = wide.file_status.fillna("absent")
    wide = wide.sort_values(["venue", "year"])
    wide.to_csv(os.path.join(out, "matrix.csv"), index=False)

    # --- record level --------------------------------------------------------------------
    counts, status_frames, prof = [], [], []
    for cfg in CONFIGS:
        old, new = load_meta(a.meta, a.old, cfg), load_meta(a.meta, a.new, cfg)
        m = classify(old, new)
        m["config"] = cfg
        status_frames.append(m)
        c = m.groupby(["file_venue", "file_year", "status"]).size().unstack(fill_value=0)
        c["config"] = cfg
        counts.append(c.reset_index())
        if cfg == "omissions":
            # label/filename and within-file consistency checks
            bad_label = new[(new.conference != new.file_venue) | (new.year != new.file_year)]
            print("new rows whose conference/year column disagrees with the filename:", len(bad_label))
            nm = new.merge(m[["file_venue", "file_year", "paper_id", "status"]],
                           on=["file_venue", "file_year", "paper_id"], how="left")
            oc = nm.omission_counts_json.map(json.loads)
            for k in ("references", "math_display", "figure", "table"):
                nm["om_" + k] = oc.map(lambda d, k=k: d.get(k, 0))
            nm["om_ratio"] = nm.chars_after / nm.chars_clean.where(nm.chars_clean > 0)
            nm["slug_id"] = ~nm.paper_id.str.fullmatch(r"[A-Za-z0-9_\-]{8,12}") | nm.paper_id.str.contains("_.*_")
            g = nm.groupby(["file_venue", "file_year", "status"])
            prof = g.agg(n=("paper_id", "size"), chars_median=("chars_after", "median"),
                         chars_p10=("chars_after", lambda s: s.quantile(.1)),
                         chars_p90=("chars_after", lambda s: s.quantile(.9)),
                         ref_pages_mean=("om_references", "mean"), tables_mean=("om_table", "mean"),
                         eq_mean=("om_math_display", "mean"), figs_mean=("om_figure", "mean"),
                         omitted_share_median=("om_ratio", lambda s: 1 - s.median()),
                         title_nonnull=("title", lambda s: s.notna().mean()),
                         slug_ids=("slug_id", "sum")).reset_index()
            prof.to_csv(os.path.join(out, "added_vs_retained.csv"), index=False)
            # ICLR id-prefix strata, old vs new
            ic = nm[(nm.file_venue == "iclr") & nm.file_year.isin([2024, 2025, 2026])].copy()
            ic["first"] = ic.paper_id.str[0]
            ic["stratum"] = ic["first"].map(lambda ch: "0-P" if ch <= "P" else "Q-z")
            ic.loc[ic.slug_id, "stratum"] = "title_slug"
            ic["in_old"] = ic.status.isin(["retained", "re_extracted", "pdf_replaced"])
            ip = ic.groupby(["file_year", "stratum"]).agg(new=("paper_id", "size"), old=("in_old", "sum")).reset_index()
            ip.to_csv(os.path.join(out, "id_prefix_new.csv"), index=False)
            # duplicates in the new revision
            dups = []
            for col in ("paper_id", "pdf_sha256", "text_sha256"):
                sizes = new.groupby(col).size()
                for k in sizes[sizes > 1].index:
                    sub = new[new[col] == k]
                    dups.append({"key": col, "value": k, "n": len(sub),
                                 "where": ";".join(sorted(f"{v}-{y}" for v, y in zip(sub.file_venue, sub.file_year))),
                                 "paper_ids": ";".join(sorted(sub.paper_id.astype(str)))})
            pd.DataFrame(dups).to_csv(os.path.join(out, "duplicates_new.csv"), index=False)
            tc = pd.concat([old.assign(rev=a.old), new.assign(rev=a.new)])
            tc.groupby(["rev", "file_venue", "file_year"]).title.apply(lambda s: round(s.notna().mean(), 3)) \
              .unstack(0).reset_index().to_csv(os.path.join(out, "title_coverage.csv"), index=False)
    cnt = pd.concat(counts, ignore_index=True).fillna(0)
    for k in ("retained", "re_extracted", "pdf_replaced", "added", "removed", "moved"):
        if k not in cnt:
            cnt[k] = 0
        cnt[k] = cnt[k].astype(int)
    cnt = cnt[["config", "file_venue", "file_year", "retained", "re_extracted", "pdf_replaced",
               "added", "removed", "moved"]].rename(columns={"file_venue": "venue", "file_year": "year"})
    cnt.to_csv(os.path.join(out, "record_changes.csv"), index=False)
    st = pd.concat(status_frames, ignore_index=True)
    key = ["file_venue", "file_year", "paper_id", "status"]
    om = st[st.config == "omissions"][key]
    for cfg in ("clean", "direct"):
        other = st[st.config == cfg][key]
        same = om.sort_values(key).reset_index(drop=True).equals(other.sort_values(key).reset_index(drop=True))
        print(f"{cfg}: status table identical to omissions: {same}")
    om.rename(columns={"file_venue": "venue", "file_year": "year"}).sort_values(["venue", "year", "paper_id"]) \
      .to_csv(os.path.join(out, "membership.csv.gz"), index=False)
    print(cnt.groupby("config")[["retained", "re_extracted", "pdf_replaced", "added", "removed", "moved"]].sum())


if __name__ == "__main__":
    main()
