# V2 negative results, false leads and methodological corrections

_Shared by the V2 lanes. Each lane edits only its own labeled section._

## Lane E (adversarial review)

- **E-N1. Silent download corruption.** 10 of about 157 whole-file Hub downloads in this environment
  returned bytes that did not match the listed LFS SHA-256, with no HTTP error. Only hash-verified
  downloads (`mlngrams.load.fetch`, `scripts/v2/review/fetch_hash.py`) are safe to cache.
  `docs/v2-adversarial-review.md` D1.
- **E-N2. "Of"-deletion test was a false alarm.** Bare "one the" and "most the" rise 4–8× in ICLR 2027,
  which looked like extraction dropping "of". Reading the matches shows grammatical uses ("at most the
  bound", "the one the gate detected"). No evidence of deletion; not a decisive test either. E7.
- **E-N3. Our header parser, not Gate 0, was wrong on 145 NeurIPS records** ("Submitted to the 38th…").
  Gate 0's version labels stand. E3.
- **E-N4. Exact-title overlap is a lower bound by about a fifth**: text matching adds 199 ICML 2026 papers
  with an ICLR 2026 counterpart under another title. D3.

## Lane C (function words)

- **C-N1. The ICLR → ICML abstract drop is not a 2026 signal.** Same-paper ICML abstracts have about 8%
  fewer "of" than the ICLR versions in 2024, 2025 and 2026 alike, and about 40% fewer "we" in every
  year (the "we" gap is mostly the region artifact in C-N2). It belongs to the ICLR→ICML revision cycle and ICML's layout, not to 2026 writing. Main-body
  prose of the same pairs does not move. `docs/v2-function-words.md` §6.
- **C-N2. ICML abstracts are partly contaminated by column interleaving.** In ICML's two-column
  layout the extracted abstract region sometimes carries introduction text, and abstracts are found
  for only 82–90% of ICML papers (`region_coverage.csv`). Do not compare ICML abstract levels with
  other venues; use main-body prose. arXiv abstracts of the same ICML papers have about 60% more "we"
  than the extracted region (18.9k vs 11.7k per million, ICML 2023), so the low ICML abstract "we" is
  this artifact, and C-N1's "we" figure for ICML abstracts should not be read as venue style.
- **C-N3. The resubmission design cannot isolate the 2027 step.** ICLR 2026 → 2027 pairs move −10% in
  prose "of", the same as the 2025 → 2026 control pairs (−10%), although the cohort step is larger
  (−32% vs −19%). Pairs move in proportion to how much their abstracts were rewritten in both years.
- **C-N4. Title-only pairing undercounted pairs** (Lane E D3). Adding Lane E's text matches grew
  ICLR 2026 → ICML 2026 from 851 to 1,047 prose pairs and moved every estimate by ≤ 2 points; tables
  now use the union.
- **C-N5. Operational: two background runs died silently.** The arXiv lookup was OOM-killed when it
  loaded the ICLR 2027 text whole (1.5 GB compressed), and a second copy died with its launching
  shell. The log simply stopped. It now streams record batches, and every run ends with an explicit
  exit line. The first counter run was also stopped and restarted from scratch to add construction
  measures; nothing from the partial run was used.
- **C-N6. Overclaim corrected: "the venues fall on top of each other."** The first figure 3b plotted
  levels across venues at their drafting dates, which §3 itself says not to compare (format differences,
  Gate 0 item 9). Lane E review C1. Figure 3b now indexes each venue to its own 2024 rate, and the claim
  reads "parallel declines". The TMLR year was also still called unresolved after Lane E's header audit
  had settled it for published papers (C2); corrected.

## Lane B (replication)

- **B-N1. V1's corpus-weighted 2017–21 → 2025–27 contrasts are not stable under complete data.**
  They weight years by paper count, so V1's recent cohort was 81% ICLR 2027. Phrases whose 2027 value
  differs from 2025–26 (*a novel*, *we propose*, *leverage*, *delve into*, *crucial role*) change
  verdict when 2025–26 become complete. Quote year-balanced contrasts or per-year values; V1's
  corpus-weighted watchlist verdicts (17/36 held) are superseded by V2's (24/36), with no change in any
  year's data. `docs/v2-replication.md`, figure 2b.
- **B-N2. The V2 trigram merge failed twice for lack of disk** (DuckDB spill > 20 GB with composite
  strata). Fixed with `count_ngrams.py --merge-by-year`, value-identical on a test venue.
- **B-N3. One V1 2027 record is an exact duplicate of a record added to 2026**, so "V1 reproduces
  exactly" holds for 2017–2026 and to within one paper for 2027.

## Lane D (appendices and disclosures)

- **D-N1. V1.5's clean-statement tier does not transfer to ICLR 2026**: 87% of 2026 statements are the
  last section of the paper, and V1.5 treated end-of-text statements as suspect. A V2 tier (sensitivity
  definition) keeps 10,069 instead of 6,607.
- **D-N2. The section-heading extractor misses statements** under headings without a use word ("WRITING
  DETAILS", "LLM DISCLAIMER") and in-text sentences: about 9% of ICLR 2026 papers without a section.
  Prevalence figures are lower bounds.
- **D-N3. The ICLR 2027 appendix jump is not a resubmission effect**: within-paper gain +913 (2027)
  vs +1,120 (2026).
- **D-N4. Pre-2026 "statements" (0.06–0.8% of papers) are mostly extractor false positives.**
- **D-N5. ICML statement extraction overruns into math more often**; the ICML keyness list is not
  interpreted.
- **D-N6. The V1.5 review file `docs/v1.5-review.md` and `results/review/blind_labels_*` are cited but
  absent from the repository.** Part A of the V2 labelling sample replaces that check.
- **D-N7. The sentence-stance rules miss denials.** On the 45-item check (2026-10-21), the rules called 8 of
  the 21 statements that the blind Opus coders read as "use + denial" plain "use", mostly in ICLR 2026
  (stance agreement 7/15 there). Denial shares are lower bounds. `docs/v2-appendices-disclosures.md`,
  "Validation".
- **D-N8. Two blind Claude Opus coders agreed on all 45 items.** That is not two independent readers;
  it is the V1.5 caveat (two runs of one model) at full strength, and the check counts them as one.
- **D-N9. The single human labelling is noisy in known directions.** Bobby never chose "use + denial"
  and ticked drafting for 19 of 40 statements against the Opus coders' 8, mostly editing statements.
  His labels are reported, not treated as ground truth (he rates himself an inexperienced annotator).
- **D-N10. Classifier v2 over-assigns "other use" on random statements.** Against the majority of
  blind Opus, Sonnet and Haiku readers on 300 random 2026–27 statements it agrees on 75% of groups
  (85% on the stratified 45): 26 of 103 polish-only and 18 of 56 drafting statements become "other
  use". ICML 2026's polish-only share is 15% by classifier and 45% by the models.
  `results/v2/disclosures/judges/`.
