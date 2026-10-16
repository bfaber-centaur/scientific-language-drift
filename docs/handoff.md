# Handoff

_Last updated 2026-10-14 (repository setup). Read this first if you are picking the study up cold, then
`README.md` (status table), `docs/findings.md` and `docs/negative-results.md`._

## Where the study stands

| Gate | State |
|---|---|
| 1. Pilot (ICLR 2018/2020/2024/2026) | Done. Superseded by the full run after QA fixes. |
| 2. Full ICLR 2017–2027 longitudinal analysis | Done: main-body text (75,118 papers, n = 1–3) and all-text sensitivity (n = 1, 2; trigram merge for all text exceeded the container disk and was skipped). |
| 3. Exploratory findings | Five findings written and adversarially reviewed (`docs/findings.md`, `docs/review_findings.md`); overclaims corrected (negative results N11, N13). Subgroup analysis of the 2027 shift done (finding 3, finding 4). |
| 4. Deliverable | Done: this repository and `docs/note-for-woog.md` ("here are your bigrams; also, look at this"). |

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
6. **Recount and subgroups (done).** The all-text recount agrees with the main-body results (top-100
   change rankings: Spearman 0.78–0.99, no riser or faller changes sign; `docs/findings.md`,
   "Sensitivity"). The trigram merge for all text ran out of container disk and was skipped; rerun
   with `--merge-only --ns 3` on a larger disk if needed. Subgroups: the 2027 shift moves the whole
   per-paper distribution, holds within submissions and in LLM and non-LLM papers.

## Active experiments and owners

Work happens in the project's research thread ("N-gram study, continued"), which writes to the working
copy at `/mnt/project-files/ml-ngrams` (branch `main`, tracking this repository). Nothing is running
now; remaining work is the next steps below (P3, comparison with AI-generated prose, is still out of scope).

### Lane A: appendix growth (2026-10-15, done through Gate 1)

`docs/appendix-growth.md`; `scripts/appendix_scan.py` → `scripts/appendix_analyze.py`
(+ `appendix_checks.py`); tables and figures in `results/appendix/`. Result: the growth is appendix growth
(main body flat at ~9 pages, appendix 1.5 → 12 pages), broad across papers, in every kind of appendix
material, within submissions and resubmissions, and in other venues. Hand audits: 63 post-reference
regions, 154 headings. Open: the 2026–27 drop in main-body prose per page; separating the 2027 appendix
jump from the doubled submitter cohort; a version check for non-ICLR venues. The per-paper scan
(`data/appendix/`, ~45 min) is git-ignored.

### Lanes B and C: AI-use disclosures and body language (2026-10-15, done through Gate 4)

**Docs:** `docs/ai-disclosures.md` (Lane B) and `docs/disclosure-body-analysis.md` (Lane C).
**Scripts:** `scripts/disclosures/` (extract, phrases, taxonomy, sample_labels, evaluate,
eval_groups, lane_c_features, lane_c_analysis, lane_c_review_checks).
**Classifier:** `src/mlngrams/disclosure_classify.py`, v2, frozen at 5c955d0.
**Labels:** `results/disclosures/labels/`.

State:
- Extractor v1 recovers 96.8% of 2027 disclosures.
- Classifier v2 passes Gate 3 narrowly on test2. The drafting group is roughly 75–86% true drafting.
- Lane C finds drafting-disclosure papers carry the 2027 register (`docs/findings.md` §6), and the
  result survives every Lane D check.

Git-ignored intermediates (regenerate with the scripts):
- `data/disclosures/iclr2027.parquet`, which contains disclosure text;
- `data/disclosures/lane_c_*`, about 25 minutes to rebuild.

Open:
- A human spot check of about 30 labels, since all labellers so far are Claude.
- Separate affirmed task-list items from template frame wording (Lane D B2).
- Regenerate the polarity table with the `.)` split and an attestation class (B3).
- Fix the end detection in extractor v1 for bibliography and ethics overruns (B1, 3.3%).
- Statement removal v2 misses about 4% of 2027 disclosures in the n-gram tables (N14). Decide
  whether to bump to v3 and rerun.
- Test the authorship-population alternative on camera-ready versions.

### Lane A (V2): corpus inventory and provenance (2026-10-15, Gates 0 and 1 done)

**Doc:** `docs/v2-corpus-inventory.md`. **Scripts:** `scripts/v2/` (collect_metadata, version_mix,
corpus_diff, inventory_extras, plot_inventory). **Tables:** `results/v2/inventory/`.

- V2 pin `2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27` (`mlngrams.load.V2_REVISION`). The default
  `REVISION` stays the V1 pin, so V1 scripts reproduce V1.
- The update only adds records: all 93,249 V1 records are byte-identical in V2, and 52,128 were added.
  `results/v2/inventory/membership.csv.gz` says which records were in V1.
- Cache is now revision-keyed and hash-verified (`src/mlngrams/load.py`, `tests/test_cache.py`). Old
  caches in `~/.cache/mlngrams/<config>/` are ignored, so the first V2 run re-downloads.
- Stratify every V2 venue by version (`data/v2/version/`, `version_mix.csv`). V1's non-ICLR samples were
  accepted papers only.
- Gate 1 (`docs/v2-corpus-diff.md`, `results/v2/diff/`): the added ICLR and accepted-paper records are
  structurally like V1's; TMLR shifts only because of submission versions. Per-record structure for
  all V2 files is in `data/v2/structure/` (git-ignored; `scripts/v2/structure_scan.py`, ~20 min).
- Open: hand audit of the header-based version labels; TMLR year semantics; NeurIPS 2021 coverage.

### Lane E (V2): adversarial review (2026-10-15, first pass done)

**Doc:** `docs/v2-adversarial-review.md`. **Scripts:** `scripts/v2/review/` (none imports `mlngrams`).
**Tables:** `results/v2/review/`.

- Confirmed on our own SHA-256 of every text: all V1 records unchanged, 52,128 added. Version labels
  reproduce exactly and agree with the printed headers. TMLR published-stratum year = publication year
  (95.5%) or one year earlier.
- Function words reproduced with a separate counter (2024→2027: of −47.6%, and +39.4%). Every venue's
  latest cohort shows the largest step; ICLR→ICML revision barely moves "of".
- Defects: D1 unverified downloaders exposed to silent transfer corruption (10 of ~157 downloads here);
  D2 `count_ngrams.py` silently reads V1 without `MLNGRAMS_REVISION`; D3 title matching undercounts
  ICML↔ICLR overlap (≥ 16.3%, not 13.3%); D4 the directive's MuPDF result has no record in the repo.
- Second pass (2026-10-16) on Lanes B, C, D: their numbers reproduce with Lane E code. D2 fixed;
  D3 adopted by B and C, not D. Open asks: Lane C fig 3b compares levels across venues (C1); Lanes B/C
  still call TMLR year unresolved (E3 settles it for published papers); Lane D's ICML appendix step
  should drop ICLR-overlap papers (D-1). New: published TMLR "of" falls smoothly every quarter from
  2025 Q2 (`results/v2/review/e10_tmlr_by_publication_quarter.csv`).

### Lane B (V2): longitudinal replication (2026-10-15, Gate 2 done)

**Doc:** `docs/v2-replication.md` (comparison rules frozen in d3511aa before any V2 estimate).
**Scripts:** `scripts/v2/run_replication.sh` runs everything: `replication_flags.py` →
`count_ngrams.py --revision 2c0dd19 --merge-by-year` → `replication_views.py` → `make_tables.py` /
`longitudinal.py` → `paper_features.py` → `venue_replication.py` → `replication_compare.py`.
**Outputs:** `results/v2/replication/` (v2main = primary V2 view; v2def = V1 definitions; figures 2, 6, 7).

State: all per-year V1 findings survive; corpus-weighted pooled contrasts shift because 2025–26 are now
complete (negative result B-N1); the 2027 markers move in ICML/COLM/TMLR 2026 cohorts.
Git-ignored intermediates: `~/work/v2_body`, `~/work/v2_all`, `~/work/views*`, `~/work/features`
(≈ 1.5 h to rebuild; needs ~25 GB disk; the direct config can be deleted after the flags step).
Open: date TMLR 2026 records by OpenReview submission month (calendar test in `docs/v2-replication.md`);
check whether OpenReview id order tracks submission time (explains *test whether* 2026, V1 vs added).

### Lane D (V2): appendices and disclosures (2026-10-15, analysis done; labels pending)

**Doc:** `docs/v2-appendices-disclosures.md`. **Scripts:** `scripts/v2/appendix_scan_v2.py` →
`appendix_analyze_v2.py`; `disclosures_extract_v2.py` → `disclosures_analyze_v2.py`; `lane_c_v2.py`
(prereg `results/v2/disclosures/lane_c_v2_prereg.md`); `labelling_sample.py`, `score_labels.py`.
**Outputs:** `results/v2/appendices/` (fig 5 + table), `results/v2/disclosures/`.

State: appendix decomposition, disclosure inventory, stance, templates and Lane C on ICLR 2027
(reproduces) and ICLR 2026 done. Open: Bobby's 45 hand labels on the labelling page (export with
ArtifactData `list` on collection `labels`, then `score_labels.py`); same-author 2026 vs 2027
statements; NeurIPS 2025 checklist LLM answers. Lane C needs `scikit-learn`/`scipy` (not in
requirements). Git-ignored intermediates in `data/v2/{appendix,disclosures,lane_c,labelling}`.

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

## V2 Lane C: function words (2026-10-15)

`docs/v2-function-words.md` answers the directive's Agent C questions; summary in `docs/v2-findings.md`
(Lane C). Scripts `scripts/v2/lane_c_*.py` do not import `mlngrams`; per-paper counts are rebuilt into
`data/v2/lane_c/` (git-ignored, ~40 min). Open items: LaTeX-source check of body prose via arXiv
e-prints; NeurIPS 2026 (when released) is the first non-ICLR cohort that could test the ICLR 2027
step; arXiv rate-limits this environment's IP (HTTP 429), so lookups need ≥ 4 s spacing and long backoff.

## Gate 5 (V2): integration (2026-10-16, draft 2)

`docs/v2-integration.md` answers the directive's seven questions from the Gate 0/1 and Lane B–E docs and
adds one figure (`results/v2/integration/fig4c_marker_heatmap.png`, `scripts/v2/integration_marker_heatmap.py`,
from Lane B's `venue_metrics.csv`). Lane E second pass (ee1cb5f) folded in. Open before it is final: routed fixes C1, C2, D-1 (B1, B2 done);
Bobby's 45 disclosure labels (category shares are provisional until scored). Recommended next experiment:
a monthly arXiv-abstract series 2023–2026, ML and non-ML categories, with Lane C's counter.
