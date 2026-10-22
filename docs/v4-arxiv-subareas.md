# V4: is the drift ML-only? arXiv abstracts 2018–2026, and ML sub-areas

_2026-10-22, thread "arXiv drift and ML sub-areas". Two questions from Bobby: (1) does the function-word
decline and the ICLR 2027 hype/self-mention reversal appear outside ML; (2) which ML sub-areas are growing
or shrinking, and which are moving towards solo or group papers. Every number cites a table in
`results/v4/`. **Fact**, **interpretation** and **hypothesis** are labelled where it matters. Nothing here
is evidence about who or what wrote any text._

## Data

- **arXiv:** every paper whose v1 was posted 2018-01 to 2026-09, from the arXiv metadata snapshot mirrored
  on Hugging Face (`librarian-bots/arxiv-metadata-snapshot` @ `d83cc98f`, synced 2026-10-19; shard hashes in
  `results/v4/arxiv/source.csv`). That's 1,850,450 papers. The abstract is the metadata abstract that the
  submitter typed in, not text extracted from a PDF. It is the latest version's abstract, and the
  single-version-only rerun gives the same results (`period_index.csv`, `sample = v1_only`).
- **Fields** are set by the primary (first-listed) category. ML = cs.LG, cs.CL, cs.CV, cs.AI, stat.ML.
  Non-ML groups (CS other, eess, stat other, math, physics, q-bio, econ/q-fin) **drop every paper
  cross-listed to an ML category**. Abstracts under 50 tokens are dropped. Rates are pooled: total
  count ÷ total tokens, per 1,000 tokens, using the V1 tokenizer (v1.3) with `$…$` math removed.
- **Lexicons** are the V3 lists, imported unchanged from `scripts/v3/style_features.py`: hype (Millar-style),
  LLM-excess words (Kobak-style), Hyland's self-mention, hedges and boosters, plus "the X of" and single
  function words.
- **ICLR 2017–2026:** title, keywords, abstract and primary area from Paper Copilot's paperlists (the V3
  source, same commit `9fcfd12`, file hashes verified), joined to the V3 author counts and decisions.
- **Sub-areas** are 27 fixed keyword tags (`scripts/v4/topics.py`). The same tags are used on arXiv and
  ICLR. A tag on title + abstract means "mentions X", which is broad. A tag on the title alone means
  "is about X", which is narrow. Both versions are written out (`*_title.csv`), and they agree on every
  direction reported below. `results/v4/iclr/topic_audit.txt` lists random matches for each tag. ICLR's
  own primary areas are used for 2025–26 only, because ICLR changed the area list after 2024.

## Summary

1. **The drift is not ML-specific (fact).** The fall in "of", the collapse of "the X of", the fall in
   self-mention, and the rise and then fall of hype and LLM-excess words all appear in every arXiv field,
   including math and physics papers with no ML cross-listing. ML has the largest changes, but it is not
   much earlier than the other fields.

   "of" per 1,000 abstract tokens (`period_rates.csv`):

   | field | 2018 | 2022 | 2024 | 2025 | 2026 H1 | 2026 Q3 | 2022 → 2026 Q3 |
   |---|---:|---:|---:|---:|---:|---:|---:|
   | ML | 32.8 | 29.7 | 27.6 | 21.7 | 16.5 | **15.3** | **−49%** |
   | CS other | 38.6 | 35.1 | 32.4 | 26.9 | 21.9 | 20.2 | −43% |
   | eess | 38.2 | 34.2 | 31.7 | 26.7 | 22.3 | 20.2 | −41% |
   | econ/q-fin | 42.7 | 39.9 | 35.7 | 30.9 | 25.5 | 23.8 | −40% |
   | q-bio | 46.1 | 43.1 | 40.2 | 33.3 | 29.2 | 26.5 | −38% |
   | stat other | 39.9 | 37.4 | 35.4 | 30.6 | 26.7 | 23.8 | −36% |
   | physics | 45.3 | 43.7 | 41.8 | 37.9 | 34.1 | **31.9** | **−27%** |
   | math | 53.5 | 52.1 | 50.7 | 47.8 | 43.3 | **39.6** | **−24%** |

   - "The X of" falls by 66% in ML, 41% in physics and 36% in math over 2022 → 2026 Q3.
   - "In" and "the" fall too, in every field.
   - An independent check with a plain regex over the raw abstracts reproduces the result: math "of"
     50.6 → 38.1, physics 42.3 → 30.7, ML 30.1 → 15.3 per 1,000 words, comparing 2022 with July–September
     2026.
   - The whole distribution moves, not a tail. The median ML abstract went from 28.2 to 13.2 "of" per
     1,000 tokens. ML abstracts with no "of" at all went from 1.9% to 11.5%. In math that share went from
     1.1% to 2.3%.
2. **The ICLR 2027 reversal is a 2026 arXiv-wide event (fact).** Hype adjectives and LLM-excess words
   peak at about the same time in every field, then fall back to near or below 2018 levels by September 2026.
   Self-mention falls in every field over the same months (`timing.csv`, `fig_monthly.png`).

   | field | hype 2018 | hype peak (month) | hype 2026 Q3 | LLM-excess 2022 → peak → 2026 Q3 | self-mention 2022 → 2026 Q3 |
   |---|---:|---|---:|---|---|
   | ML | 8.3 | 13.8 (2025-04) | **5.9** | 1.50 → 3.89 → **0.96** | 22.6 → 14.3 (−37%) |
   | CS other | 4.9 | 9.3 (2025-04) | 4.5 | 1.05 → 2.87 → 0.82 | 19.6 → 15.0 (−23%) |
   | physics | 4.3 | 6.3 (2025-05) | 4.7 | 0.53 → 1.45 → 0.60 | 19.0 → 16.3 (−14%) |
   | math | 2.4 | 3.6 (2025-04) | 2.6 | 0.34 → 0.79 → 0.29 | 25.8 → 22.9 (−11%) |
   | econ/q-fin | 3.6 | 6.5 (2024-12) | 3.0 | 0.82 → 2.20 → 0.59 | 21.4 → 15.0 (−30%) |

   - LLM-excess words peak between 2024-12 and 2025-02 in six of the eight fields; eess and q-bio, two of
     the noisiest series, peak in 2024-05. Hype peaks between 2024-12 and 2025-06 in every
     field. The fall starts in late 2025 and steepens from April 2026.
   - "Novel" in ML abstracts: 1.72 per 1,000 tokens (2022), 2.06 (2024), 0.46 (2026 Q3).
   - Not everything reverses. "Across" keeps rising: ×5.5 in ML since 2022, ×3.8 in physics, ×3.7 in math.
     Mean word length and nominalisations stay near their highs. As in ICLR 2027, the new register is
     impersonal and compressed, not plainer.
   - This matches ICLR. ICLR 2026 abstracts, submitted in September 2025, have "of" 19.1 and hype 13.7;
     arXiv ML in September 2025 has 20.4 and 13.0 (`results/v4/iclr/topic_style_year.csv`). ICLR 2027
     bodies (V3) have hype back at 2017 levels, and so do arXiv ML abstracts from mid-2026.
3. **Interpretation.** The timing is synchronised across unrelated fields: LLM-excess words peak in
   early 2025 and hype in spring 2025, both fall in 2026, and "of" erodes steadily from late 2024. Math
   and physics have no shared reviewing culture or venue guidance with ML, so a cause specific to ML
   culture or ICLR is now unlikely. That answers open item (c) of V2 Lane C (`docs/v2-function-words.md`
   §8). A writing-tool change is the leading candidate and is a **hypothesis**: something in the widely
   used drafting and polishing tools whose default style moved away from promotional vocabulary (2025–26)
   and towards denser, function-word-light prose. Field differences in size would then reflect how much
   text passes through those tools (ML most, math least). Nothing here identifies the tool or measures
   its use.
   - Topic mix is not the cause. Holding ML's 2022 mix of primary category × LLM-topic fixed moves 2026
     Q3 "of" only from 15.3 to 15.9 (`ml_standardised.csv`).
   - Every ML sub-area shows the shift: "of" falls 40–58% in every topic from 2022 to 2026 Q3, and hype
     falls 18–44% below its 2022 level (`topic_style_year.csv`).
   - Single-author papers moved furthest. In ML, solo abstracts went from "of" 35.5 (2022) to 17.4, and
     from LLM-excess 2.93 (2024) to 0.28 (`team_style.csv`).
4. **ML sub-areas: growing and shrinking (fact).** At ICLR, comparing shares of submissions in
   2017–19 with 2025–26 (`results/v4/iclr/topic_change.csv`; the title-only version is in
   `topic_change_title.csv`):
   - **Growing:** LLMs (2.2% → 45% mention them, 0.7% → 21% are about them); agents (0.2% → 4.8%);
     alignment and safety (2.2% → 17%); reasoning (2.5% → 17%); multimodal and vision-language
     (2.5% → 17%); benchmarks and datasets (10% → 34%); federated learning and privacy, AI-for-science,
     fairness and causality (each about ×3 to ×5, from small bases).
   - **Shrinking as a share:** classic NLP tasks (7.8% → 3.6%); theory and optimization (14% → 11%);
     GAN/VAE/diffusion generative modelling (14% → 11%); RL (16% → 14%); speech; continual, meta and
     few-shot learning. By title, robustness halves (4.8% → 2.5%) and generative modelling falls
     6.4% → 3.6%. These counts still grow, because ICLR submissions per year grew about fifteenfold. Only their
     share falls.
   - ICLR's own primary areas, 2025 → 2026 (same list): growth in robotics (2.1% → 3.0%), datasets and
     benchmarks (6.5% → 8.0%), foundation models (11.1% → 13.4%) and applications (11.8% → 13.7%);
     shrinkage in graphs (3.7% → 2.7%), representation learning (7.4% → 5.9%), optimization
     (4.5% → 3.7%) and learning theory (3.1% → 2.6%) (`area_change.csv`).
   - **arXiv categories,** 2022 → 2025 (`results/v4/arxiv/cat_year.csv`): cs.AI ×4.0 (2,097 → 8,445
     primary), cs.GR ×3.3, cs.HC ×2.9, cs.CY ×2.7, cs.SE ×2.6, cs.CL ×2.4. cs.LG and cs.CV grew ×1.9.
     stat.ML grew ×1.4 and is barely above its 2018 level. cs.IT (×0.87) and eess.IV (×0.98) shrank.
5. **Solo against group papers (fact).** Two things are happening at once.
   - **Teams keep growing, unevenly.** Large-team areas are getting relatively larger:
     - Agents: ICLR 2025–26 papers have +0.39 log2 more authors than the average paper, and 29% have
       9+ authors.
     - Video, multimodal, reasoning, robotics, and datasets and benchmarks. In the 2026 ICLR datasets and
       benchmarks area, 36% of papers have 9+ authors.
     - Smaller-team areas are getting relatively smaller: theory and optimization (−0.33; 3.7% solo, 4.6%
       9+), graphs, federated learning, causality, self-supervised learning, interpretability and
       time series.
     - On arXiv, the share of ML papers with 10+ authors rose from 1.9% (2019) to 8.3% (2026). It is
       14–17% for agents, video, multimodal and robotics.
   - **Solo papers surged on arXiv from late 2025.** After falling for years (5.3% in 2019, 4.1% in
     2024), the single-author share of ML papers went to 9.0% in 2026 (`topic_year.csv`). In ML-primary
     papers: 3.3–4.8% per quarter from 2023 to 2025 Q3, 6.0% in 2025 Q4, then 7.2%, 8.5% and 9.4% in the three
     quarters of 2026. That is 2,593 solo ML papers in 2026 Q3, against 490–760 per quarter in 2024
     (`solo_quarterly.csv`).

     Every ML topic rose. Theory and optimization rose most, from 4.7% (2024) to 16.5% (2026). Causal
     rose 4.3% → 14.5%, efficiency 2.7% → 8.7%, LLMs 3.2% → 8.3%, interpretability 4.1% → 8.6%. The
     lowest are video (2.8%), multimodal (3.0%), robotics (3.3%) and vision (3.4%).

     It is not only ML. From 2024 to 2026 Q3, solo shares rose in math (28.5% → 37.1%), stat other
     (9.9% → 19.3%), CS other (7.7% → 11.9%) and physics (11.0% → 14.7%). Solo math papers doubled
     from 3,447 in 2026 Q1 to 7,117 in 2026 Q3.
   - **At ICLR the solo share is low and flat:** 4.2% in 2017–19, 2.1% in 2025–26, highest in
     optimization (5.7%) and learning theory (5.2%). The latest ICLR author lists are from 2026,
     submitted in September 2025, before the arXiv surge.
   - **Interpretation and hypothesis.** The field is splitting into large-team empirical areas
     (agents, multimodal, video, robotics, benchmarks) and a fast-growing tail of single-author arXiv
     papers, concentrated in theory. That tail appeared in the same months as the 2026 style shift, so
     cheaper solo writing with LLM assistance is a natural hypothesis. It is untested, and the quality
     of these papers is unmeasured. Whether they reach review is a question for ICLR 2027 author lists
     and decisions.

## Negative results and caveats

- **ML is not clearly earlier.** "Of" first sits 10% below its 2022 level in 2024-05 to 2024-11 for ML, CS
  other, eess, q-bio and econ; in 2025-01 for stat other; in 2025-03 for physics; and in 2025-12 for math.
  ML leads in size, not by a year in timing.
- **Composition does not explain it.** The topic-mix standardisation, the single-version sample and the
  per-topic tables all show the same change.
- **These are abstracts, not body text.** The ICLR body-text findings (V1–V3) are matched in direction and
  timing by abstracts here, but no arXiv body text was read.
- **The abstract is the latest version.** A revised abstract would carry newer style back into older
  months, which weakens trends rather than creating them. The v1-only sample gives the same direction and
  similar size for every field and feature (ML indices within 0.08; the largest gap is stat other hype in
  2025, 1.34 against 1.49).
- **Math abstracts include LaTeX outside `$…$`** (`\(…\)`, bare commands), which inflates token counts.
  That lowers math's rates, but nothing suggests the inflation changed over time, and the regex check
  agrees.
- **The lexicons count words, not senses** ("critical point", "robust statistics"). Topic tags are coarse.
  Mention-tags (title + abstract) are broad: "benchmark" alone tags a third of ICLR 2026 papers. Title
  tags miss papers. Directions agree between the two, but the levels do not.
- **2026 is January–September.** Seasonal effects are small for these features: the monthly series has no
  visible annual cycle before 2024.
- **Author counts come from arXiv's parsed author lists.** Solo papers were spot-checked (2026-08 cs.LG):
  they are real single-name author fields.

## Next steps worth doing

- **ICLR 2027 author lists** (when released): do the arXiv solo papers reach ICLR, and in which areas?
- **Same author, before and after.** Track authors who posted to arXiv in both 2024 and 2026 and test
  whether one author's abstracts change, which would separate a population change from a change in how
  people write.
- **Outside arXiv:** PubMed abstracts by month (Kobak et al.'s corpus) would test biomedicine, a field far
  from both ML and math.
- **arXiv LaTeX sources** for 2024–26 body text, to test whether the abstract findings hold in full text
  outside ML.

## Reproduce

    # arXiv snapshot: 11 parquet shards of librarian-bots/arxiv-metadata-snapshot @ d83cc98f into ~/.cache/arxiv
    python3 scripts/v4/arxiv_features.py --src ~/.cache/arxiv --jobs 4   # ~35 min on 4 cores, ~1 GB per worker
    python3 scripts/v4/arxiv_analyze.py
    python3 scripts/v3/review_meta.py --src ~/ext/paperlists             # V3 author counts (data/v3)
    python3 scripts/v4/iclr_subareas.py --src ~/ext/paperlists
    python3 scripts/v4/topic_audit.py --src ~/ext/paperlists

Figures: `results/v4/arxiv/fig_monthly.png` (six series by field and month) and
`results/v4/arxiv/fig_subareas.png` (topic growth against change in relative team size; solo share by
topic).
