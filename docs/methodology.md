# Methodology

_Versions at the time of writing (2026-10-14): tokenizer v1.3, content filter v1.2, statement sections v2,
dataset revision `cb5553e0c192c31c562a2822668c7f4ebbb9437a`. Every count run records its parameters in
`run.json` next to its outputs; the longitudinal analysis records them in
`results/full/longitudinal/method.json`._

## 1. Corpus selection

- Source: `woog/open-text-detector-papers`, config `omissions` (see `docs/corpus.md` for why).
- Longitudinal corpus: ICLR 2017–2027. ICLR 2013/2014 (≈65 papers each) appear in all-text tables only
  and are excluded from rankings. Other venues are used only as cross-checks (finding 2, finding 4).
- Excluded papers: exact duplicate texts (`text_sha256`), texts under 2,000 characters, unmodified ICLR
  template placeholders (`results/paper_flags_iclr.csv`, column `exclude`; per-run list in `duplicates.csv`).
- ICLR 2025: only papers whose OpenReview id starts with 0–9 or A–P enter year-level tables (4,781
  papers). The extracted remainder (ids Q–z, title-slug ids) is a partial, accepted-heavy crawl
  (43.7% and 100% camera-ready vs 30.2%); it is kept in stratified tables as `|offsample`.
- ICLR 2026: 26% of submissions, all with ids starting 0–9/A–F (+91 G): a crawl cut off in id order,
  plausibly random with respect to content. Used as is.
- Version strata: `published` (camera-ready header in the raw `direct` text), `under_review`
  (submission header), `unknown`. Needed because 2027 is 94% submissions vs 59–72% in 2017–2026.

## 2. Text units

1. Statement sections removed (`src/mlngrams/sections.py`): a heading line that, after an optional
   section number, is one of the listed statement names (ethics, reproducibility, LLM/AI use or
   disclosure, broader impact, impact statement, acknowledgments, author contributions); removed up to
   the next heading-like line, a reference-list marker, or 5,000 characters.
2. Main body (`--body-only`, headline): text before the first `⟦references omitted⟧`. All text
   (sensitivity): including appendices.

## 3. Tokenization (`src/mlngrams/tokenize.py`)

Normalize (NFKC, fold diacritics, repair line-break hyphenation), mark heading lines and parenthetical
acronyms as boundaries, lowercase, replace omission markers, URLs/e-mails and citations with boundaries,
protect abbreviations and decimals, split into segments at `. ! ? ; :`, math-like characters and blank
lines; tokens are `[a-z]+` words with internal `-`/`'`, digit runs → `<num>`. N-grams (n = 1, 2, 3) are
formed within segments only. Each rule has a synthetic test in `tests/`.

## 4. Counting and normalization (`scripts/count_ngrams.py`)

- Per group (year, and year × version stratum): `count`, `df` (papers containing the n-gram), `docs`,
  `tokens`, `positions_n` = Σ over segments max(0, len − n + 1).
- `per_million = 1e6 · count / positions_n`; `prevalence = df / docs`.
- Stored n-grams: df ≥ 3 in at least one year; all other years' rows exact (missing row = 0).
- Exact: chunk counts are merged with DuckDB, not sampled or hashed.

## 5. Aggregation across years

- Corpus-weighted (cw): pool counts and positions over the years of a cohort. Dominated by large years
  (2027 = 56% of all papers; 81% of the 2025–27 cohort).
- Year-balanced (yb): mean of the per-year rates. Both are reported for every ranking, and
  `cw_vs_yb_*.csv` lists n-grams whose rank depends on the choice.

## 6. Change statistics (`scripts/longitudinal.py`)

- Cohorts: early 2017–2021; recent 2025–2027 (main), 2024–2026 (excludes the 2027 submission snapshot),
  2027 alone.
- Score: log2 of add-k smoothed rates, rate = 1e6 · (Σcount + 5) / Σpositions.
- Eligibility: in the higher cohort, prevalence ≥ 1% and ≥ 20 papers.
- Also ranked by change in prevalence (percentage points).
- Non-monotonic trajectories: interior peak/trough with ≥ 2× ratio on both sides, prevalence ≥ 2% in
  some year.
- Uncertainty: Wilson 95% intervals on per-year prevalence. A paper-level bootstrap is not possible from
  the aggregate tables; single-paper dominance is guarded only by the df floor.
- Sensitivity columns: under-review stratum only (`log2_cw_ur`), all-text run, `spike_2027` (2027 rate
  ≥ 8× the 2024–26 rate, flags 2027-only template text).
- Pre-registration: a 36-item watchlist with predicted directions was written into the script docstring
  before the full run (`watchlist_evaluation.csv`).

## 7. Cross-checks (each with its own script)

| Check | Script | Population | Output |
|---|---|---|---|
| Raw-text layer and other venues | `check_style_shift.py` | ≤800 random papers per venue-year-config, seed = year | `results/style_shift_checks.csv` |
| Same paper, two versions | `resubmission_test.py` | near-duplicate cross-year pairs from `recon.py` (ICLR 2024→25, 25→26, 25→27, 26→27) | `results/resubmission_*.csv` |
| Self-reported AI use | `ai_disclosure_strata.py` | 12,000 random ICLR 2027 papers, keyword classes of their AI-use statement | `results/ai_disclosure_strata_2027.csv` |

## 8. What the methods cannot do

Observational frequencies only; no authorship attribution, no causal claims. Self-reported AI-use
classes are crude keyword rules. Prevalence intervals understate uncertainty (coverage selection,
burstiness). Partial years (2025, 2026) are samples of unknown representativeness beyond the id checks.
