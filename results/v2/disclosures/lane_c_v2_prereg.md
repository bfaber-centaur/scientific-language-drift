# Lane D (V2) preregistration: the Lane C analysis on new cohorts

Written 2026-10-15, before any V2 body feature was computed. Committed before
`scripts/v2/lane_c_v2.py` was run on any cohort.

## What is reused unchanged

`results/disclosures/lane_c_prereg.md`: body definition, the 11 features, groups (classifier v2,
frozen at 5c955d0), the three contrasts, topic (40 k-means clusters on TF-IDF of title + first 3,000
body characters) and length-decile fixed effects, bootstrap CIs, within-stratum label permutations
(the shuffled-label control), BH correction, the formulaic-disclosure robustness subset, and the
disclosure/body overlap measure with 20 topic- and length-matched control bodies. The scripts are
imported, not copied (`scripts/v2/lane_c_v2.py`). The only changes are input/output paths, the
omissions file read for bodies, and the stock-wording threshold, scaled to cohort size
(max(5, 50 / 39,351 of the cohort's clean disclosures)).

## Cohorts, in order

1. **ICLR 2027 on the V2 pin** (reproduction). Every ICLR 2027 record is byte-identical in V2, so
   group sizes and effects should match `results/disclosures/lane_c_contrasts.csv` up to the
   V2 extractor's table-of-contents skip (expected to touch only a handful of papers). A larger
   difference is a defect to report.
2. **ICLR 2026, all versions, then submissions only.** 2026 is now complete (19,732 papers). ICLR
   2026 asked for an LLM-usage section only when LLM use was "significant", allowed it in the
   appendix, and supplied no template (`policies.md`). So the 2026 disclosers are self-selected,
   and the 2026 polish-only group is people who disclosed polishing voluntarily.
3. **COLM 2026 and ICML 2026**, only if both drafting and polish_only have >= 100 clean-tier
   papers. Otherwise group rates are reported descriptively, with no inference.

## Predictions

- If the ICLR 2027 drafting vs polish-only gradient reflects who reports what (not the 2027
  template or the 2027 cohort), ICLR 2026 shows the same signs on the three strongest 2027
  features: "we propose" lower in drafting papers, "a novel" lower, AI words lower.
- No prediction for magnitude: selection into disclosure differs (voluntary in 2026).
- Overlap: own-body enrichment over matched controls stays positive (2027: +0.057 of types) and the
  stopword fingerprint stays near zero.

## Amendment (2026-10-15, before the ICLR 2026 run)

The V1.5 clean tier rejects statements that end at the end of the text. 87% of ICLR 2026 statements
are the paper's last section, so the 2026 run uses the V2 tier (`tier_v2` in
`scripts/v2/disclosures_analyze_v2.py`: end-of-text statements accepted when line or run-in form, no
omission marker, ≤ 3,000 characters, no bibliography residue). Fixed before any 2026 body feature
was computed; the ICLR 2027 reproduction keeps the V1.5 tier. Predictions unchanged.

## Status of the labels

Classifier v2 was validated only on ICLR 2027 statements, and only against Claude labels. On other
cohorts its labels are **provisional** until checked against Bobby's hand labels
(`results/v2/disclosures/labelling/`). Every group-level result here is associational: a
self-reported AI-use category is not verified authorship provenance, and a body difference is not
evidence that AI assistance caused it.
