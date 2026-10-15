# Lane C preregistration: disclosure categories vs paper-body language (ICLR 2027)

Written 2026-10-15, after Gate 3 (classifier v2 on held-out test2) and before any body-text
feature was computed for any paper. Committed before the analysis script was run.

## Status of the labels

Classifier v2 passes the Gate 3 rule only on point estimates (drafting P = R = 0.863; polish_only
P 0.938, R 0.833; lower 95% bounds 0.74 and 0.61). Everything below is exploratory and
associational. Self-reported AI use is not verified authorship provenance; a group difference does
not show that AI assistance caused it.

## Population and body text

- ICLR 2027 papers whose disclosure was extracted in the `clean` tier
  (`data/disclosures/iclr2027.parquet`), classified by `mlngrams.disclosure_classify` v2 into
  groups as in `scripts/disclosures/eval_groups.py`: `drafting` (any drafting claim),
  `polish_only` (polish is the only category), `other_use`, `none`, `unknown`. For the second
  secondary contrast, `other_use` is split into `polish_plus` (polish plus non-writing uses, no
  drafting) and `nonwriting` (no polish, no drafting).
- Body = `load.main_body` (text before the references marker) -> `sections.strip_statements` (v2)
  -> the disclosure span located by `mlngrams.disclosures.extract` on that body is cut as well
  (the Gate 2 leak of ~1,700 disclosures). Tokenizer v1.3. Papers with < 1,000 body tokens are
  dropped.

## Primary contrast and features (fixed here)

Primary contrast: **drafting vs polish_only**. Secondary: (s1) other_use vs polish_only;
(s2) drafting vs polish_plus. s2 matters because drafting papers usually also report coding and
other uses, so drafting vs polish_only partly contrasts "more AI use of any kind" with "less";
s2 holds non-writing use roughly constant. `none` is
reported descriptively only if it has >= 100 papers.

Features (11), each per paper:
1. `ai_words_p10k`: delve/delves/delved/delving, intricate/intricately, pivotal,
   underscore/underscores/underscored/underscoring, showcase/showcases/showcased/showcasing,
   realm/realms, combined, per 10,000 tokens.
2-7. Prevalence (paper contains, 0/1) of: "we propose", "a novel", "test whether", "held fixed",
   "results support", "percentage points".
8. `func_share`: share of tokens in `filters.STOPWORDS`.
9. `mean_tok_len`: mean letters per token, excluding `<num>`.
10. `mattr500`: moving-average type-token ratio, window 500 tokens.
11. `bundle_rep`: share of 4-gram positions whose 4-gram occurs >= 3 times in the same body.

Predictions (from the withdrawn N13 lead, which used an invalid classifier): drafting papers use
"we propose" less, and "test whether" and "held fixed" more, than polish_only papers. No
directional prediction for the other features; expected effects are small (|d| < 0.1).

## Estimation

- Topic: 40 k-means clusters (seed 20271015) on TF-IDF of title + first 3,000 body characters
  (sublinear tf, English stop words, min_df 20, max 20,000 features). Length: body-token deciles.
- Effect: OLS of the feature on the group indicator with topic-cluster and length-decile fixed
  effects; reported raw and as a standardized difference (divided by the pooled SD).
  Unadjusted differences are reported alongside.
- Uncertainty: 95% percentile bootstrap over papers (1,000 resamples, seed 20271015).
- Negative control / p-values: permute group labels within topic x length-decile strata
  (2,000 permutations); two-sided p. Benjamini-Hochberg at q = 0.05 across the 11 features of the
  primary contrast (and separately for the secondary contrast).
- Robustness: (a) drop papers whose disclosure is >= 50% template tokens or sits in a
  near-duplicate cluster; (b) unadjusted.
- Label error: with drafting precision ~0.86 and most false positives coming from other_use,
  observed differences are expected to be attenuated; no correction is applied, the bound is stated.

## Disclosure length and specificity

Spearman correlation of disclosure word count and of specificity (number of v2 categories + named
tool 0/1 + author-attributed token count, each rank-transformed and averaged) with features 1, 8-11,
within topic x length strata (rank residuals). BH across these 10 tests.

## Disclosure/body overlap

- D = the disclosure's author-attributed word types (not template- or stock-covered; lowercase;
  not stopwords, not `<num>`, >= 3 letters).
- Overlap = share of D that occurs in the body. Control = mean overlap of the same D with 20 bodies
  drawn from the same topic cluster and length decile (seed 20271015). Enrichment = own - control.
- Run on (i) all of D and (ii) D restricted to general vocabulary (types in >= 5% of bodies) to
  separate topical from stylistic reuse.
- Stylistic fingerprint: cosine similarity of 100-stopword frequency profiles, disclosure vs own
  body vs the 20 matched bodies.
- Prediction: enrichment > 0 for all of D (topical terms), near zero for general vocabulary and
  for the stopword fingerprint.

## Exploratory scan (after the above)

Body word types with document frequency >= 1% (top 5,000): prevalence difference drafting vs
polish_only, Cochran-Mantel-Haenszel test across topic clusters, BH q = 0.05. Reported as leads
only.
