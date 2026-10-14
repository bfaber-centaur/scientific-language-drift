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

**Interpretation.** Most of the large lexical change is what the field works on, not how it writes.

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

The jump is a step between 2023 and 2024 (10× in one year), after six flat years. The same 2024 peak and
2025 decline of "delve" appear in NeurIPS (6.5% in 2024 → 1.8% in 2025), TMLR (9.6% → 4.9% → 2.7%) and
COLM (11.7% → 1.9%) (`results/style_shift_checks.csv`, samples of ≤800 papers). Different words peak in
different years: delve/realm in 2024, underscores/showcasing in 2025.

**Interpretation (tentative).** A shared, time-limited vocabulary fashion. These words are widely
reported as overused by chat assistants of that period, so LLM-assisted writing is a candidate
explanation; so is ordinary imitation within a fast-growing field. The staggered decline (delve first)
is consistent with authors or tools dropping words once they became notorious, but that is not tested.

**Confounders.** ICLR 2025/2026 are partial samples (2026: 26% of submissions, by id order, plausibly
random); topic mix (LLM papers may use the words more for reasons of subject matter).

**Tests.** (a) Within-topic: compute prevalence separately for papers with and without "language
model(s)" in the abstract; if the 2024 step survives in non-LLM papers it is not topical. (b) Use the
OpenReview submission vs camera-ready versions of the same 2024 papers: does wording change between
them? (c) Compare against a pre-2023 frozen corpus (arXiv 2021–22) to fix the baseline.

## 3. ICLR 2027 breaks with every earlier year, and it is the new papers that are different

**Facts.** Share of papers containing the phrase (main body; submissions-only values in brackets):

| phrase | 2023 | 2025 | 2026 | 2027 |
|---|---|---|---|---|
| we propose | 80.2% | 81.8% | 79.8% [80.8%] | **50.7%** [51.3%] |
| a novel | 48.0% | 60.8% | 53.6% [55.4%] | **8.7%** [8.7%] |
| in this paper (per million) | 397 | 290 | 190 | **77** |
| test whether | 2.4% | 2.4% | 4.8% [4.8%] | **22.9%** [22.7%] |
| held fixed | 0.4% | 0.1% | 0.8% | **12.9%** |
| results support | 1.1% | 1.0% | 1.8% | **16.5%** |
| percentage points | 1.2% | 1.3% | 3.9% | **24.5%** |

"leverage", "notably" and "furthermore" also fall to their lowest level of the decade
(e.g. notably 54.6% → 16.1%). The shift is visible in the raw PDF text layer (`direct` config), not only in
the cleaned text, and it holds within submission versions, so it is not the camera-ready/submission mix.

**Paired resubmission test** (`scripts/resubmission_test.py`, `results/resubmission_summary.csv`). 55
papers rejected or withdrawn from ICLR 2026 and resubmitted to 2027 (matched by near-identical
abstracts). Their 2027 versions keep "we propose" (78% → 76%) and their stopword share (0.343 → 0.340),
while the cohort moved to 51%. They do drop some words: underscores 15% → 2%, notably 56% → 42%,
a novel 49% → 38%. Control pairs (2024→2025, 2025→2026) show no comparable drops.

**Self-reported AI use** (`scripts/ai_disclosure_strata.py`, 12,000 sampled 2027 papers, crude keyword
classes of the paper's own AI-use statement). Papers whose statement mentions AI help with *drafting*
text (n=4,452) use "we propose" in 43%, "test whether" in 25%, "held fixed" in 15%; those reporting
*language polish only* (n=5,011): 58%, 21%, 12%; the 42 statements classified as *no AI use*: 71%, 17%,
0%. (`results/ai_disclosure_strata_2027.csv`.)

**Interpretation (tentative).** The 2027 cohort (42k submissions, double 2026) is written in a
recognisably different register: fewer formulaic claims of novelty, more hypothesis-test phrasing.
Resubmitted papers mostly keep their old register, so the change sits in newly written papers rather
than in a cohort-wide editing pass. The gradient with self-reported drafting help is consistent with a
new generation of writing tools carrying a new style, but it is an association in self-reports with crude
classification, and the "no AI" group is tiny.

**Alternatives.** (1) A new population of submitters (the cohort doubled). (2) Author guidance or
reviewer incentives specific to ICLR 2027 (e.g. discouraging novelty claims) — not checked.
(3) Resubmission matching only finds lightly revised papers, so it under-represents rewrites.
(4) 2027 is a submission snapshot; earlier years mix in later revisions of the PDF.

**Tests.** (a) Check ICLR 2027 author/reviewer guidelines for wording advice. (b) Repeat on a venue with
2026-written papers, e.g. TMLR 2026 later in the year or ICML 2026 when extracted. (c) Fuzzy-match more
resubmissions (title + first page) to enlarge the paired sample. (d) Hand-label 100 AI-use statements to
measure the keyword classifier's error before reading anything into the gradient.

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

**Alternatives.** More bullet lists, tables-as-text and inline lists in recent papers (fragments with few
function words); extraction differences in newer LaTeX templates. **Test.** Restrict to sentences of
≥15 tokens ending in a period and recompute; if the decline persists, it is in running prose.

## 5. The "across" construction

**Facts.** across diverse: 0.2–1.0% of papers in 2017–23, 9.1% (2024), 16.4% (2025), 34.1% (2026),
13.8% (2027). "performance across", "across three/four/five", "experiments across", "across models"
rise in prevalence by 9–18 percentage points between the early and recent cohorts.
(`changes_content_bigrams_main.csv`, list `riser_pp_cw`.)

**Interpretation.** Partly evaluation practice (multi-benchmark, multi-model evaluation became standard),
partly a phrasing fashion ("across diverse" behaves like the words in finding 2 and drops in 2027).
**Test.** Count "across" + number + noun versus "across diverse/various": the first should track the
number of benchmarks reported; the second should not.

## Limitations

- Observational; no claims about authorship of any paper. Papers are not verified human-only text.
- ICLR 2025 uses only the unbiased id stratum (4,781 of 6,160 extracted papers); ICLR 2026 is 26% of
  submissions (plausibly random by id). 2027 is a submission snapshot (October 2026).
- Aggregate tables cannot show single-paper dominance of rare phrases; rankings require ≥1% prevalence and
  ≥20 papers in the higher cohort, which limits but does not eliminate this.
- The tokenizer and section stripping are heuristic; QA found and fixed six tokenizer defects
  (`docs/qa.md`). Remaining known artifacts: inline-math residue that escapes the omission markers, leaking
  table cells, author-year citations reduced to "Name et al".
