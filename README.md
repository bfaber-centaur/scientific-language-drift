# A Decade of Language in ML Papers: n-gram baseline

Exploratory corpus analysis of word n-grams in ML papers from
[`woog/open-text-detector-papers`](https://huggingface.co/datasets/woog/open-text-detector-papers),
with ICLR 2017–2027 as the primary longitudinal corpus.
Question: what are the most common n-grams, and how have their frequencies changed over time?
This is not an AI-text detector and makes no authorship claims.

**Status:** pipeline code and synthetic tests are in place. No corpus results yet:
the build environment could not reach huggingface.co (network policy), so the
dataset revision is not pinned and the source column names in `src/mlngrams/load.py`
are unconfirmed. See `docs/handoff.md`.

## Setup

```bash
python3 -m pip install pyarrow pandas matplotlib huggingface_hub pytest
python3 -m pytest          # synthetic counting / normalization checks
```

## Data contract

`mlngrams.load.iter_docs()` yields `{doc_id, venue, year, text}` and is the only
way analysis code touches the corpus. Files are read from a pinned dataset
revision (`MLNGRAMS_REVISION`) into a local cache outside this repo.
No paper text is committed here; only code and aggregate tables.

## Tokenization (`src/mlngrams/tokenize.py`, v1)

1. Unicode NFKC, lowercase; repair line-break hyphenation (`represen-\ntation`).
2. Strip author-year parenthetical citations and numeric `[3, 12]` citations (configurable).
3. Segment boundaries: `. ! ? ; :`, blank lines, and math-like characters
   `= + \ { } ^ _ $ | < > ~ * / #`. **N-grams never cross a boundary.**
   Commas, quotes and parentheses are dropped but do not break n-grams.
4. Tokens: alphabetic words with optional internal hyphens/apostrophes; digit runs → `<num>`.

## Normalization (`src/mlngrams/count.py`)

- `per_million = 1e6 × count / positions_n`, where `positions_n` is the number of
  n-gram slots (Σ max(0, len(segment) − n + 1)), not the token count.
- `prevalence = df / docs`: share of (deduplicated) papers containing the n-gram.
- Tables may be pruned by minimum document frequency; group totals never are.

## Filtering rule (`src/mlngrams/filters.py`, v1)

Raw tables are always kept. The *content-bearing* view keeps an n-gram only if
every token is not an NLTK English stopword, not `<num>`, and at least 2 characters,
and the n-gram is not on a short, listed boilerplate list (`et al`, `arxiv preprint`, ...).
