# Adversarial review of docs/findings.md (Agent D), 2026-10-14

**Inputs.** `~/work/full_body` (body-only, ICLR 2017–2027, sections v2, tokenizer v1.3), `results/`, and
`results/full/longitudinal/`. `~/work/full` (all text) had not finished, so it was not used.

**New checks.** `scripts/qa_findings.py` draws a per-paper sample: 1,000 papers per year for 2021–2026,
all 486 for 2017, and 3,000 for 2027. It takes only on-sample papers from `docs.parquet` and uses the
same body extraction, statement cut and tokenizer as the main pipeline. The per-paper flags were
written to the scratchpad, not the repo. Its estimates agree with the full tables to within about 1
point, e.g. "we propose" in 2027 is 47.9% here vs 50.7% in the full table.

**Number check.** Every number in findings.md was compared with its source table. All of them match,
except for two values.

## Finding 1: topic turnover. Verdict: keep, soften the interpretation
**Numbers.** All correct:
- neural network: 80.2% of papers in 2017, 7.3% in 2027.
- language models: 8.8% in 2017, 51.7% in 2026.
- The listed risers and fallers are the top entries of `changes_content_bigrams_main.csv`.
- Affiliations fall less within submissions: google brain log2 -7.94 overall vs -5.52 in submissions.

**Break attempt.** The log2 ranking with k=5 puts n-grams that start near zero at the top by
construction, and those are nearly always topical. When I ranked by percentage-point change in paper
share instead (`riser_pp_cw`), most of the top 30 were not topical. Examples:
- experimental setup +22
- percentage points +19
- main results +19
- performance across +18
- test whether +16
- across diverse +15
- results support +13
- held fixed +10
- ask whether +10

**Fix.** Replace "Most of the large lexical change is what the field works on" with: "The largest
*relative* changes are topical. The largest changes in *paper share* are mostly reporting and
rhetorical phrases (findings 2–5)."

## Finding 2: 2024 burst of rhetorical words. Verdict: keep
**Numbers.** The table and the NeurIPS, TMLR and COLM figures all match `ngrams_n1` and
`style_shift_checks.csv`. "10× in one year" is approximate: delve rose 10.7×, intricate 8×,
underscores 27×.

**Break attempt (non-LLM papers).** I flagged papers whose abstract mentions language models or
LLMs. The 2024 step holds in the other papers:

| word, non-LLM papers | 2023 | 2024 |
|---|---|---|
| delve | 0.7% | 10.1% |
| intricate | 2.8% | 14.6% |
| pivotal | 1.6% | 12.2% |

LLM papers have similar or slightly higher rates (delve 14.3% in 2024), so the burst is not a topic
effect. Run test (a) and report it as done.

**Fix (minor).** "after six flat years" should be "after seven flat years (2017–23)".

## Finding 3: ICLR 2027 break. Verdict: keep the cohort facts; soften the resubmission claim; drop the AI-disclosure gradient
**Numbers.** The table, the bracketed submission-only values, "notably 54.6% → 16.1%" and the
resubmission and disclosure figures all match their tables. One row is off: "in this paper" per
million should read 397 / **293** / **187** / 77 (from `ngrams_n3`), not 397 / 290 / 190 / 77.

**Concentration and topic check.** The four 2027 markers are not tied to a topic. In 2027:

| marker | non-LLM papers | LLM papers |
|---|---|---|
| test whether | 20% | 27% |
| held fixed | 14% | 12% |
| results support | 16% | 16% |
| percentage points | 22% | 31% |

They are also not template-like clusters:
- 3.9% of 2027 papers contain three or more of the four markers, against 2.4% expected if they occurred independently. That is mild co-occurrence only.
- Within-2027 near-duplicates are negligible (28 pairs).
- Their contexts are varied, e.g. "these results support" (13.8% of papers), "to test whether" (10.2%).

The break is broad, across the whole cohort.

**Resubmission control: the claim does not hold as written.**
- **Stopwords.** The control pairs drift *more* on stopword measures than the 2026→2027 pairs:
  - 2025→26: stop share -0.0066 [CI -0.011, -0.0025]; "of the" -481 per million [-839, -120]
  - 2026→27: stop share -0.0029 [-0.0055, -0.0005]; "of the" -142 [-386, +106]

  Measured against the cohort, resubmitted papers capture about the same fraction of the cohort's
  stopword change in both transitions:
  - 2025→26: 0.0066 of a 0.030 drop, about 22%
  - 2026→27: 0.0029 of a 0.012 drop, about 24%

  So "stopword share kept" says nothing special about 2027.
- **Marker words.** Here the 2026→27 pairs do move, while the controls do not. Using the same
  prefix-match measure on both sides:

  | phrase | resubmission pairs (n=55) | 2026→27 cohort | share of cohort move |
  |---|---|---|---|
  | we propose | -2 pp | -32 pp | ~6% |
  | a novel | -11 pp | -45 pp | ~25% |
  | notably | -15 pp | -38 pp | ~40% |
  | leverage | -11 pp | -53 pp | ~20% |
  | underscores | -13 pp | -12 pp | ~100% |

  The pairs move part of the way: all of it for underscores and almost none for "we propose".
- **Selection.** Pairs were matched on an identical 300-character abstract prefix or on shingle
  Jaccard ≥ 0.3 over the first 2,000 characters. That selects papers whose opening text was kept, so
  some "keeping the old register" is built in.
- **Measure mismatch.** The pairs use prefix matching ("leverage" also counts leverages and
  leveraging), while the cohort figures come from exact n-gram tables. Compare like with like.

**Fix.** Replace "Resubmitted papers mostly keep their old register, so the change sits in newly
written papers" with: "Resubmitted papers move part of the way: they drop underscores as much as the
cohort, and notably, a novel and leverage by 20–40% of the cohort change, but they barely change
'we propose'. Their stopword drift is no different from the 2025→26 control. The matching selects
lightly revised papers. This is consistent with both new-population and editing explanations and
cannot separate them." Delete "Control pairs show no comparable drops", or limit it to the marker
words.

**AI-disclosure strata.** I hand-labelled 40 sampled 2027 statements and compared them with the
classifier's labels:
- Overall agreement was about 21/40 (~50%).
- Only 5 of the 12 "drafting" labels were right. The drafting rule fires on the negated lists in the
  standard ICLR 2027 disclosure wording, e.g. a statement disclaiming any use "to assist in the
  writing of proofs".
- Polish-only statements were mislabelled "other" ("manuscript editing", "language revision") and
  vice versa ("typo" in a statement about checking derivations).
- One extraction captured only an omission marker.
- No "none" statement appeared in the 40.

A roughly 50%-accurate classifier, plus a "none" group of 42 papers, cannot support the gradient.
**Fix:** drop the gradient paragraph from the findings, or move it to "tests" pending a
negation-aware classifier. If it is kept anywhere, report the measured error.

**Statement leakage.** In 1.7% of 2027 papers, AI-use prose sits just before the heading because of
extraction order, so it escapes the cut. That is negligible here.

## Finding 4: function words thinning. Verdict: keep
**Numbers.** All match:
- "of the" per million: 8,784 / 7,026 / 6,349 / 5,809 / 4,172 / 3,338.
- Stopword share: 39.6 / 37.0 / 33.2 / 32.1%.
- "can be": 2,161–2,192 per million through 2023, then 680 in 2027.
- Venue figures match, and mean token length goes 5.1 → 5.7.
- Median stopword share: 0.372 (2024), 0.313 (2027).

**Break attempt: segments of ≥ 15 tokens only.** Segments end at `.!?;:` and math characters, so
they approximate sentences. The decline persists in running prose:
- stopword share: 0.416 (2017) → 0.392 (2024) → 0.349 (2026) → 0.338 (2027)
- "of the" per million: 9,721 → 7,169 → 4,642 → 3,591

The share of tokens in long segments also falls, from 0.68 to 0.60 in 2027, so fragments add a
little but do not explain the trend.

**Fix.** Report this test as done. Also state that 2025→26 is the largest single-year step (-2.8
points in the full table), larger than 2026→27 (-1.1 points), so "accelerates after 2024" is right but 2027 is not
special on this measure.

## Finding 5: "across" construction. Verdict: keep
**Numbers.** "across diverse": 0.2–1.0% → 9.1 / 16.4 / 34.1 / 13.8% ✓. The pp_cw rises are 9.1–17.8 ✓.

**Cheap version of the proposed test.** The paper-share tables already separate the two uses:
- "across diverse" falls in 2027 (34.1 → 13.8%).
- "across three / four / five" keep rising (15.3 → 19.4, 9.7 → 14.0, 6.7 → 11.1%).

Fashion and evaluation practice diverge as predicted. **Fix:** cite this as partial support.

## General
- The wording "consistent with a new generation of writing tools" (finding 3) is acceptable only
  after the disclosure gradient is removed. Without it, nothing in the data points to tools in
  particular over a population change or new guidelines.
- 2027 is 55% of all papers and is a submission snapshot. Keep every pooled claim year-balanced.
