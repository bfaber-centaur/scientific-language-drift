# Note for woog: here are your bigrams. Also, look at this.

_From the n-gram study of `woog/open-text-detector-papers` at revision `cb5553e` (2026-10-14).
ICLR 2017–2027, 75,118 papers, main-body text (before the reference list, with ethics, reproducibility
and AI-use statements removed). Details and caveats are in `docs/findings.md`; reproduction steps are in
`README.md`._

## Your bigrams

**Top content bigrams, year-balanced** (each year weighted equally; occurrences per million bigram
positions): neural networks 528, neural network 464, training data 288, learning rate 277,
reinforcement learning 243, loss function 218, deep learning 200, training set 189, related work 183,
gradient descent 175, machine learning 174, test set 162, ground truth 159, language models 153,
see appendix 152.

**Raw bigrams** are mostly function words and numbers: of the 6,634, in the 4,099, `<num> <num>` 3,502,
to the 2,997, et al 2,637.

**By year** (top 5 content bigrams):

| 2017 | 2020 | 2023 | 2025 | 2027 |
|---|---|---|---|---|
| neural networks | neural networks | neural networks | language models | related work |
| neural network | neural network | neural network | training data | language models |
| learning rate | learning rate | training data | diffusion models | percentage points |
| deep learning | training data | loss function | neural networks | reinforcement learning |
| training data | reinforcement learning | learning rate | large language | training data |

**Tables:** `results/full/body/top100_n{1,2,3}_{raw,content}_{by_year,pooled_yb,pooled_cw}.csv` hold
counts, per-million rates and the share of papers per n-gram. Annual series are in
`results/full/longitudinal/timeseries_*.csv`.

## Also, look at this

1. **A 2024 vocabulary burst.** "delve" goes from 1.0% of ICLR papers in 2023 to 10.7% in 2024, then
   6.1%, 1.2% and 0.1%. "underscores", "intricate", "pivotal", "showcasing" and "realm" follow the same
   pattern. Non-LLM papers show it too, and so do NeurIPS, TMLR and COLM.
   (`results/full/longitudinal/figures/fig2_watchlist_stylistic.png`)
2. **ICLR 2027 reads differently.** The papers come from the 2026 submission round.
   - "a novel" falls from 54% of papers to 9%, and "we propose" from 80% to 51%.
   - "test whether" rises from 5% to 23%, "held fixed" from 1% to 13%, and "percentage points" from
     4% to 25%.
   - It holds within submission versions only, in the raw PDF text, and in LLM and non-LLM papers alike.
   - We don't know why. A new population of submitters, ICLR 2027 guidance and writing tools are all
     open explanations.
3. **Function words are thinning.** "of the" falls from 8,784 to 3,338 per million (2017 to 2027), and
   the stopword share from 40% to 32%. The decline is gradual before 2023, faster after, and also seen
   in NeurIPS, TMLR and COLM.
4. **A warning for the dataset.** ICLR 2027 papers carry a required "AI use statement". If it isn't
   removed, it dominates every "what's new in 2027" list: 43 of the top 100 risers in our first run came
   from it (`docs/negative-results.md` N1). The `omissions` config doesn't mark it.

## Dataset observations you may want to know about

- **ICLR 2025:** the extracted subset beyond ids 0–P is partial and skews toward camera-ready (accepted)
  PDFs, at 44% vs 30%. 140 rows use title slugs rather than OpenReview ids.
- **ICLR 2026:** coverage stops at ids starting with "G" (26% of submissions).
- **Placeholders and duplicates:** 28 unmodified ICLR template placeholders and 48 texts under 2,000
  characters, plus one 2027 paper submitted twice under two forum ids.
- **Capped samples:** several partial venue files have near-identical row counts (1,169 for ICML 2025,
  NeurIPS 2025 and TMLR 2025), which suggests a capped sample.
- **Leftover headers:** running headers survive in `omissions` for NeurIPS camera-ready footers.

(`docs/corpus.md`)
