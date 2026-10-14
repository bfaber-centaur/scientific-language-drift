# QA and adversarial review (Agent D), 2026-10-14

Scope: pilot run `~/work/pilot` (ICLR 2018/2020/2024/2026, omissions config, tokenizer v1.2,
filter v1.1, min_df 3, 14,861 docs, 2 exact duplicates skipped). I also ran a body-only
sensitivity run for 2018 and 2026 in a scratch directory. All figures here are aggregates.

Artifacts: `tests/test_qa.py` (hand-derived synthetic counts, an end-to-end run of
`scripts/count_ngrams.py` on a fake `iclr-9999` cache, and strict-xfail tests that pin known
defects), and `scripts/qa_audit.py` (recompute, contamination, denominators, risers with
document bootstrap). Test suite: 25 passed, 6 xfailed.

## 1. Correctness: what passed
- Hand-computed unigram, bigram and trigram counts, per-doc positions, df, prevalence and
  per_million match exactly, both through `GroupAccumulator` and through the script end to end.
  Duplicate (`same_as`) and empty-text skipping work. `--min-df` prunes only the n-gram tables;
  the denominators in `totals.csv` and in the tables' `positions` column are unpruned.
- Pilot: 240 sampled docs (60 per year) re-tokenized. Tokens, positions_1/2/3 and chars match
  `docs.parquet` 100%. `totals.csv` equals the sums over `docs.parquet`. Per-doc recounts of
  80 candidate bigrams equal the table counts.
- Four real papers (2 from 2018, 2 from 2026): hand-checked introduction passages. Citations
  in "(A et al., 2024b;a)" form are stripped, hyphen repair is correct ("down-\nstream"), and
  bigram counts such as "large language" ×2 and "language models" ×2 match.
- Every file's `year` label matches its filename for 2013–2027, so the script's join on the
  loop year is safe.

## 2. Defects (proposed fixes; src/ not edited)
| # | Where | Example | Effect |
|---|---|---|---|
| D1 | tokenize.py:40 (`.` in `_SEGMENT_BREAK`) makes the decimal branch of :45 dead | `0.5` -> `<num>` / `<num>` (two segments); `qwen2.5-7b` -> `qwen <num>` / `<num> b` | One extra `<num>` and one extra boundary per decimal. That is about 27 per 2018 paper and 73 per 2026 paper, so the effect grows over time. Fix: protect `\d\.\d` before the segment break. |
| D2 | tokenize.py:40 | `e.g.` -> `['e'],['g']`; `Fig. 2` -> `fig` / `<num>`; `vs.` ends a segment | Creates false sentence boundaries and single-letter tokens (7–11 e.g./i.e. per paper). Fix: replace a whitelist (e.g., i.e., et al., Fig., Eq., Sec., vs., cf., resp.) before splitting. |
| D3 | tokenize.py:45 (`[a-z]` only) | `naïve` -> `na`,`ve`; `café` -> `caf` | Spurious tokens. Fix: strip combining marks after NFKD, or use `[^\W\d_]`. |
| D4 | README "parentheses do not break" | `large language models (LLMs) can` -> bigram `models llms` | `models llms` is in 53% of 2026 papers, also `learning rl` and `super-resolution sr networks`. Fix: make a parenthetical acronym `\(\s*[A-Z][A-Za-z0-9-]{1,10}\s*\)` a boundary. |
| D5 | single newline is not a boundary | `INTRODUCTION\nDeep learning` -> `introduction deep` | All-caps heading lines rose from 22 to 39 per paper (2018 to 2026). Also fuses appendix letters after a page break. Fix: treat a line matching `^\s*([A-Z]\.?|\d+(\.\d+)*)?\s*[A-Z][A-Z0-9 &:,-]{2,80}$` as a boundary. |
| D6 | tokenize.py:33 | `state-of-the-\nart` -> `state-of-theart` | Minor. Keep the hyphen when the left part already contains a hyphen. |
| D7 | count_ngrams.py:98 / :184 | A stale `run.json` stays during a rerun into the same `--out` (seen in this pilot: v1.1 run.json while the v1.2 run was writing) | Readers poll `run.json` and can audit stale tables. Fix: delete run.json at start, or write to `out.tmp` and rename. |
| D8 | count_ngrams.py:124 | `ex.map` consumes the whole generator up front | Every text in a year is held in memory. 2027 has 42,344 docs. Fix: bounded submit window. |
| D9 | count_ngrams.py:175 | per-year `df >= min_df` pruning | In a year-vs-year join, an absent n-gram is treated as count 0, although it really means df ≤ 2 with unknown count. All 40 naive top risers were "absent in 2018". Fix: emit unpruned counts for the union of n-grams kept in any year (second pass), or join only on n-grams kept in both years. |
| D10 | filters.py:7 docstring | says "e g"/"i e" bigrams exist; they cannot (D2) | Doc only. "conference paper" is moot: running headers are already removed upstream (0% of sampled papers). |

## 3. Contamination
Classes are rule-based (`qa_audit.classify`). Values are the per-million mass of the class within each year's top-300 bigrams.

| view / class | 2018 | 2020 | 2024 | 2026 |
|---|---|---|---|---|
| raw: number/table (`<num>`) | 36,402 | 44,107 | 42,508 | 41,709 |
| raw: math single letter (`x t`, `x i`, `t t`) | 2,677 | 5,055 | 5,324 | 3,827 |
| raw: citation (`et al`) | 2,487 | 2,427 | 2,425 | 2,028 |
| content: header (`workshop track`, `track iclr`) | 109 | 0 | 0 | 0 |
| content: template statement | 0 | 0 | 0 | 141 |
| content: prompt furniture (`final answer`, `system prompt`, `prompt template`, `output format`, `correct answer`) | 0 | 0 | 0 | 250 |
| content: parenthetical acronym | 0 | 0 | 44 | 152 |
| content: reference residue (`international conference`, `information processing`) | 0 | 0 | 35 | 62 |
| content: cross-ref/section (`main text`, `see appendix`, `implementation details`...) | 757 | 711 | 981 | 1,029 |

Across all bigram positions, number and single-letter residue together account for 12–15% in every year (about 12% of unigram tokens). The share is roughly stable, so denominator contamination moves per-million rates by only about 1–2%.

Template-driven year differences are real and large. Prevalence (share of papers), 2018 to 2026:
- `reproducibility statement` 0 to 0.49
- `ethics statement` 0 to 0.34
- `llm usage` 0 to 0.21
- `code of ethics` 0 to 0.14
- `use of llms` 0 to 0.10

Among the riser lists ranked by prevalence (dfB ≥ 30), 7 of the top 25 are statement or template text: `reproducibility statement`, `ethics statement`, `llm usage`, `iclr code`, `full responsibility`, `personally identifiable`, `ensure reproducibility`. Compute-statement text (`nvidia rtx`) and `adamw optimizer` are probably appendix boilerplate as well.

The top two fallers, `workshop track` and `track iclr`, come from 2% of 2018 files being workshop-track papers. That is a corpus-composition issue to raise with Agent A.

Suggested ARTIFACT_NGRAMS additions:
- `workshop track`, `track iclr`
- `reproducibility statement`, `ethics statement`, `llm usage`, `impact statement`, `broader impact`, `iclr code`
- `international conference`, `information processing`, `neural information`, `processing systems`

Better: detect these statement sections as units and drop them, or report them separately. Put prompt-template text in a separate "appendix furniture" list rather than the main ranking.

## 4. Denominators and length
- Median paper length grew from 5,549 to 7,869 tokens (2018 to 2026). The share of tokens before the first `⟦references omitted⟧` fell from 0.85 to 0.63. Appendices drive the growth.
- Body-only vs full, log2 change 2018 to 2026:
  - `learning rate`: -1.13 full vs -1.58 body
  - `batch size`: -0.32 vs -0.86
  - `related work`: -0.19 vs +0.05 (the sign flips)
  - `see appendix`: +0.30 vs +0.77
  - In the 2026 content top 300, 38 bigrams are not in the body-only top 300.
- Body-only does not remove the statements. They sit before the references, so `reproducibility statement` is higher body-only (103/M) than full (64/M).
- `<num> b` (7B) and `<num> d` (3D) are handled consistently: always `<num>` plus a single-letter token, never content. They still carry real signal in the raw tables (`<num> b`: 1,430/M in 2026). If model size matters, a dedicated `<num>b` token would be needed.

## 5. Ranking recommendations
Rank on `lr = log2(((cB+k)/PB) / ((cA+k)/PA))` with k = 5, using unpruned counts (D9). Require:
- prevalence ≥ 1% in at least one year (df ≥ 10 for the 987-paper 2018 year)
- df ≥ 20 in the higher year
- no single paper contributing more than 20% of the count in the higher year
- a document-bootstrap 95% CI lower bound above 1 bit

Report prevalence ratios alongside. Pilot result:
- Risers under these rules are robust, with 0 of 40 fragile. Examples: `large language`, `diffusion models`, `foundation models`, `flow matching`, `kv cache`, `mathematical reasoning`, and stylistic `across diverse`, `consistently achieves`, `results highlight`, `thereby enhancing`, `relying solely`.
- Fallers are fragile. In the smoothed faller top 40, 22 have dfA < 20 and 18 have one 2018 paper contributing more than 20% of the count (`ensemble adversarial`, `omniglot dataset`, `rnn cell`). The robust fallers are `word embeddings`, `penn treebank`, `lstm model`, `inference network` and `word vectors`.
- The naive per-million ratio with an epsilon gives ±15–18 bits for every "absent" n-gram and should not be used.

## 6. Threats to findings
1. Template sections that ICLR introduced or encouraged after 2023 (reproducibility, ethics and LLM-usage statements) contaminate the 2024–2026 risers. They must be removed or reported separately before stylistic claims are made.
2. Appendix growth changes per-million rates for moderate-frequency n-grams by up to about 0.5 bit and can flip signs. Report a body-only sensitivity check, and paper-level prevalence, next to every claim.
3. Pruned tables (D9) make "new in year X" undefined.
4. Population: 2027 appears to be roughly 42k submissions rather than accepted papers, and 2018 includes workshop-track papers. Do not compare these with the accepted-paper years without stratifying.
