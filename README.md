# Scientific language drift: a decade of n-grams in ML papers

A longitudinal, observational study of word n-grams in ML papers from
[`woog/open-text-detector-papers`](https://huggingface.co/datasets/woog/open-text-detector-papers)
(pinned revision `cb5553e0c192c31c562a2822668c7f4ebbb9437a`), with ICLR 2017–2027 as the primary corpus
and NeurIPS, TMLR, COLM, ICML and EMNLP as cross-checks. This repository is the durable record of the
study: code, derived tables, methods, findings, and the results that turned out to be wrong.

It is not an AI-text detector. Nothing here is evidence about who or what wrote any paper, and
linguistic correlations are not treated as evidence that AI use caused a change.

## Research questions

1. What are the most common word n-grams in ML papers, and how have their frequencies changed over time?
2. Which changes are topic turnover (what the field studies) and which are changes in how papers are written?
3. Are there abrupt or non-monotonic shifts in phrasing, and do they survive corpus artifacts
   (template text, appendix growth, version mix, partial coverage, extraction)?

**Scope:** frequencies, prevalence and their change, with explicit confounders and cheap falsification
tests. **Out of scope** for now: authorship attribution, AI-text classifiers, causal claims.

## Current status (2026-10-14)

| Result | Status | Where |
|---|---|---|
| Reproducible uni/bi/trigram counts, per-million rates and paper prevalence, ICLR 2017–2027 | **Validated**: 34 synthetic tests, hand-checked papers, independent QA (`docs/qa.md`) | `results/full/body/` |
| F1. Topic turnover drives the largest movers | **Validated (descriptive)**: holds corpus-weighted, year-balanced and in submissions only | `docs/findings.md` §1 |
| F2. 2024 burst of rhetorical words (*delve*, *underscores*, *intricate*), fading by 2027 | **Validated (descriptive)** in ICLR, raw PDF text, NeurIPS, TMLR, COLM, and in non-LLM papers; cause untested | §2 |
| F3. ICLR 2027 breaks with earlier years (*a novel*, *we propose* fall; *test whether*, *held fixed* rise) | **Validated (descriptive), cause unknown**: holds in submissions only, raw text, LLM and non-LLM papers, after the contamination fix; resubmission evidence is ambiguous; full-text recount and subgroup analysis in progress | §3 |
| F4. Function words thinning since before 2023, accelerating from 2024 | **Validated (descriptive)** across venues, the raw text layer and long running-prose segments | §4 |
| F5. The "across" construction | **Preliminary** | §5 |
| "2027 surge of AI vocabulary" (*generative ai*, *ai use*, *ai tools*) | **Invalid**: template contamination from the required ICLR 2027 AI-use statement | `docs/negative-results.md` N1 |
| 2027 phrasing tracks self-reported AI drafting help | **Withdrawn**: keyword classifier agreed with hand labels on ~50% of statements | N13 |

Active work, blockers and next steps: [`docs/handoff.md`](docs/handoff.md).

## Documents

- [`docs/methodology.md`](docs/methodology.md): corpus selection, tokenization, normalization, statistics
- [`docs/corpus.md`](docs/corpus.md): provenance, pinned revision, venue/year coverage, extraction limits
- [`docs/findings.md`](docs/findings.md): observations with evidence, facts / interpretations / hypotheses kept apart
- [`docs/negative-results.md`](docs/negative-results.md): false leads, failed predictions, corrections
- [`docs/qa.md`](docs/qa.md), [`docs/review_findings.md`](docs/review_findings.md): independent QA of the pipeline and adversarial review of the findings
- [`docs/handoff.md`](docs/handoff.md): current state, history, how to resume

## Quickstart

```bash
python3 -m pip install -r requirements.txt
python3 -m pytest                       # 34 synthetic counting / tokenization / normalization tests
# Smallest real run: one ICLR year, main body only (downloads one parquet to ~/.cache/mlngrams)
python3 scripts/count_ngrams.py --years 2018 --body-only --out data/demo
python3 scripts/make_tables.py data/demo data/demo_tables   # data/ is git-ignored
```

The full reproduction sequence for every published table and figure is under
[Setup and reproduction](#setup-and-reproduction).

## Results layout

| Path | What |
|---|---|
| `results/full/body/` | Top-100 uni/bi/trigram tables per year and pooled (`_pooled_yb` year-balanced, `_pooled_cw` corpus-weighted), raw and content-filtered, from the **main-body** run (headline) |
| `results/full/alltext/` | The same from the all-text run (sensitivity: includes appendices) |
| `results/full/longitudinal/` | Annual time series, risers/fallers, non-monotonic trajectories, year-over-year jumps, prevalence CIs, denominator diagnostics, watchlist with pre-registered predictions, figures |
| `results/pilot/` | Gate 1 pilot (ICLR 2018/2020/2024/2026, all text) |
| `results/coverage_*.csv`, `duplicates_*.csv`, `paper_flags_iclr.csv` | Corpus recon (ids and aggregates only) |
| `results/style_shift_checks.csv`, `resubmission_*.csv`, `ai_disclosure_strata_2027.csv` | Cross-checks behind findings 2–4 |

No paper text is stored in this repository; derived tables contain only n-grams, counts and ids.
Full per-year count tables (hundreds of MB) are regenerated by the commands below.

## Setup and reproduction

```bash
python3 -m pip install pyarrow pandas numpy matplotlib duckdb pytest
python3 -m pytest                                    # synthetic counting / normalization tests

# Corpus recon and per-paper flags (downloads ~5 GB of parquet into ~/.cache/mlngrams)
python3 scripts/recon.py
python3 scripts/paper_flags.py

# Counts (4 cores: ~18 min body-only, ~20 min all text; DuckDB spills to disk)
python3 scripts/count_ngrams.py --years 2017-2027 --body-only --out data/full_body
python3 scripts/count_ngrams.py --years 2013 2014 2017-2027 --out data/full
python3 scripts/count_ngrams.py --years 2018 2020 2024 2026 --out data/pilot

# Tables, longitudinal analysis, cross-checks
python3 scripts/make_tables.py data/full_body results/full/body
python3 scripts/make_tables.py data/full results/full/alltext
python3 scripts/make_tables.py data/pilot results/pilot
python3 scripts/longitudinal.py data/full_body full --sens data/full --sens-label alltext
python3 scripts/check_style_shift.py
python3 scripts/resubmission_test.py
python3 scripts/ai_disclosure_strata.py
```

`data/` is git-ignored. The cache directory and revision can be overridden with `MLNGRAMS_CACHE` and
`MLNGRAMS_REVISION`.

## Data contract

`mlngrams.load.iter_docs(config, venue, year)` yields `{doc_id, venue, year, pdf_sha256, text_sha256, text}`
and is the only way analysis code touches the corpus. Primary config is `omissions` (equations, inline math,
tables, figure text and reference lists replaced by `⟦...⟧` markers); see `docs/corpus.md`.

## Which papers are counted

- Exact duplicate texts (same `text_sha256`), texts under 2,000 characters, and unmodified ICLR template
  placeholders are skipped (listed in each run's `duplicates.csv`).
- `results/paper_flags_iclr.csv` assigns each paper a **version stratum** from the running header in the raw
  text layer: `published` (camera-ready), `under_review` (submission) or `unknown`. 2027 is 94% submissions,
  earlier years 59–72%, so every comparison is also available within `under_review` only
  (`ngrams_n*_by_stratum.parquet`).
- ICLR 2025 year-level tables use only papers whose OpenReview id starts with 0–9/A–P: the rest of 2025 was
  extracted only partially and skews to accepted papers. They stay in the stratified tables as `|offsample`.

## Text processing

1. **Statement sections cut** (`src/mlngrams/sections.py`, v2): ethics, reproducibility, LLM/AI-use,
   broader-impact, acknowledgment and author-contribution sections, from their heading to the next heading
   (max 5,000 chars). These are required template text whose arrival would otherwise dominate the risers.
2. **Main body** (headline runs, `--body-only`): text before the first `⟦references omitted⟧` marker.
   Appendices grew from 7% to 47% of text between 2017 and 2027.
3. **Tokenizer** (`src/mlngrams/tokenize.py`, v1.3):
   NFKC, diacritics folded, lowercase; line-break hyphenation repaired (real compounds keep their hyphen);
   n-grams never cross sentence punctuation `. ! ? ; :`, blank lines, math-like characters
   `= + \ { } ^ _ $ | < > ~ * / #`, omission markers, URLs/e-mails, heading lines without lowercase
   letters, parenthetical acronyms like "(LLMs)", or stripped citations (author-year parentheticals and
   numeric brackets). Abbreviations (e.g., i.e., et al., Fig., Eq., vs., ...) and decimals do not end a
   segment. Tokens are alphabetic words with internal hyphens/apostrophes; digit runs become `<num>`.
   Commas, quotes and parentheses are dropped without breaking n-grams.

## Normalization

- `per_million = 1e6 × count / positions_n`, where `positions_n` is the number of n-gram slots
  (Σ max(0, len(segment) − n + 1)), not the token count.
- `prevalence = df / docs`: share of papers containing the n-gram at least once. Preferred for claims,
  because it is robust to paper length and to single papers repeating a phrase.
- Count tables hold every n-gram with df ≥ 3 in at least one year, with exact counts in all other years
  (a missing row is a true zero). Totals are never pruned.
- **Corpus-weighted** pools counts over years (2027 is 56% of all papers); **year-balanced** averages the
  per-year rates. Both are reported.

## Content filter (`src/mlngrams/filters.py`, v1.2)

Raw tables are always kept. The content view keeps an n-gram only if every token is not an NLTK English
stopword, not `<num>`, at least 2 characters, not citation/abbreviation residue (`et`, `al`, `eg`, `fig`,
...), and the n-gram is not on a short listed boilerplate list (`et al`, `workshop track`,
`international conference`, statement headings, ...). Each list addition is noted in the file.

## Rankings of change

log2 of add-5 smoothed per-million rates between cohorts (early 2017–2021, recent 2025–2027; sensitivity
2024–2026 and 2027 alone), eligible only with ≥1% prevalence and ≥20 papers in the higher cohort; also
ranked by change in prevalence (percentage points). See `scripts/longitudinal.py` for details.
