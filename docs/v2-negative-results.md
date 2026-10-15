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
  year. It belongs to the ICLR→ICML revision cycle and ICML's layout, not to 2026 writing. Main-body
  prose of the same pairs does not move. `docs/v2-function-words.md` §6.
- **C-N2. ICML abstracts are partly contaminated by column interleaving.** In ICML's two-column
  layout the extracted abstract region sometimes carries introduction text, and abstracts are found
  for only 82–90% of ICML papers (`region_coverage.csv`). Do not compare ICML abstract levels with
  other venues; use main-body prose.
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
