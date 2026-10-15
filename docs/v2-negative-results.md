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
