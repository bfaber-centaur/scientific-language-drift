# V3 corpus inventory (Gate 0)

_2026-10-22, thread "V3 new data and exploration". Numbers from `results/v3/inventory/`, produced by
`scripts/v3/corpus_diff_v3.py` (reads non-text columns only)._

## Summary

- **New pin: `b9bfffba0c81927866a747d48c6c259fb42edd76`** (`mlngrams.load.V3_REVISION`, dataset commit of
  2026-10-16 00:28 UTC, still the head on 2026-10-22). V2 stays at `2c0dd192`, V1 at `cb5553e0` (default).
- Three dataset commits since V2, each "add N papers": **ICLR 2026 +67, TMLR 2023 +49, TMLR 2026 +49**,
  so 145,377 → **145,542 records (+165, +0.1%)**. ICLR 2026 is now 99.9% of the public submissions
  (19,799 / 19,814).
- **Purely additive again.** In all three configs every V2 record of the three changed files is present
  under the same `pdf_sha256` with the same `text_sha256` and `paper_id`. The 107 other parquet files are
  byte-identical (same LFS sha256). The README changed only in the counts.
  (`files_changed.csv` reports `paper_id_changed = 2` for TMLR 2026: that is one PDF that already appeared
  under two paper ids in V2, `8xEXo9D5rg` and `TAzPZ1US0J`, which the join by `pdf_sha256` crosses. Both
  ids are present and unchanged in both revisions.)
- No new venue, year or metadata column. No other woog dataset changed after 2026-10-13.

**Consequence.** The addition is too small to move any V2 result (at most 0.3% of an ICLR 2026 or TMLR
cohort). V3 work uses the V3 pin for new analyses; V2 numbers are not recomputed.

## The added records

`added_records.csv` lists the 165 records (omissions config) with ids and hashes.

## New external data: review metadata (not from woog)

The dataset has no authors, reviews or decisions. For the author-count analysis V3 adds ICLR 2017–2026
review metadata from Paper Copilot's `paperlists` (github.com/papercopilot/paperlists, commit
`9fcfd1234879a8e5630b5116dde411ec143dd763`; per-file sha256 in `results/v3/review_meta/source_files.csv`).
It is a third-party scrape of OpenReview; the OpenReview API itself answers this environment with a
browser challenge (HTTP 403). Coverage: `results/v3/review_meta/coverage.csv`. Per-paper rows
(names, affiliations) stay out of the repository in `data/v3/review_meta.parquet`, rebuilt by
`scripts/v3/review_meta.py`.

## Reproduce

    python3 scripts/v3/corpus_diff_v3.py --new b9bfffba0c81927866a747d48c6c259fb42edd76
    python3 scripts/v3/review_meta.py --src <dir with paperlists iclr/iclr20{17..26}.json>
