# Findings: a decade of language in ICLR papers

_Exploratory report, 2026-10-14. Dataset `woog/open-text-detector-papers` @ `cb5553e`. ICLR 2017–2027,
75,118 papers, main body only (text before the reference list; required statement sections cut). Methods in
`README.md`, corpus caveats in `docs/corpus.md`, QA in `docs/qa.md`._

Each finding is split into **facts** (what the tables show), **interpretation** (tentative) and
**hypotheses / tests** (what would confirm or kill it). Nothing here is evidence about who or what wrote
any individual paper.

## Here are your bigrams

- Per-year top-100 raw and content bigrams (also unigrams, trigrams), with counts, per-million rates and
  paper prevalence: `results/full/body/top100_n2_{raw,content}_by_year.csv`.
- Pooled over years: `results/full/body/top100_n2_*_pooled_yb.csv` (year-balanced: each year weighs the
  same) and `*_pooled_cw.csv` (corpus-weighted; 55% of papers are ICLR 2027, so this is mostly 2027).
- Full annual time series for the top 100 content and raw bigrams and a pre-registered watchlist:
  `results/full/longitudinal/timeseries_*.csv`; rising/falling rankings: `changes_*.csv`.
- Raw tables are dominated by function words and numbers ("of the", "<num> <num>", "in the"), as
  expected. Year-balanced top content bigrams: neural network(s), learning rate, training data, related
  work, reinforcement learning, loss function, gradient descent, deep learning, language models.
- It is also true that scientific prose is repetitive: "related work" is in 77% of papers, "can be" in
  ~99% of papers through 2025.

## 1. Topic turnover explains the biggest movers

**Facts.** Largest risers 2017–21 → 2025–27 (log2 of smoothed per-million rates, both corpus-weighted
and year-balanced, and within submission versions only): foundation models, flow matching, KV cache,
LLM agents, visual tokens, preference optimization, vision-language models, in-context learning,
reasoning traces, instruction tuning. Largest fallers: Google Brain, LSTM cell/layer/model, seq2seq,
word vectors, GAN training/objective, Penn Treebank, Titan Xp. "neural network" is in 80% of 2017
papers and 7% of 2027 papers; "language models" goes from 9% to 52% (2026).
(`results/full/longitudinal/changes_content_bigrams_main.csv`, `fig1_watchlist_topical.png`.)

**Interpretation.** The largest *relative* changes (log2 ratios, which favour n-grams starting near
zero) are topical: what the field works on. The largest changes in *paper share* are mostly reporting and
rhetorical phrases instead (experimental setup +22 pp, percentage points +19, test whether +16, across
diverse +15, held fixed +10; list `riser_pp_cw`), which is why findings 3 and 5 exist.

**Confounders / alternatives.** Affiliation n-grams (Google Brain, Facebook AI) also fall because
camera-ready versions (with author blocks) are rarer in 2027; within submissions only the drop is smaller.

**Test.** Already done: rankings hold under year-balanced weighting and in the under-review stratum.

## 2. A 2024 burst of rhetorical words, fading by 2027

**Facts.** Share of ICLR papers (main body) containing the word:

| word | 2017–23 | 2023 | 2024 | 2025 | 2026 | 2027 |
|---|---|---|---|---|---|---|
| delve | 0.5–1.0% | 1.0% | **10.7%** | 6.1% | 1.2% | 0.1% |
| underscores | ≤0.6% | 0.4% | 10.8% | **14.9%** | 12.6% | 0.8% |
| intricate | 1–2% | 1.8% | **15.0%** | 14.4% | 7.9% | 1.1% |
| pivotal | ≤1.5% | 1.1% | **11.7%** | 9.6% | 5.6% | 1.0% |
| showcasing | ≤1.2% | 1.2% | 9.8% | **13.1%** | 5.0% | 0.4% |
| realm | ≤1.2% | 1.0% | **9.9%** | 6.1% | 0.9% | 0.3% |

The jump is a step between 2023 and 2024 (8–27× in one year, depending on the word), after seven flat
years (2017–2023). The same 2024 peak and
2025 decline of "delve" appear in NeurIPS (6.5% in 2024 → 1.8% in 2025), TMLR (9.6% → 4.9% → 2.7%) and
COLM (11.7% → 1.9%) (`results/style_shift_checks.csv`, samples of ≤800 papers). Different words peak in
different years: delve/realm in 2024, underscores/showcasing in 2025.

**Interpretation (tentative).** A shared, time-limited vocabulary fashion. These words are widely
reported as overused by chat assistants of that period, so LLM-assisted writing is a candidate
explanation; so is ordinary imitation within a fast-growing field. The staggered decline (delve first)
is consistent with authors or tools dropping words once they became notorious, but that is not tested.

**Confounders.** ICLR 2025/2026 are partial samples (2026: 26% of submissions, by id order, plausibly
random); topic mix (LLM papers may use the words more for reasons of subject matter).

**Done: within-topic test.** In papers whose abstract does not mention language models or LLMs, the
step survives: delve 0.7% → 10.1%, intricate 2.8% → 14.6%, pivotal 1.6% → 12.2% (2023 → 2024;
`scripts/qa_findings.py`, `docs/review_findings.md`). So it is not a topical effect of LLM papers.

**Further tests.** (b) Use the
OpenReview submission vs camera-ready versions of the same 2024 papers: does wording change between
them? (c) Compare against a pre-2023 frozen corpus (arXiv 2021–22) to fix the baseline.

## 3. ICLR 2027 breaks with every earlier year

**Facts.** Share of papers containing the phrase (main body; submissions-only values in brackets):

| phrase | 2023 | 2025 | 2026 | 2027 |
|---|---|---|---|---|
| we propose | 80.2% | 81.8% | 79.8% [80.8%] | **50.7%** [51.3%] |
| a novel | 48.0% | 60.8% | 53.6% [55.4%] | **8.7%** [8.7%] |
| in this paper (per million) | 397 | 293 | 187 | **77** |
| test whether | 2.4% | 2.4% | 4.8% [4.8%] | **22.9%** [22.7%] |
| held fixed | 0.4% | 0.1% | 0.8% | **12.9%** |
| results support | 1.1% | 1.0% | 1.8% | **16.5%** |
| percentage points | 1.2% | 1.3% | 3.9% | **24.5%** |

"leverage", "notably" and "furthermore" also fall to their lowest level of the decade
(e.g. notably 54.6% → 16.1%). The shift is visible in the raw PDF text layer (`direct` config), not only in
the cleaned text, and it holds within submission versions, so it is not the camera-ready/submission mix.
It is not driven by a topic or a shared template either: the four 2027 markers (test whether, held fixed,
results support, percentage points) have similar rates in LLM and non-LLM papers, only 3.9% of 2027
papers contain three or more of them (2.4% expected if independent), and within-2027 near-duplicates are
negligible (28 pairs).

**Paired resubmission test** (`scripts/resubmission_test.py`, `results/resubmission_summary.csv`). 55
papers from ICLR 2026 resubmitted to 2027 (matched by near-identical abstracts). They move only part of
the way with the cohort (change in share of papers, pairs vs cohort): underscores −13 vs −12 pp,
notably −15 vs −38, a novel −11 vs −45, leverage −11 vs −53, we propose −2 vs −32. Their stopword share
drifts (−0.003), but 2025→2026 control pairs drift more (−0.007), so resubmissions make roughly a quarter
of the cohort's function-word change in both transitions. Two caveats: matching selects lightly revised
papers, and the pair measure uses prefix matching ("leverage" also counts "leveraging") while the cohort
figures are exact n-grams.

**Interpretation (tentative).** The 2027 cohort (42k submissions, double 2026) is written in a
recognisably different register: fewer formulaic novelty claims, more hypothesis-test phrasing.
Resubmitted papers move partly (fully on "underscores", barely on "we propose"). This cannot separate a
new population of papers and authors from an editing pass that light revisions only partly reflect.
Nothing in these data points to writing tools specifically rather than a new population or new guidance.

**Alternatives.** (1) A new population of submitters (the cohort doubled). (2) Author guidance or
reviewer incentives specific to ICLR 2027 (e.g. discouraging novelty claims), not checked.
(3) Resubmission matching only finds lightly revised papers, so it under-represents rewrites.
(4) 2027 is a submission snapshot; earlier years mix in later revisions of the PDF.

**Tests.** (a) Check ICLR 2027 author/reviewer guidelines for wording advice. (b) Repeat on a venue with
2026-written papers, e.g. TMLR 2026 later in the year or ICML 2026 when extracted. (c) Fuzzy-match more
resubmissions (title + first page) to enlarge the paired sample, including heavily revised ones.
(d) Self-reported AI use: a first keyword classifier of 2027 AI-use statements agreed with hand labels on
only ~50% of 40 statements (it reads disclaimer lists as positive use), so its gradient is not reported
(`docs/negative-results.md` N13). A negation-aware classifier validated on ~100 hand-labelled statements
would make the comparison usable; it would still be self-report and associational.

## 4. Function words are thinning out, across venues, since well before LLMs

**Facts.** "of the" per million bigram positions: 8,784 (2017), 7,026 (2021), 6,349 (2024), 5,809 (2025),
4,172 (2026), 3,338 (2027). Stopword share of tokens: 39.6% → 37.0% (2024) → 33.2% (2026) → 32.1% (2027).
"can be" falls from ~2,160 per million (2017–23) to 680 (2027). The same direction and acceleration after
2024 appears in the raw `direct` text layer and in NeurIPS ("of the" 6,608 → 4,663, 2021→2025), TMLR
(7,184 → 5,292, 2022→2026) and COLM (5,146 → 3,922, 2024→2025). Mean token length rises
(5.1 → 5.7 letters). In 2027 the whole per-paper distribution shifts (median stopword share 0.37 in 2024,
0.31 in 2027), not just a tail. (`results/full/longitudinal/denominator_diagnostics.csv`,
`results/style_shift_checks.csv`.)

**Interpretation (tentative).** Prose is getting denser and more nominal (more noun compounds, fewer
"the X of the Y" constructions). A slow trend existed before 2023; it roughly doubles in speed from 2024.

**Consequences for this study.** Every per-million rate for 2026/2027 sits on a shrinking function-word
base, so content-bigram rates are inflated slightly in those years. Prevalence (share of papers) is less
affected; the findings above are stated in prevalence where possible.

**Done: running-prose test.** In segments of ≥15 tokens only, stopword share is 0.416 / 0.392 / 0.349
/ 0.338 (2017 / 2024 / 2026 / 2027) and "of the" falls from 9,721 to 3,591 per million. Short fragments do
grow (the long-segment token share drops from 0.68 to 0.60 in 2027) but do not explain the trend. The
biggest single-year step is 2025 → 2026 (−2.8 points of stopword share vs −1.1 for 2026 → 2027), so 2027
is not special on this measure. (`docs/review_findings.md`.)

**Alternatives.** Extraction differences in newer LaTeX templates (partly ruled out by the raw-layer
check); a shift in paper genre (more empirical/benchmark papers) within ML.

## 5. The "across" construction

**Facts.** across diverse: 0.2–1.0% of papers in 2017–23, 9.1% (2024), 16.4% (2025), 34.1% (2026),
13.8% (2027). "performance across", "across three/four/five", "experiments across", "across models"
rise in prevalence by 9–18 percentage points between the early and recent cohorts.
(`changes_content_bigrams_main.csv`, list `riser_pp_cw`.)

**Interpretation.** Partly evaluation practice (multi-benchmark, multi-model evaluation became standard),
partly a phrasing fashion ("across diverse" behaves like the words in finding 2 and drops in 2027).
**Partial test.** The two uses already separate in 2027: "across diverse" falls (34.1% → 13.8%) while
"across three/four/five" keep rising (15.3 → 19.4%, 9.7 → 14.0%, 6.7 → 11.1%, 2026 → 2027). Next: relate
"across <number>" to the number of benchmarks reported per paper.

## Sensitivity: appendices included

The all-text run (`results/full/alltext/`, change columns `log2_cw_alltext` in
`results/full/longitudinal/changes_*.csv`) gives the same picture: for the top-100 risers, fallers and
paper-share risers, Spearman correlation of the log2 changes between body-only and all text is 0.78 / 0.87
/ 0.99, median absolute difference 0.3 bits, and no riser or faller changes sign. Two paper-share risers
flip sign when appendices are included: *related work* and *ablation study*, which move between the main
text and the appendix over time (`docs/negative-results.md` N5).

## Subgroups of the 2027 shift

The 2027 shift is population-wide rather than carried by a subgroup: the per-paper stopword-share
distribution moves as a whole (finding 4); the new markers are similar in LLM and non-LLM papers and
rarely co-occur (finding 3); it holds within submission versions; resubmitted papers move partly
(finding 3). Not yet split: by research area beyond LLM/non-LLM, by paper length, or by first-time vs
returning authors (author identities are anonymous in 2027).

## Appendix growth (Lane A, 2026-10-15)

_Full write-up: [`docs/appendix-growth.md`](appendix-growth.md); tables `results/appendix/`. Descriptive._

**Fact.** The growth of ICLR papers is appendix growth. Median PDF length went from 13 pages (2017) to 24
(2027); the main body stayed at 8.5–10 pages and ~4,300–5,100 prose tokens, tracking the page limit; the
reference list grew by about half a page; the appendix went from 1.5 to 12 pages (median 372 → 4,151
tokens, P25 0 → 2,195). The appendix accounts for more than all of the growth in mean prose per paper,
because main-body prose fell slightly. It holds within submissions only (137 → 4,158 tokens), within 305
resubmitted papers (appendix +20%, main body +0.7% per resubmission), and in NeurIPS, TMLR, COLM and CoRL
wherever appendices are inside the PDF. Growth is broad, not driven by a few huge papers: the top decile's
share of appendix tokens fell from 41% to 32%.

**Fact.** In ICLR, ≥ 97% of post-reference text is appendix (63 hand-checked papers; bibliography residue
0.3–1.5%, statements ≤ 1.2% of characters). The earlier study's "text after the references" share
(7.4% → 47.2%) is a good proxy for ICLR, but not for NeurIPS 2021–22, where it is mostly the paper
checklist.

**Fact.** Every kind of appendix material grew, roughly in proportion: implementation/experimental details
and additional results are a third of the growth, proofs a tenth; examples/prompts doubled in 2024;
extended related work and limitations moved into appendices from ~2020 (heading rules agree with hand
labels on 85% of 154 headings).

**Fact.** Growth compounds at ~18% a year after a fast 2017–19 start, with the largest jump in 2026→2027
(+65% in submissions). Page-limit changes explain main-body length but not ICLR appendix growth: ICLR has
allowed unlimited same-PDF appendices since 2017, and TMLR, which has no page limit, also grows.

**Hypotheses (untested).** Reviewer expectations (camera-ready appendices are ~2× the same year's
submissions); cheaper production of supplementary material; and for 2027 a changed submitter population
(the cohort doubled). Main-body prose per page fell 7–9% in 2026–27 at an unchanged page count; open.

## Limitations

- Observational; no claims about authorship of any paper. Papers are not verified human-only text.
- ICLR 2025 uses only the unbiased id stratum (4,781 of 6,160 extracted papers); ICLR 2026 is 26% of
  submissions (plausibly random by id). 2027 is a submission snapshot (October 2026).
- Aggregate tables cannot show single-paper dominance of rare phrases; rankings require ≥1% prevalence and
  ≥20 papers in the higher cohort, which limits but does not eliminate this.
- The tokenizer and section stripping are heuristic; QA found and fixed six tokenizer defects
  (`docs/qa.md`). Remaining known artifacts: inline-math residue that escapes the omission markers, leaking
  table cells, author-year citations reduced to "Name et al".
