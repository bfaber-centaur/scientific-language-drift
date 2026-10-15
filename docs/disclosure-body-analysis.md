# Disclosure categories and paper-body language, ICLR 2027 (Lane C, Gate 4)

Exploratory and associational. The disclosure categories are self-reports, classified by a
rule-based classifier that passed Gate 3 narrowly (`docs/ai-disclosures.md` §6). A difference
between groups does not show that AI assistance caused it, and nothing here identifies
AI-generated text.

The plan was preregistered in `results/disclosures/lane_c_prereg.md` (commit ccfd54f), before any
body feature was computed.

Reproduce:

```
python3 scripts/disclosures/lane_c_features.py    # ~25 min, 4 workers; data/disclosures/lane_c_*.{parquet,npz}
python3 scripts/disclosures/lane_c_analysis.py    # contrasts, controls, overlap, scan, figures
```

## Population and body text

- **Papers:** 39,304 ICLR 2027 papers with a clean-tier disclosure and at least 1,000 body tokens.
- **Body text:** the main body before the references marker, with statement removal v2 applied.
  The disclosure span found by the Lane B extractor is also cut, which removed a further 1,133
  leaked disclosures. Tokenizer v1.3.
- **Groups (classifier v2):**
  - drafting 11,751
  - polish_only 5,354
  - other_use 21,411 (polish_plus 18,238; non-writing only 3,173)
  - unknown 535
  - none 253

  Explicit non-use (253) is too small and too heterogeneous for the planned three-way comparison,
  so it is shown only in the distribution figure.
- **Adjustment:** 40 TF-IDF topic clusters (`results/disclosures/lane_c_topics.csv`) and
  body-length deciles, entered as fixed effects.
- **Uncertainty:** effects are standardized differences with 1,000-resample bootstrap CIs.
  p-values come from 2,000 within-stratum label permutations, which also serve as the
  shuffled-label negative control. BH correction is applied per contrast.

## Result 1: drafting-disclosure papers are written in the "2027 register", polish-only papers are not

Primary contrast, drafting vs polish_only (`results/disclosures/lane_c_contrasts.csv`,
`fig_lane_c_heatmap.png`). Raw means are shown, with topic- and length-adjusted d and 95% CI:

| feature | drafting | polish_only | adjusted d [95% CI] |
|---|---:|---:|---|
| "we propose" (% of papers) | 39.9 | 66.5 | **−0.41** [−0.44, −0.38] |
| "a novel" | 5.4 | 11.8 | −0.22 [−0.26, −0.18] |
| "test whether" | 26.2 | 17.5 | +0.17 [+0.14, +0.20] |
| "held fixed" | 16.0 | 9.8 | +0.14 [+0.11, +0.17] |
| "percentage points" | 25.9 | 23.3 | +0.09 [+0.06, +0.12] |
| "results support" | 15.6 | 18.2 | +0.01 [−0.03, +0.04] (n.s.) |
| AI-associated words per 10k tokens (delve, intricate, pivotal, underscores, showcasing, realm) | 0.14 | 0.29 | −0.08 [−0.16, −0.04] |
| function-word share | 0.321 | 0.311 | +0.07 [+0.05, +0.09] |
| mean token length | 5.64 | 5.81 | −0.14 [−0.17, −0.12] |
| MATTR-500 | 243.4 | 241.6 | +0.16 [+0.13, +0.18] |
| repeated 4-gram share | 0.026 | 0.032 | −0.24 [−0.28, −0.21] |

- **Significance and size.** 10 of the 11 features pass BH at q < 0.05. The permutation null SDs
  of d are 0.01 to 0.02, and the observed effects lie far outside them. The effects are small to
  moderate; the largest is a 27-point gap in "we propose".
- **Prediction check.** The predictions carried over from the withdrawn N13 lead (fewer "we
  propose"; more "test whether" and "held fixed" in drafting papers) all hold, now with a
  validated classifier.
- **Robustness to formulaic disclosures.** Dropping disclosures that are at least 50% template or
  that sit in a near-duplicate cluster leaves 13,892 papers; every effect keeps its sign and size
  (`robust_d_adj`).
- **Robustness to adjustment.** Topic and length adjustment shrinks the style features (for
  example, function-word share falls from d 0.28 raw to 0.07) but barely changes the phrase
  features.
- **Other contrasts.** other_use vs polish_only sits between, in the same direction everywhere.
  Drafting vs polish_plus, which holds non-writing AI use roughly constant, keeps the same signs at
  about half the size (we propose −0.20, a novel −0.12, held fixed +0.08). So the pattern is not
  only "more AI use of any kind".
- **Effect of classifier error.** Drafting precision is about 0.86 on the full test2 set but may be
  as low as 0.71 (Lane D: simple-random strata). Most errors come from other_use, which itself lies
  between the two groups, so they attenuate the contrasts rather than create them. Check C2 below
  gives the corrected range.

**The direction is the opposite of the "AI words" intuition.** Papers whose authors report AI
*drafting* use the stereotyped AI vocabulary *less*. They also use fewer novelty formulas, shorter
words, more function words, more varied vocabulary and fewer repeated bundles. Polish-only papers
look like the 2023–2026 ICLR register. Drafting papers carry the 2027 break described in
`docs/findings.md` §3: "we propose" at 40% against 80% in 2023–2026, and "test whether" at 26%
against 2–5%.

### Exploratory word scan

This scan is lead-generating only. It covers the 5,000 most frequent body words, compares drafting
with polish_only, and uses a CMH test across topic clusters (`lane_c_scan.csv`, top 200).
- 3,167 of 5,000 words pass BH. Five within-topic shuffles of the labels gave 0 hits each.
- Words lower in drafting papers include *extensive, effectiveness, specifically, conduct, propose,
  achieves, thereby, demonstrate, framework, employ, enhance, summarized, ablation,
  respectively*.
- Words higher in drafting papers include *gives, give, every, own, per, run, what, read, never,
  was, ask, call*.
- So this is a broad register difference, with conventional ML-paper boilerplate on one side and
  plainer, more verbal prose on the other. It is not a handful of marker words.

## Result 2: disclosure length and specificity barely relate to body style

Rank correlations, adjusted for topic and length (`lane_c_disclosure_corr.csv`):
- **Disclosure length:** function-word share ρ = +0.12; all other features |ρ| ≤ 0.03.
- **Specificity:** |ρ| ≤ 0.07 for every feature (MATTR +0.07, repeated bundles −0.07).

Several of these pass BH only because n is 39k; none is large.

## Result 3: disclosures share vocabulary with their own paper beyond topic matching

`lane_c_overlap.csv` and `fig_lane_c_overlap.png` give the share of a disclosure's author-written
word types (template and stock wording removed) that appear in the paper's body. Each own body is
compared with 20 bodies matched on topic cluster and length decile, and with 20 random bodies:

| vocabulary | own body | matched | random | own − matched [95% CI] |
|---|---:|---:|---:|---|
| all author word types | 0.357 | 0.300 | 0.288 | +0.057 [0.056, 0.058] |
| only words found in ≥ 5% of bodies | 0.452 | 0.396 | 0.381 | +0.056 [0.055, 0.057] |
| stopword-profile cosine | 0.749 | 0.739 | 0.735 | +0.010 [0.010, 0.011] |

- **Enrichment.** 67% of papers overlap more with their own body than with their matched
  controls. The enrichment survives restriction to general vocabulary, so it is not only method
  names and datasets.
- **Matching is weak.** Topic matching captures only 0.012 of the 0.069 gap between own body and
  random. The 40 clusters are coarse, and some of the "beyond topic" overlap is finer-grained
  topical reuse.
- **By group.** Enrichment is larger for drafting papers than for polish-only ones (all words
  +0.060 vs +0.033; difference +0.027 [0.023, 0.031]). Drafting disclosures are longer and more
  concrete, so this partly reflects disclosure content (such as describing the paper's own
  pipeline) rather than a shared "fingerprint".
- **Stylistic fingerprint.** The stopword-profile similarity is real but tiny (+0.010).

## Strongest alternative explanation: who writes polish-only disclosures

Self-reported category tracks *who the authors are and when the text was written* at least as much
as how the prose was produced.

**Who.** "Language polishing only" is the typical disclosure of authors who draft themselves in a
second language. Formulaic academic English ("extensive experiments demonstrate the
effectiveness") is a documented register of such writing. Drafting-assistance papers often describe
agentic, verification-heavy workflows. This alternative could not be tested directly, because 2027
submissions are anonymous.

**When.** Among the 48 matched 2026→2027 resubmissions, whose text was largely written in 2026:
- polish_only is over-represented: 23% vs 14% in 2027 overall;
- drafting is under-represented: 15% vs 30%
(`results/disclosures/lane_c_resubmission_groups.csv`). Papers written before the 2027 cohort carry
the older register and tend to report polishing only. This is a small sample, but it points the
same way.

**What would separate the explanations:**
- repeat the contrast within de-anonymized camera-ready versions with author affiliations;
- check whether the drafting/polish gap appears within the same authors' papers;
- check whether the gap holds among papers that newly mention AI coding agents.

## Checks requested by the Lane D review (added after results; not preregistered)

Run with `python3 scripts/disclosures/lane_c_review_checks.py` (seed 20271016). Requests C1–C4 and
Gate 3 verdict (c) come from `docs/v1.5-review.md`. Nothing changed the conclusions.

| check | result | file |
|---|---|---|
| C1: overlap without the 1,303 disclosures (3.3%) that overran into bibliography or ethics text | Enrichment for all author words drops from +0.057 to +0.055; for general vocabulary from +0.056 to +0.053. The drafting minus polish_only gap grows slightly, from +0.026 to +0.028. | `lane_c_overlap_c1.csv` |
| C2: drafting precision anywhere from 0.71 to 0.86, assuming the false drafting labels come from other_use | Corrected effects are larger than observed. For "we propose", d is −0.44 at P = 0.86 and −0.49 at P = 0.71; "results support" stays near 0. | `lane_c_label_error.csv` |
| C3: group sizes per topic cluster | No cluster has fewer than 30 papers in either group (smallest: 66 drafting, 41 polish_only), so nothing was dropped and the estimates are unchanged. | `lane_c_topic_cells.csv` |
| C4: cluster bootstrap with 15,856 near-duplicate disclosure clusters as units | CIs widen by at most about 0.01 (for example "we propose" [−0.447, −0.373]). | `lane_c_robustness.csv` |
| (c): only papers where the surface wording agrees with the classifier (drafting cue in the drafting group; polish cue and no drafting cue in polish_only) | n = 10,966 vs 4,891. Every effect is within 0.02 of the main estimate (we propose −0.43, a novel −0.23, test whether +0.17). | `lane_c_robustness.csv` |

## Weak or null results (reported prominently)

- "results support" does not differ between groups in any contrast.
- The stereotyped "AI words" differ only slightly (d −0.08). They are rare (about 0.2 per 10k
  tokens) and *lower* in drafting papers.
- Disclosure length and specificity explain almost nothing about body style.
- The disclosure/body stylistic fingerprint (stopword-profile cosine) is about 0.01.

## Caveats

- **Labels.** Gate 3 passed narrowly. Both labellers are Claude, and no human labels were used.
- **Confounding.** Topic adjustment uses 40 unsupervised clusters, so residual topic confounding
  is likely; the shrinking style effects show that topic matters.
- **Scope.** Only one venue-year (ICLR 2027 submissions).
- **Removal quality.** Section and disclosure removal are imperfect: 1,133 disclosures were cut by
  this lane, and more text could remain.
- **Multiple comparisons.** The scan's 3,167 hits are not independent findings.
