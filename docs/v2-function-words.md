# V2 function words: does the mystery persist, and is it ICLR-only? (Lane C)

_2026-10-15, Agent C (thread "Lane C"). Corpus: `woog/open-text-detector-papers` at
`2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27` (V2 pin), `clean` config, every record. Tables and figures are
in `results/v2/function_words/`; scripts are `scripts/v2/lane_c_*.py` (commands at the end). No paper
text is stored in the repository. Facts, interpretation and hypotheses are labelled as such._

## Answer

1. **The shift persists on V2, at full size, on a full census.** With a new counter, ICLR submissions'
   main-body running prose has 28,114 "of" per million letter tokens in 2023, 21,431 in 2026 and 14,511
   in 2027 (−48% from 2023; V1 −48% from 2024). "in" −42%, "we" −45%, "and" +39%. Abstracts and the
   first 600 introduction tokens move the same way (abstract "of" −52% from 2024 to 2027).
2. **The V2 additions change nothing.** The 52k added ICLR 2024–2026 papers have the same rates as the
   V1 records of the same year, to within 1–2% (2026 prose "of": V1 records 21,385, added 21,399). V1's
   partial samples were representative for these words. Because no V1 record changed (Gate 0), there
   is no re-extraction term to separate.
3. **It is not ICLR-only. Every venue shows the 2024–2026 decline, timed by when papers were written.**
   Prose "of", change since 2023: ICML camera-ready 2026 −32%, TMLR published 2026 −28%, COLM 2026 −36%
   (since 2024), NeurIPS 2025 −18%, CoRL 2025 −18%, ICLR 2026 submissions −24%. Placed at each cohort's
   approximate submission deadline, the venues fall on top of each other (figure 3b). Every venue's
   per-paper distribution shifts as a whole: 46% of ICML 2026 papers and 80% of ICLR 2027 papers fall
   below the 5th percentile of ICLR 2023.
4. **The ICLR 2027 step cannot yet be tested outside ICLR.** No other cohort in the dataset was drafted
   in mid-2026 (COLM 2026, drafted around March 2026, is the latest). ICLR 2027 also differs in kind
   from the earlier decline: "the", "to", "and" and the em dash change direction or jump (below).
5. **Within the same paper, the rates are set when the paper is drafted, not when it is polished.**
   868 papers appear as an ICLR 2026 submission (drafted by September 2025) and an ICML 2026 camera-ready
   (finalised mid-2026). Their main-body prose keeps its "of" rate: −0.8% [−1.7, +0.1] (ICML cohort vs
   ICLR 2026 cohort: −7%). Resubmissions to ICLR 2027 move −12% [−14, −10], and the movement is
   concentrated in papers whose abstracts were rewritten (−22%) rather than lightly edited (−5%).
6. **Extraction check outside the PDF pipeline:** see "arXiv abstracts" below.

Nothing here identifies a cause. In particular these are linguistic correlations; they say nothing
about who or what wrote the text.

## 1. Method (independent of the shared pipeline)

- **Counter** (`scripts/v2/lane_c_count.py`). Does not import `mlngrams`. Tokens are maximal runs of
  ASCII letters, lowercased (`[A-Za-z]+`), so digits, review line numbers, table values and maths symbols
  never enter the denominator. Rates are pooled occurrences per million letter tokens. The V1 headline
  used the `omissions` main body and a different tokenizer, so levels differ; relative changes compare.
- **Regions** (line-anchored headings in the clean text; a region that is not found is missing):
  `abstract` (between an Abstract heading and the introduction heading, 300–6,000 characters),
  `intro600` (the first 600 tokens after the introduction heading, so no section-2 boundary is needed),
  `body` (introduction to references), `prose` (body lines with ≥ 12 tokens and ≥ 85% letters: drops
  tables, equations and headings) and `all`. Body and intro600 were found for ≥ 98.6% of papers in
  every venue-year from 2017 on; abstracts for ≥ 95% except ICML (82–90%, two-column title blocks)
  and EMNLP (94%) (`region_coverage.csv`).
- **Downloader** (`scripts/v2/lane_c_fetch.py`). huggingface_hub's blob cache at the pinned sha, each
  file then checked against the LFS SHA-256 recorded by Gate 0 (`results/v2/inventory/files.csv`).
- **Exclusions** (V1 rules): texts under 2,000 characters, exact duplicate text hashes (first id
  kept), the ICLR 2025 title-slug stratum. **Version** labels are Gate 0's first-page header rule
  (`scripts/v2/version_mix.py`); I re-ran it and reproduced `version_mix.csv` byte for byte.
- **Uncertainty**: 95% percentile intervals from 400 Poisson-weighted paper bootstraps (pairs: 1,000
  multinomial pair bootstraps). They cover sampling of papers only, not extraction or coverage.
- **Statements in the body.** ICLR 2027 papers carry ethics, reproducibility and AI-use statements
  before the references, and my body region keeps them. Cutting the body at the first statement
  heading moves 2027 prose "of" by −1.4% and "and" by −4% (`statement_sensitivity.csv`, a seeded sample
  of 6k papers per year). The abstract and intro600 regions contain no statements and show the full
  shift.

## 2. ICLR recount and the V1/V2 decomposition

`results/v2/function_words/rates_by_cohort.csv` (every venue × year × version × region),
`iclr_v1_vs_added.csv`.

| ICLR submissions, change 2024 → 2027 | of | in | we | and |
|---|---:|---:|---:|---:|
| abstract | −52% | −48% | −32% | +22% |
| intro600 | −52% | −47% | −18% | +24% |
| main-body prose | −48% | −43% | −42% | +39% |
| whole text | −43% | −39% | −54% | +21% |
| _V1 published (omissions main body, own tokenizer)_ | _−48%_ | _−44%_ | _−44%_ | _+36%_ |

| ICLR prose "of" per million | V1 records | added in V2 | all |
|---|---:|---:|---:|
| 2024 | 27,815 (n 6,076) | 27,789 (n 1,146) | 27,811 |
| 2025 | 26,401 (n 5,962) | 26,485 (n 5,399) | 26,441 |
| 2026 | 21,385 (n 5,123) | 21,399 (n 14,426) | 21,395 |
| 2027 | 14,512 (all records are V1) | – | 14,512 |

The camera-ready (published) stratum of ICLR moves with the submissions: prose "of" 26,793 (2023) →
21,309 (2026). The decline is not a version mix.

## 3. Outside ICLR

![Function-word trajectories by venue and version](../results/v2/function_words/fig3_trajectories.png)

_Figure 3 (visualization 3). Pooled rates per thousand letter tokens; bands are 95% paper bootstraps;
cohorts with ≥ 100 papers. Data: `fig3_trajectories.csv`._

- **Within-venue trajectories agree in direction and timing.** Levels differ by venue (CoRL is lower in
  "of"; ICML abstracts have far fewer "we", in every year and in the same papers, which is a venue or
  layout effect), so only trajectories are compared, as Gate 0 advised.
- **ICML is the main independent venue.** ICML camera-ready prose "of": 29,413 (2023), 29,069 (2024),
  26,508 (2025), 19,860 (2026). Removing the 833 papers whose title also appears at ICLR changes 2026 to
  19,659 (`nonclr_overlap_sensitivity.csv`). The ICLR-overlap papers themselves sit higher (21,139),
  as expected if they were drafted earlier, for the ICLR deadline.
- **TMLR** moves in both strata: published prose "of" 29,568 (2023) → 21,229 (2026), submissions
  30,388 → 19,108. TMLR's year field is still unresolved (Gate 0 item 7), so its timing is provisional.
- **COLM** (camera-ready, drafted around March 2026) falls furthest among non-ICLR cohorts: 26,654 (2024)
  → 17,098 (2026).
- **NeurIPS 2025 and CoRL 2025** (drafted spring 2025) already show −18%.
- **EMNLP 2023** is one year (prose "of" 27,924) and places a level only.

![Change since 2023 by venue](../results/v2/function_words/fig4_heatmap.png)

_Figure 4 (visualization 4). Percent change in main-body running prose relative to each cohort's 2023
rate (COLM: 2024). Data: `fig4_heatmap.csv`._

**By drafting date.** Figure 3b places each cohort at its venue's approximate submission deadline
(ICLR Y: late September Y−1; ICML Y: late January; COLM: late March; CoRL and NeurIPS: spring). These
dates come from the usual calendars and are not checked per paper. On this axis the venues trace one
decline that starts in 2024 and steepens through 2025–2026, and ICLR 2027 continues it.

![By drafting date](../results/v2/function_words/fig3b_by_drafting_date.png)

**Interpretation (tentative).** A cause specific to ICLR (reviewing guidance, its submission system,
its population) cannot produce the 2024–2026 decline, because accepted-paper populations at five other
venues show it at the same time. A cause tied to writing date fits the timing across venues. The
same extraction pipeline produced every venue's text, so cross-venue agreement alone does not rule out
an extraction effect that depends on how recent PDFs are built; the arXiv check addresses that.

## 4. Per-paper distributions

`per_paper_quantiles.csv` (5th–95th percentiles per venue-year-version-region and word).

ICLR submissions, prose "of" per million: median 27,706 (2023), 20,818 (2026), 13,105 (2027); 5th
percentile 18,528 → 11,799 → 6,318; 95th 39,848 → 32,184 → 25,221. The histograms stay unimodal in
every venue and year: the whole distribution moves, with no sign of a separate subpopulation of
extreme papers. Share of papers below ICLR 2023's 5th percentile: ICLR 2026 35%, ICML 2026 46%,
TMLR 2026 published 34%, COLM 2026 67%, ICLR 2027 80%. Papers with no "of" at all in their main body
are still essentially absent (0.05% in 2027).

## 5. Constructions

Main-body running prose, per million letter tokens (from `rates_by_cohort.csv`):

| ICLR submissions | 2019 | 2023 | 2025 | 2026 | 2027 |
|---|---:|---:|---:|---:|---:|
| "the X of" (e.g. *the performance of*) | 9,808 | 9,441 | 9,368 | 6,648 | 3,551 |
| "of the" | 8,295 | 7,039 | 6,092 | 4,369 | 3,381 |
| hyphenated compounds (*target-domain*) | 15,960 | 20,324 | 21,672 | 26,715 | 31,683 |
| possessive 's | 1,014 | 1,050 | 1,819 | 1,912 | 2,179 |
| ", and" | 3,981 | 4,133 | 4,403 | 5,410 | 8,938 |
| "to" | 24,742 | 23,408 | 23,625 | 21,361 | 14,475 |
| "the" | 70,439 | 68,538 | 64,320 | 52,715 | 55,206 |
| em dash | 170 | 141 | 276 | 745 | 361 |
| passive *be + -ed* | 10,641 | 9,607 | 8,735 | 8,224 | 7,616 |
| tokens per sentence | 24.4 | 24.2 | 24.3 | 24.1 | 22.0 |
| mean token length (letters) | 4.97 | 5.02 | 5.20 | 5.39 | 5.39 |

ICML camera-ready moves the same way up to 2026: "the X of" 9,665 → 5,634 (2023 → 2026), hyphenated
compounds 18,833 → 29,699, em dash 246 → 514.

**Facts.** The "of" decline is concentrated in the *the X of Y* construction (−62% since 2023 in ICLR
submissions), while hyphenated compound modifiers rise by about half and possessives double. This is
the pattern of post-modifying *of*-phrases being replaced by pre-modifying compounds (*the performance
of SSL on the target domain* → *target-domain SSL performance*). Read in the text, 2027 low-"of"
abstracts are fluent prose dense with compound modifiers, not garbled or truncated text.

**The 2027 step differs from 2024–2026.** Up to 2026, "the", "to" and "and" change modestly and the em
dash rises in every venue. In ICLR 2027, "to" falls a further 32% in one year, ", and" rises 65%,
sentences shorten by two tokens, "the" rises slightly and the em dash halves. The 2027 cohort is not
simply further along the 2024–2026 trajectory.

## 6. Same-paper pairs

`pairs_summary.csv`, `pairs_by_similarity.csv`, `pairs.csv.gz` (ids, versions and abstract similarity
only). Pairs are exact normalized-title matches (≥ 25 characters, titles unique in both cohorts).
"Similarity" is the difflib ratio between the two abstracts' word sequences. It is a rough revision
measure; ICML's two-column layout sometimes interleaves introduction text into the abstract region,
which lowers it.

| design | pairs (prose) | "of" in A | "of" in B | pair change | cohort change |
|---|---:|---:|---:|---:|---:|
| ICLR 2026 → ICML 2026 | 851 | 21,287 | 21,121 | −0.8% [−1.7, +0.1] | −7.1% |
| ICLR 2025 → ICML 2025 | 415 | 27,231 | 26,979 | −0.9% [−1.8, −0.1] | +0.3% |
| ICLR 2024 → ICML 2024 | 253 | 27,798 | 28,268 | +1.7% [+0.6, +2.8] | +4.5% |
| ICLR 2026 → ICLR 2027 | 233 | 23,293 | 20,502 | −12.0% [−14.3, −9.6] | −32.2% |
| ICLR 2025 → ICLR 2026 | 150 | 27,047 | 24,347 | −10.0% [−12.5, −7.7] | −19.1% |
| ICLR 2024 → ICLR 2025 | 72 | 27,263 | 26,557 | −2.6% [−5.2, +0.2] | −4.9% |
| ICLR 2026 → TMLR 2026 | 315 | 22,729 | 21,306 | −6.3% [−7.5, −4.9] | −5.8% |
| ICLR 2026 → COLM 2026 | 81 | 20,932 | 19,060 | −8.9% [−11.5, −6.4] | −20.1% |

- **ICLR → ICML: revision for a 2026 camera-ready leaves the prose rates where they were.** The same
  holds for "in", "we" and "and" (all within ±2%), and in the two earlier years. The abstracts are
  heavily edited (median similarity 0.47) and their "of" falls about 8% in every year, 2024 included,
  so that abstract change belongs to the ICLR→ICML revision cycle, not to 2026.
- **Resubmissions move in proportion to how much they were rewritten.** ICLR 2026 → 2027 prose "of":
  −22% for pairs with abstract similarity below 0.5, −8% for 0.5–0.95, −5% at ≥ 0.95. The 2025 → 2026
  control pairs show the same gradient (−19%, −11%/−6%, −3%). Rewritten papers take on the newer
  cohort's rates; lightly edited papers keep their old ones.
- **Interpretation (tentative).** The function-word profile behaves like a property of the drafting
  of a text: it changes when text is (re)drafted, not when a finished paper is revised, re-typeset or
  moved to another venue's template. Re-typesetting from ICLR's one-column to ICML's two-column format
  changes the extraction (Gate 0 item 9) but not these rates, which also argues against a
  layout-dependent extraction artifact.

## 7. arXiv abstracts (extraction-independent check)

_Pending: written when `scripts/v2/lane_c_arxiv.py` finishes._

## 8. Hypotheses after V2

| Hypothesis | V2 evidence | Status |
|---|---|---|
| Counting or preprocessing error in the shared pipeline | New counter, full census, letters-only denominator: same size of shift | Rejected as the explanation |
| Composition: V1's partial ICLR 2024–2026 samples | Added papers have the V1 records' rates | Rejected for V1→V2; nothing changes |
| Something specific to ICLR (guidance, OpenReview, population) | ICML, TMLR, COLM, NeurIPS, CoRL show the 2024–2026 decline in step | Rejected for 2024–2026; untestable for the 2027 step |
| Version mix (submission vs camera-ready) | Both ICLR strata and both TMLR strata decline; camera-ready revision leaves paired prose unchanged | Rejected |
| Statements and boilerplate | Abstracts and intro600 show the full shift; cutting statements moves 2027 prose by 1% | Rejected |
| Extraction artifact tied to recent PDFs | Same rates after re-typesetting into ICML format; see §7 | See §7 |
| A change in how text is drafted, from 2024 on, across ML venues | Timing by drafting date across venues; the *the X of* → compound shift; rates change only when text is rewritten | Consistent with everything here; cause not identified |

What would separate the remaining explanations: (a) hash-matched source PDFs or LaTeX sources for a
seeded sample (arXiv e-prints are reachable from this environment; OpenReview is not); (b) a
non-ICLR cohort drafted in mid-2026 (NeurIPS 2026 when released) for the 2027 step; (c) a corpus
outside ML, or outside this dataset, to see whether the change is field-specific.

## Reproduce

```bash
python3 -m pip install -r requirements.txt
python3 scripts/v2/version_mix.py --revision 2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27   # Gate 0 labels, ~15 min
python3 scripts/v2/lane_c_fetch.py --config clean      # 4.4 GB, hash-checked
python3 scripts/v2/lane_c_count.py                     # per-paper counts -> data/v2/lane_c/counts (~40 min, 4 cores)
python3 scripts/v2/lane_c_analyze.py                   # cohort tables
python3 scripts/v2/lane_c_pairs.py                     # same-paper pairs
python3 scripts/v2/lane_c_figures.py                   # figures 3, 3b, 4
python3 scripts/v2/lane_c_statement_check.py           # statement sensitivity
python3 scripts/v2/lane_c_arxiv.py --n 120             # arXiv abstracts (~1 h; arXiv rate-limits)
```
