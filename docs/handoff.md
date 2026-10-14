# Handoff / status

_Last updated 2026-10-14._

- **Blocked:** huggingface.co is denied by the build environment's network policy,
  so the corpus has not been read. Nothing in `results/` is derived from data yet.
- Done: tokenizer, n-gram accumulator with explicit denominators, content filter,
  14 synthetic tests (`python3 -m pytest`).
- Next once access exists: pin revision, run `scripts/recon.py`, confirm
  `COLUMN_MAP`, write `docs/corpus.md`, inspect sample texts for header/equation
  artifacts, then the Gate 1 pilot (ICLR 2018, 2020, 2024, 2026).
