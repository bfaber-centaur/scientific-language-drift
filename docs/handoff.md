# Handoff

_Last updated 2026-10-14 (repository setup). Read this first if you are picking the study up cold, then
`README.md` (status table), `docs/findings.md` and `docs/negative-results.md`._

## Where the study stands

| Gate | State |
|---|---|
| 1. Pilot (ICLR 2018/2020/2024/2026) | Done. Superseded by the full run after QA fixes. |
| 2. Full ICLR 2017–2027 longitudinal analysis | Done for main-body text (75,118 papers). Full-text (appendices included) recount still running as a sensitivity check. |
| 3. Exploratory findings | Five findings written and adversarially reviewed (`docs/findings.md`, `docs/review_findings.md`); overclaims corrected (negative results N11, N13). Subgroup analysis of the 2027 shift in progress. |
| 4. Deliverable | Not started beyond this repository. |

Settled parameters (change only with new evidence, and bump the version): dataset revision
`cb5553e0c192c31c562a2822668c7f4ebbb9437a`, config `omissions`, tokenizer v1.3, content filter v1.2,
statement removal v2, main body = text before the first `⟦references omitted⟧`, ICLR 2025 restricted
to the 0–P id stratum, add-5 smoothing, ≥1% prevalence and ≥20 papers for rankings. Each run records
them in `run.json`; the longitudinal run in `results/full/longitudinal/method.json`.

## What happened, in order

1. **The 2027 shift was first seen in a contaminated run.** The first full longitudinal pass ranked 43 of
   the top 100 content risers as 2027-only AI vocabulary (*generative ai*, *ai use*, *ai tools*,
   *take responsibility*). It looked like a sudden surge of AI-related language.
2. **It was template text.** ICLR 2027 requires an "AI use statement". Statement removal v1 only knew the
   2026 "LLM usage" wording, so the 2027 statements were counted as prose. Caught by the `spike_2027`
   flag (2027 rate ≥ 8× the 2024–26 rate), a phrase-family cluster, and a census of heading lines
   (`AI USE STATEMENT` in 351 of 400 sampled 2027 papers).
3. **Removed and rerun.** `src/mlngrams/sections.py` v2 adds the 2027 headings and variants, with a test;
   on 1,000 sampled 2027 papers "ai use" fell from 90% to 2.1% prevalence. All counts were rerun.
   The v1 result is preserved as negative result N1 and must not be quoted as a trend.
4. **Cross-checks.** After removal, a different 2027 break remains (*a novel*, *we propose*, *in this
   paper* fall; *test whether*, *held fixed*, *results support* rise). It holds within submission
   versions only and in the raw PDF text layer (`direct` config), so it is not version mix or cleanup.
   Five other venues were sampled (`results/style_shift_checks.csv`, `scripts/check_style_shift.py`):
   the 2024 rhetorical-word peak and the function-word decline recur in NeurIPS, TMLR and COLM; ICML 2025
   and EMNLP 2023 are single-year samples and only place levels. None has 2026-written papers yet, so
   the 2027 break itself is ICLR-only so far.
5. **What remains uncertain about the 2027 shift.** Whether it reflects authors' writing, a different
   population of submitters (the cohort doubled to 42k), venue guidance, or the writing tools in use.
   The shift is not topical (similar in LLM and non-LLM papers) and not one shared template (only 3.9% of
   papers carry three or more of the new markers). Resubmitted papers (55 pairs, 2026→2027) move only
   part of the way with the cohort, which cannot separate a new population from a partial editing pass.
   An early association with self-reported AI drafting help was withdrawn after the keyword classifier
   matched hand labels on only ~50% of statements (N13). No causal claim is made.
6. **In progress now.** Full-text recount (sensitivity to appendix growth) and subgroup analysis of
   whether the 2027 shift is uniform across papers or concentrated in a subgroup. The adversarial review
   of the five findings is done (`docs/review_findings.md`).

## Active experiments and owners

Work happens in the project's research thread ("N-gram study, continued"), which writes to the working
copy at `/mnt/project-files/ml-ngrams` and should commit each milestone here.

- Full-text recount: `scripts/count_ngrams.py --years 2013 2014 2017-2027 --out data/full`, then
  `scripts/longitudinal.py ... --sens data/full`.
- Subgroup analysis of the 2027 shift (per-paper distribution, topic, version stratum).

## Blockers and risks

- The dataset keeps growing. Never move the revision pin without rerunning recon and updating
  `docs/corpus.md`.
- ICLR 2025 (53%) and 2026 (26%) are partial; 2027 is a submission snapshot. Every claim needs its
  comparison population stated.
- The corpus cache (~5 GB) lives outside the repo in an ephemeral container and must be re-downloaded.
- Per-paper n-gram vectors are not stored, so single-paper dominance and paper-level bootstraps need a
  rerun that keeps them.

## Next steps (from the findings' falsification tests)

1. Finding 2: compare submission and camera-ready wording of the same 2024 papers; fix a pre-2023 baseline.
2. Finding 3: check ICLR 2027 author guidelines for wording advice; repeat on a venue with 2026-written
   papers when extracted; enlarge the resubmission sample by fuzzy title matching; build a
   negation-aware AI-use classifier validated on ~100 hand-labelled statements.
3. Finding 5: relate "across <number>" to the number of benchmarks reported per paper.
4. Gate 4: a short report for woog ("here are your bigrams; also, look at this").

## Reproducibility check done at repository setup

On a fresh container, `python3 -m pytest` passed (34 tests) and
`scripts/count_ngrams.py --years 2018 --body-only` followed by `scripts/make_tables.py` reproduced the
committed 2018 rows of `results/full/body/corpus_totals.csv` and the top content bigrams exactly
(983 papers, 4,733,716 tokens; *neural networks* 3,810 occurrences in 768 papers).

## Repository hygiene

- Commit at each analytical milestone, with the parameters in the commit message or `run.json`.
- Commit small derived tables and figures only; `data/` (count parquet, hundreds of MB) is git-ignored
  and regenerated by the commands in `README.md`. No paper text is committed.
- Preserve failed experiments in `docs/negative-results.md`; never delete an invalidated result,
  mark it invalid and say why.
