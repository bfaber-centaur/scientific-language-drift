# V2 adversarial review (Lane E)

_2026-10-15, Lane E (thread "Lane E: independent adversarial review"). Dataset
`woog/open-text-detector-papers`, V1 pin `cb5553e0c192c31c562a2822668c7f4ebbb9437a`, V2 pin
`2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27`. Tables are in `results/v2/review/`, scripts in
`scripts/v2/review/`. **No review script imports `mlngrams`**: downloads, hashing, tokenizer, region
rules and counters are written separately, so agreement with the other lanes is not shared code
agreeing with itself. The one shared component that cannot be avoided is the dataset's own text
extraction (all three configs and all venues come from the same pipeline). No paper text is stored._

Labels used below: **fact** = measured here, with the table named; **interpretation** = what the
fact suggests; **hypothesis** = untested.

## Verdicts

| # | Claim checked | Owner | Verdict |
|---|---|---|---|
| E1 | All 93,249 V1 records are unchanged in V2; 52,128 added, 0 removed | Gate 0 / Lane A | **Confirmed** on our own SHA-256 of every text (145,377 × 3 configs) |
| E2 | Revision-cache collision fixed; V1 unaffected | Gate 0 / Lane A | **Confirmed** for `mlngrams.load`. Two latent defects elsewhere (D1, D2) |
| E3 | First-page version labels (`scripts/v2/version_mix.py`) | Gate 0 / Lane A | **Confirmed**; reproduced exactly and consistent with the venue/year printed in headers. TMLR year resolved for the published stratum |
| E4 | ICLR↔ICML exact-title pairs are the same manuscripts; overlap ≈ 13% of ICML 2026 | Gate 0, Lanes B/C | **Pairs confirmed; overlap undercounted.** Text matching raises it to ≥ 16.3% (D3) |
| E5 | ICLR 2024→2027 function-word shift (of −48%, in −43%, we −44%, and +41%) survives V2 | Lane C (and B) | **Reproduced** with an independent counter: −47.6 / −42.6 / −41.8 / +39.4%. Added records change nothing. The shift is a whole-distribution move, and it appears in every venue's latest cohort |
| E6 | Same-paper pairs | Lane C | ICLR 2026→2027 resubmissions move only part of the way; ICLR→ICML camera-ready revision barely moves "of" |
| E7 | Could an extraction artifact be deleting "of"? | Lane C | **No evidence** in obligatory-"of" frames; not decisive |
| E8 | Directive's statement that a 2027 PDF was re-extracted with MuPDF | Coordinator | **Not in the repository record** (D4) |

## Defects found

### D1. Unverified downloaders are exposed to silent transfer corruption (latent; affects any lane with its own downloader)

**Fact.** During this review, 10 of about 157 whole-file download attempts from the Hub through this
environment's proxy delivered bytes whose SHA-256 did not match the LFS hash the Hub API lists for that
path at that revision. No HTTP error was raised. 9 happened with 3 parallel downloads, 1 with a single
download. Each retry succeeded, and a single-stream re-download of one affected file
(`direct/iclr-2021.parquet`) had the right length (66,252,579 bytes) and hash. Our downloader
(`scripts/v2/review/fetch_hash.py`) caught all 10 because it hashes the stream; logs are in the
scratchpad, not the repo.

**Which code is exposed.**
- `src/mlngrams/load.fetch`: **safe.** It verifies against the API's LFS hash and refuses a mismatch.
  Every V2 script of Lanes B and D goes through it.
- Lane C's V2 counter: says its downloader verifies against the Gate 0 LFS hashes (commit `6b80821`).
- `scripts/independent_function_words.py` `fetch()`: **no hash check.** A corrupted transfer is cached
  under `<cache>/<revision>/…` and reused forever. Also, the cache key is the revision string as
  given, so `--revision main` would collide across dataset updates (the original V1 defect).
- `scripts/v2/version_mix.py` and `scripts/v2/collect_metadata.py` read parquet over HTTP range
  requests (`HfFileSystem`) with no hash check. **Their outputs are nevertheless correct:** our
  hash-verified copies reproduce the Gate 0 version-label counts exactly in all 36 V2 files, and the
  added/retained counts exactly (E1, E3).

**MRE.** `python3 -I scripts/v2/review/fetch_hash.py --store S --out R --workers 3` prints
`retry k: <path>@2c0dd19: bytes sha … != listed LFS …` lines; the frequency varies by session.

**Fix.** Any downloader used for results should hash against the Hub API (as `load.fetch` does), or
call `load.fetch`. Retire or patch `independent_function_words.py` before reusing it on V2.

### D2. `scripts/count_ngrams.py` has no `--revision`; a V2 run without the environment variable silently counts V1 (latent; Lane B)

**Fact.** `count_ngrams.py` reads `iter_docs(a.config, a.venue, year)` with the module default
`REVISION`, which is the V1 pin unless `MLNGRAMS_REVISION` is set (`src/mlngrams/load.py:41`). It accepts
the V2 flags file. If the variable is missing, the run reads the V1 files, finds no row for the 21,177
added ICLR records, and writes V1 counts into a directory meant for V2. Nothing fails; only
`run.json` (`"revision"`) shows it.

**MRE.**
```bash
python3 -c "import sys; sys.path.insert(0,'src'); from mlngrams import load; print(load.REVISION)"
# cb5553e0c192c31c562a2822668c7f4ebbb9437a  (default when MLNGRAMS_REVISION is unset)
grep -n "add_argument(\"--revision" scripts/count_ngrams.py   # no match
```

**Fix.** Add `--revision` (default `REVISION`) and refuse to run when a V2 flags file is passed with the
V1 revision. **Check for Lane B:** every V2 `run.json` should say `2c0dd192…`, and per-year document
counts should equal the V2 row counts (e.g. ICLR 2026: 19,732 records before exclusions).

### D3. Title matching undercounts venue overlap by about a fifth (Lanes B and C)

**Fact** (`e4_title_pairs_summary.csv`, `e4_textpairs_*.csv`). For each venue-year pair we MinHashed
(128 permutations) the 6-word shingles of the first 1,500 body tokens and found text matches
(estimated Jaccard ≥ 0.3) by LSH. Random cross-venue pairs never exceed 0.016.

| pair | exact-title pairs | text matches with a different title | b-side papers matched by title or text | Gate 0 share |
|---|---:|---:|---:|---:|
| ICLR 2026 ↔ ICML 2026 | 868 | 199 | **16.3%** of ICML 2026 | 13.3% |
| ICLR 2025 ↔ ICML 2025 | 423 | 120 | **15.9%** of ICML 2025 | 12.4% |
| ICLR 2024 ↔ ICML 2024 | 258 | 78 | **12.9%** of ICML 2024 | 9.9% |
| ICLR 2026 ↔ TMLR 2026 | 326 | 95 | **13.9%** of TMLR 2026 | 10.7% |
| ICLR 2026 ↔ ICLR 2027 | 237 | 71 | 0.7% of ICLR 2027 | 1.2% of ICLR 2026 |
| COLM 2026 ↔ ICLR 2026 | 81 | 12 | 9.5% of COLM 2026 (title) | 9.5% |

Shingle matching is itself a lower bound (heavily rewritten papers fall below 0.3), so these shares are
still minima. **Effect:** an ICML "without ICLR overlap" sensitivity built from titles keeps about 3% of
ICML papers that are ICLR manuscripts.

**The exact-title pairs are the same manuscripts.** On a bag-of-words cosine of the first 1,500 body
tokens, 0 of 423 (2025), 4 of 868 (ICLR→ICML 2026) and 6 of 237 (ICLR 2026→2027) title pairs fall below
the 99th percentile of random pairs (`title_pairs_low.py`). But many are heavily rewritten: 22% of the
ICLR 2026→2027 pairs and 7% of the ICLR 2026→ICML 2026 pairs share less than 10% of their 6-word
shingles. So "same title" means "same project", not "same text".

**Fix.** Use the union of title and text matches (`e4_textpairs_*.csv` has the ids) for exclusions,
and say the overlap is ≥ 16%.

### D4. The MuPDF re-extraction result in the V2 directive has no record in the repository (coordinator)

The directive says a separately downloaded 2027 PDF was extracted with MuPDF and closely matched the
dataset. `docs/independent-function-word-investigation.md` says the opposite: OpenReview returned 403,
and **zero PDFs were downloaded or re-extracted**; `results/independent_function_words/pdf_metrics.csv`
has a header and no rows. OpenReview still returns 403 from this environment. Until the PDF, its hash
and the extraction output are committed, that observation should not be cited as evidence against an
extraction artifact.

### Minor

- Gate 0 says "55 of the 95 parquet files are byte-identical". V1 has 93 parquet files (31 per config),
  of which 54 (18 per config) are byte-identical in V2; the 55/95 count includes `.gitattributes` and
  `README.md`.
- Gate 0's overlap shares use titles ≥ 25 characters as the denominator, not all records. The difference
  is small for ICML (titles present for all records).

## E1. V1 records unchanged (fact)

`scripts/v2/review/fetch_hash.py` lists both revisions with the Hub API, downloads every V2 file and every
V1 file whose LFS hash differs (147 files, ~16 GB), verifies the bytes, and computes SHA-256 of every
text itself. `identity_check.py` then compares (`e1_identity.csv`):

- `text_sha256` column = our SHA-256 of the text in **all 145,377 V2 rows and all 26,852 V1 rows of
  changed files, in all three configs**. So identity of the hash column implies identity of the text.
- V1 records missing in V2: **0**. V1 records whose `(paper_id, pdf_sha256, text)` changed: **0**. Added:
  **52,128** per config. Duplicate `paper_id` within a file: 0. `conference`/`year` ≠ filename: 0.
- The three configs hold exactly the same `(file, pdf_sha256, paper_id)` keys.
- V1's committed coverage tables (`results/coverage_iclr.csv`, `coverage_venues.csv`) have the V1 row
  count in 31/31 venue-years, so V1 counts were not computed on a later, larger cached file.

## E2. Cache fix (fact)

`src/mlngrams/load.fetch` keys the cache by the resolved 40-character sha, verifies downloads against
the Hub API's LFS hash, and ignores the legacy layout; `tests/test_cache.py` passes (6 tests). One
residual weakness, documented in the code: a same-size corruption of an already-cached file is only
caught with `MLNGRAMS_VERIFY=1`. Recommended for final runs: set `MLNGRAMS_VERIFY=1` once.

## E3. Version labels (fact)

`header_audit.py` re-runs the Gate 0 classifier on every V2 `direct` record and, separately, parses
the venue, edition and year that the first page itself names, with our own patterns
(`e3_header_audit.csv`, `e3_header_year_mismatch.csv`, `e3_tmlr_year_vs_header.csv`).

- **Reproduction:** our label counts equal `results/v2/inventory/version_mix.csv` in all 36 V2 files.
  Every record has a form feed, so "first page" is always defined.
- **Agreement with the header:** of 42,864 records whose header names a camera-ready, Gate 0 labels 42,699
  published; of 81,899 whose header names a submission, all are labelled submission. The 165 that
  disagree: 145 NeurIPS records are our parser's error (it misses "Submitted to *the* 38th Conference…",
  which Gate 0 handles), and 20 ICLR/CoRL records carry both a camera-ready header and an "anonymous
  authors"/"double-blind review" line; Gate 0 calls them submissions. Negligible.
- **Hand reading:** 44 first pages (4 per stratum: ICML 2026 published/submission/unknown, TMLR 2026
  published/submission/unknown, COLM 2026, ICLR 2026 and 2027 unknown, NeurIPS 2025 unknown, EMNLP 2023)
  match their labels. "Unknown" ICML records are camera-ready papers whose footer is split by figure
  text; "unknown" NeurIPS 2025 records are "Preprint. Under review." arXiv-style PDFs; unknown TMLR
  includes two browser printouts of the TMLR web page. EMNLP pages have no version line, as Gate 0 says.
- **Header year vs file year:** ICLR 2027 holds 206 records whose header names an earlier ICLR (196
  "under review … ICLR 2026"); ICLR 2026 holds 143 naming ICLR 2025. These look like reused templates.
  Their body rates are 2027-like ("of" 15,332 vs 13,898 per million for ICLR-2027-header papers; ICLR
  2026: 20,438), so they are not a block of old texts.
- **TMLR year, now answered for the published stratum:** in 95.5% of published TMLR records the year in
  "Published in Transactions on Machine Learning Research (MM/YYYY)" equals the file year; the other
  4.5% name the following year (2024 file: 63 of 981 say 2025; 2025 file: 145 of 1,461 say 2026). So
  for published records the dataset year is the publication year or one year earlier. The 115% card
  excess in TMLR 2026 comes from submissions. Lane A's open item 7 can be closed for the published
  stratum.

## E5. Function words, independent recount (fact, then interpretation)

`fw_recount.py`: drop `⟦…⟧` markers, join line-break hyphens, lowercase, tokens = `[a-z]+`; denominator
= all such tokens; body = text before the first `⟦references omitted⟧`; papers with < 300 body tokens
and exact duplicate texts (our hash) excluded. Rates per million tokens (`e5_function_words.csv`).

**ICLR, all records, body**

| year | n | of | in | we | and | the | median "of" per 1k, per paper |
|---|---:|---:|---:|---:|---:|---:|---:|
| 2023 | 4,821 | 26,456 | 18,702 | 14,484 | 23,246 | 62,531 | 26.2 |
| 2024 | 7,299 | 26,514 | 18,974 | 13,867 | 23,404 | 60,889 | 26.2 |
| 2025 | 11,605 | 25,257 | 18,618 | 13,029 | 23,999 | 58,860 | 24.9 |
| 2026 | 19,727 | 20,438 | 15,908 | 11,355 | 25,971 | 48,753 | 19.9 |
| 2027 | 42,323 | 13,906 | 10,892 | 8,075 | 32,616 | 51,606 | 12.6 |

- **2024→2027:** of −47.6%, in −42.6%, we −41.8%, and +39.4% (V1: −48, −43, −44, +41). The V1 finding
  survives; our "we" is 2 points smaller, a tokenizer difference.
- **V1 vs added records**, same year: within 2.4% for every word in 2024, 2025 and 2026 (e.g. "of" 2026:
  20,396 V1 vs 20,453 added). The expansion does not move the estimates; this is expected from E1 and
  Gate 1.
- **Version:** ICLR 2026 camera-ready vs submission: "of" 20,436 vs 20,440. The 2026 drop is not a
  camera-ready effect.
- **Not a mixture.** The whole per-paper distribution moves (`e5_iclr_of_distribution.csv`): the share of
  papers with fewer than 16 "of" per 1,000 tokens is 3% in 2025, 23% in 2026 and 72% in 2027; the 95th
  percentile in 2027 (24.1) is below the 2025 median (24.9).
- **2026 already moved.** About 40% of the 2024→2027 fall in "of" happens between 2025 and 2026 (−19%).

**Other venues, published stratum** (body; same counter)

| venue | earlier years ("of") | latest cohort | step into latest cohort |
|---|---|---|---:|
| ICML | 27,226 (2023), 26,959 (2024), 24,644 (2025) | 18,700 (2026) | −24% |
| NeurIPS | 28,188–26,909 (2021–24) | 22,966 (2025) | −15% |
| COLM | 25,677 (2024), 21,909 (2025) | 16,454 (2026) | −25% |
| TMLR | 28,215–25,355 (2022–25) | 20,575 (2026) | −19% |
| CoRL | 24,978–22,396 (2021–24) | 19,287 (2025) | −14% |

"and" rises and "we" falls at every venue in the same years. **Cross-check with Lane C** (commit
`6b80821`, `results/v2/function_words/rates_by_cohort.csv`, a separately written counter): its levels
are ~6% lower (different denominator) but the latest-cohort steps agree within 1 point (ICML −24.0 vs
−24.1, NeurIPS −14.9 vs −14.7, COLM −25.6 vs −24.9, TMLR −19.4 vs −18.8, CoRL −13.6 vs −13.9).

**Interpretation.** The decline is not ICLR-specific and not a 2027 discontinuity alone: every venue
shows its largest step in its most recently written cohort, and ICLR's own fall starts with 2026. That
fits a field-wide change tied to writing date. It does not identify a cause, and it cannot exclude an
artifact of the shared extraction pipeline that correlates with PDF date (see E7). Reading excerpts of
introductions from six 2027 papers with 5–13 "of" per 1,000 tokens (not stored): fluent, grammatical
prose with dense noun compounds and semicolons ("Contrast information ranks candidates; level
information anchors their absolute performance"), no visible dropped words. Six excerpts are an
illustration, not a test.

## E6. Same-paper pairs (fact)

Per-paper change of the body rate (per 1,000 tokens) within exact-title pairs, excluding identical
texts; median and bootstrap 95% CI (`e6_paired_function_words.csv`):

| pair | n | "of" before → after | median change | "and" median change |
|---|---:|---|---:|---:|
| ICLR 2025 → ICML 2025 (control) | 423 | 25.6 → 24.9 | −0.37 [−0.60, −0.16] | +0.24 |
| ICLR 2026 → ICML 2026 | 867 | 19.6 → 19.1 | −0.28 [−0.42, −0.12] | −0.19 |
| ICLR 2026 → ICLR 2027 | 229 | 21.6 → 18.0 | −1.98 [−2.39, −1.48] | +2.00 |

- Revising an ICLR submission into an ICML camera-ready barely changes "of", in 2025 and in 2026. The
  ICML 2026 cohort's drop is therefore not produced by revising existing manuscripts; the ~16% of ICML
  2026 that are ICLR 2026 manuscripts sit near the ICLR 2026 level (19.1).
- ICLR 2027 resubmissions move part of the way (−9%) but stay far above the 2027 population median
  (12.6). Lane C reports a similar within-pair change for 2025→2026 resubmissions (−10%, `pairs_summary.csv`,
  P2ctl), so the within-paper change at the 2027 boundary is not larger than a year earlier.
- **Interpretation:** most of the population shift is carried by papers that are new in each cohort,
  not by edits to carried-over text. This is consistent with V1's N11 correction.

## E7. Extraction-deletion test

If extraction were dropping "of" tokens, phrases in which "of" is obligatory would surface without it
("one the", "most the"). `of_deletion_test.py` counts "Q of the" and bare "Q the" for 11 quantifiers
(`e7_of_deletion_test.csv`). Bare "one the" rises from 4.7 to 17.9 per million (2026→2027) and "most the"
from 0.8 to 6.0, which looked like a signal. **Reading 26 of the 2027 matches shows they are
grammatical:** "at most the …" (a bound, frequent in theory papers), "the one the gate detected",
"each the mean of …". None was a sentence with a missing "of". "Q of the" frames fall roughly with "of"
itself ("one of the" 58.8 → 30.7; "some of the" 11.1 → 5.2).

**Verdict:** no evidence of word deletion by extraction; this cheap test cannot exclude subtler
artifacts. The decisive test is still a hash-matched PDF re-extracted with another tool (D4).

## Reproduce

```bash
S=<scratch dir>
python3 -I scripts/v2/review/fetch_hash.py --store $S/store --out $S/rec --workers 1   # ~45 min, ~16 GB transient
python3 -I scripts/v2/review/identity_check.py $S/rec results/v2/review
python3 -I scripts/v2/review/header_audit.py $S/rec $S/store $S/out/headers.parquet
python3 -I scripts/v2/review/fw_recount.py $S/rec $S/store $S/out/fw_iclr.parquet iclr
python3 -I scripts/v2/review/fw_recount.py $S/rec $S/store $S/out/fw_other.parquet icml neurips colm tmlr corl emnlp
python3 -I scripts/v2/review/review_tables.py $S/rec $S/out results/v2/review
python3 -I scripts/v2/review/title_pairs.py $S/rec $S/store results/v2/review iclr-2026:icml-2026 iclr-2025:icml-2025 \
    iclr-2024:icml-2024 iclr-2026:iclr-2027 iclr-2026:tmlr-2026 colm-2026:iclr-2026
python3 scripts/v2/review/title_pairs_low.py $S/rec $S/store $S/out/title_pairs_detail.csv iclr-2026:icml-2026 iclr-2026:iclr-2027 iclr-2025:icml-2025
python3 -I scripts/v2/review/of_deletion_test.py $S/rec $S/store results/v2/review/e7_of_deletion_test.csv iclr-2023 iclr-2025 iclr-2026 iclr-2027
```
`e6_paired_function_words.csv` was computed from the outputs of `fw_recount.py` and `title_pairs_low.py`
(median of per-pair differences, 1,000 bootstrap resamples, seed 0).
