# Corpus

_Reconnaissance of 2026-10-14. Numbers from `scripts/recon.py`; tables in `results/coverage_*.csv`
and `results/duplicates_*.csv`. No paper text is stored in this repo._

## Source

- Dataset: [`woog/open-text-detector-papers`](https://huggingface.co/datasets/woog/open-text-detector-papers)
- Pinned revision: `cb5553e0c192c31c562a2822668c7f4ebbb9437a` (`mlngrams.load.REVISION`). The dataset is
  growing; change the pin only together with this file.
- One parquet per `<config>/<venue>-<year>.parquet`; one row per PDF, keyed by `pdf_sha256`; rows join across
  configs on `pdf_sha256`. Licence: per paper (each author's OpenReview licence).

## Configs

| Config | Content | Use here |
|---|---|---|
| `omissions` | `clean` text with non-prose replaced by markers: `⟦equation omitted⟧` (display math), `⟦math⟧` (garbled inline math), `⟦figure omitted⟧`, `⟦table omitted⟧`, `⟦numbers omitted⟧`, `⟦references omitted⟧` (one marker per reference-list page). Duplicate and hidden text is dropped without a marker. | **Primary** for lexical analysis: removes most non-prose that would otherwise produce spurious n-grams. |
| `clean` | Text layer after `positioned-clean-v2` (dehyphenation, running headers/footers, page numbers, small-caps joins, anonymous-author placeholders removed). | Sensitivity check. |
| `direct` | Raw poppler text layer (`pdftotext -bbox-layout`), tesseract OCR for pages without a text layer (`method`), `pages`. | Not used for counting; used here only for the header (version) check, because running headers are removed from `clean`/`omissions`. |

Pages are separated by `\f` in all configs (page count = `text.count("\f") + 1` matches `direct.pages`).

## Schema

`omissions`: `paper_id` (OpenReview forum id; equals `openreview_id` in every ICLR row), `openreview_id`,
`title` (**always null**), `conference` (lowercase), `year` (int), `pdf_sha256`, `text`, `text_sha256`,
`source_clean_text_sha256`, `omission_counts_json` (counts by type: `math_display`, `math_inline`, `figure`,
`table`, `numeric`, `references`, `duplicate`, `hidden`), `omissions_json` (each omission with type, page,
source offsets and the removed text), `chars_clean`, `chars_after`.
`clean` adds `source_text_sha256`, `cleanup_version`, `flag_count`, `stats_json` (rule counts) instead of the
omission columns. `direct` has `method`, `pages`.

## ICLR coverage (omissions config)

Extracted / total submissions per the dataset card: 2013 94%, 2014 100%, 2017–2023 97–99%, 2024 83.1%,
**2025 52.8%, 2026 26.1%**, 2027 99.8%. ICLR 2015/2016 are absent.

`chars_*`: characters of omissions text. `ratio`: median `chars_after/chars_clean`. `refs%`: share with a
`⟦references omitted⟧` marker. `appx`: median share of text after the first references marker (appendix).
`pub%` / `rev%`: share whose `direct` text contains "published as a conference paper" / "under review as a
conference paper" (case-insensitive). `tmpl`: unmodified ICLR LaTeX template submitted as the paper.

| year | rows | unique text | <2000 chars | tmpl | chars median | p5 | p95 | ratio | refs% | appx | pages | pub% | rev% |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2013 | 63 | 63 | 0 | 0 | 25295 | 7362 | 64424 | 0.864 | 96.8 | 0.003 | 9 | 0 | 0 |
| 2014 | 69 | 69 | 0 | 0 | 29433 | 15705 | 49008 | 0.853 | 100 | 0.002 | 10 | 0 | 0 |
| 2017 | 486 | 486 | 0 | 0 | 34011 | 21986 | 53778 | 0.83 | 100 | 0.074 | 13 | 39.9 | 58.8 |
| 2018 | 987 | 987 | 3 | 1 | 35712 | 21770 | 60032 | 0.827 | 99.4 | 0.109 | 14 | 32.7 | 62.6 |
| 2019 | 1553 | 1553 | 3 | 1 | 37490 | 23994 | 63213 | 0.814 | 99.8 | 0.172 | 15 | 31.2 | 67.9 |
| 2020 | 2559 | 2557 | 10 | 4 | 38507 | 24652 | 67405 | 0.797 | 99.5 | 0.192 | 16 | 26.1 | 72.4 |
| 2021 | 2973 | 2973 | 8 | 0 | 41242 | 25609 | 75340 | 0.787 | 99.6 | 0.242 | 17 | 28.4 | 70.5 |
| 2022 | 3363 | 3363 | 0 | 1 | 45620 | 27928 | 81776 | 0.78 | 99.9 | 0.267 | 18 | 31.1 | 67.4 |
| 2023 | 4824 | 4824 | 3 | 1 | 45218 | 28952 | 83325 | 0.765 | 99.8 | 0.27 | 19 | 30.6 | 65.8 |
| 2024 | 6150 | 6150 | 4 | 1 | 46390 | 29030 | 88994 | 0.76 | 99.8 | 0.295 | 20 | 30.5 | 66.2 |
| 2025 | 6160 | 6159 | 6 | 2 | 52700 | 31434 | 99194 | 0.759 | 99.8 | 0.323 | 22 | 34.5 | 62.6 |
| 2026 | 5167 | 5167 | 1 | 6 | 54409 | 30693 | 105832 | 0.762 | 100 | 0.382 | 23 | 27.4 | 69.0 |
| 2027 | 42344 | 42342 | 10 | 11 | 60570 | 32175 | 132275 | 0.78 | 99.9 | 0.472 | 24 | 0.05 | 94.2 |

In every year rows = unique `paper_id` = unique `pdf_sha256`; no empty texts. Mean omissions per paper
(display math / inline math / figures / tables) rise from about 20/11/11/7 (2017) to 48/26/14/22 (2027); full
per-type means are in `coverage_iclr.csv`. Papers get longer every year (median 34k chars in 2017, 61k in
2027), almost entirely through appendices: the median appendix share goes from 7% to 47%. **Use
`main_body()` (text before the first references marker) for the headline analysis**, or year-to-year change
will largely reflect appendix growth.

## Other venues (omissions config)

| venue | year | rows | <2000 | chars median | p5 | p95 | ratio | refs% | appx | pages |
|---|---|---|---|---|---|---|---|---|---|---|
| colm | 2024 | 299 | 0 | 50064 | 31824 | 94638 | 0.749 | 99.7 | 0.327 | 22 |
| colm | 2025 | 418 | 0 | 54506 | 34477 | 108847 | 0.762 | 100 | 0.371 | 24 |
| corl | 2021 | 153 | 0 | 31528 | 27041 | 37985 | 0.769 | 100 | 0.002 | 11 |
| corl | 2022 | 197 | 0 | 30842 | 26275 | 38521 | 0.752 | 100 | 0.002 | 11 |
| corl | 2023 | 198 | 0 | 44752 | 29079 | 74330 | 0.772 | 100 | 0.32 | 19 |
| corl | 2024 | 264 | 0 | 44770 | 29305 | 74931 | 0.758 | 100 | 0.362 | 19 |
| emnlp | 2023 | 1218 | 0 | 42028 | 23188 | 71590 | 0.754 | 99.9 | 0.213 | 15 |
| icml | 2025 | 1169 | 0 | 61762 | 40443 | 113891 | 0.772 | 100 | 0.369 | 22 |
| neurips | 2021 | 2689 | 0 | 37068 | 30243 | 46751 | 0.773 | 99.4 | 0.003 | 13 |
| neurips | 2022 | 2958 | 0 | 37928 | 31126 | 46615 | 0.763 | 99.6 | 0.067 | 14 |
| neurips | 2023 | 1217 | 0 | 49920 | 31537 | 95040 | 0.761 | 99.9 | 0.288 | 20 |
| neurips | 2024 | 1219 | 0 | 57037 | 36583 | 106407 | 0.757 | 99.9 | 0.379 | 29 |
| neurips | 2025 | 1169 | 0 | 58679 | 36090 | 102342 | 0.756 | 100 | 0.409 | 31 |
| tmlr | 2022 | 222 | 0 | 60286 | 36923 | 106568 | 0.782 | 100 | 0.22 | 26 |
| tmlr | 2023 | 592 | 0 | 61578 | 38263 | 109977 | 0.781 | 99.7 | 0.249 | 25 |
| tmlr | 2024 | 923 | 0 | 60999 | 37164 | 122772 | 0.78 | 100 | 0.246 | 26 |
| tmlr | 2025 | 1169 | 0 | 62085 | 38357 | 117637 | 0.769 | 100 | 0.265 | 27 |
| tmlr | 2026 | 477 | 0 | 65707 | 41894 | 133488 | 0.765 | 100 | 0.298 | 29 |

No duplicate texts within any venue file. Card coverage is partial for EMNLP 2023 (60%), ICML 2025 (34%),
NeurIPS 2023–2025 (19–33%) and all TMLR years (18–59%); ICML 2023/2024/2026, COLM 2026, CoRL 2025 have no
files. Several partial files have near-identical sizes (1169 rows for ICML 2025, NeurIPS 2025, TMLR 2025;
1217–1219 for NeurIPS 2023/2024, EMNLP 2023), which suggests a capped sample; how it was drawn is not documented.
NeurIPS 2021/2022 and CoRL 2021/2022 have almost no appendix text (supplementary material was a separate file).
Version mix (camera-ready vs submission) was not checked for these venues.

## Duplicates (ICLR)

Nothing was removed; `results/duplicates_iclr.csv` lists every pair (ids only).

- **Same `paper_id` across years:** none. Same `paper_id` within a year: none.
- **Exact `text_sha256` duplicates:** 4 groups. One 2019 and two 2025 papers whose whole text is `1`;
  three 2020 forums and two 2027 forums with the identical unmodified ICLR template; and one 2027 paper
  submitted twice under two forum ids (the only real duplicate). Whitespace/case-normalized hashing finds the
  same groups.
- **Placeholder template submissions** ("Formatting instructions for ICLR ...", 28 in all, 11 of them in 2027)
  and texts under 2000 characters (48 in all) should be excluded from counting.
- **Near duplicates** (same first 300 normalized chars after "Abstract", or 8-word-shingle Jaccard >= 0.5 on
  the first 2000 normalized chars after "Abstract"; templates and short texts excluded): 179 cross-year pairs
  and 11 within-year pairs (9 in 2027). Cross-year pairs are resubmissions of rejected papers, 168 of them
  to the next year. The later-year papers involved: 2020: 6, 2021: 7, 2022: 22, 2023: 22, 2024: 34, 2025: 28,
  2026: 15, 2027: 43, i.e. 0.1–0.7% of each year. These counts are lower bounds: rewritten abstracts are not
  caught, and partial 2025/2026 coverage hides most resubmission pairs that involve those years.

## Version mix: camera-ready vs submission

The dataset holds the PDF that OpenReview currently serves: the camera-ready version for accepted papers, the
submission version for rejected and withdrawn ones. Running headers reveal which ("Published as a conference
paper at ICLR" vs "Under review as a conference paper at ICLR"). They are removed by the clean cleanup, so they
survive in `omissions` only in 3–27 papers per year (in-text mentions); the shares above come from `direct`.

- 2017–2026: 26–40% published, 59–72% under review, 1–5% neither. The published share tracks the ICLR
  acceptance rate (about 30%; 2024: 30.5%), so in those years accepted papers are present as camera-ready
  versions (deanonymized: author names, affiliations, emails, acknowledgements) and the rest as anonymous
  submissions (`share_anonymous_block` 65–72% in `direct` for 2018–2026; 2017 was not double-blind, so 0%).
- **2027: 0.05% published, 94% under review, 99.7% anonymous.** All 2027 papers are submissions under review.
  The last year differs from all earlier years in version (no camera-ready revisions, no acknowledgements,
  no author blocks, no reviewer-requested additions). Any 2026→2027 change in n-grams tied to versions
  (acknowledgements, "camera-ready" additions, author/affiliation tokens) is confounded. Mitigations:
  compare under-review-only subsets across years (the header flag per paper is reproducible from
  `direct`), or report 2027 separately.
- 2013/2014 have no ICLR style header (pre-template years).

## Coverage bias in ICLR 2025 and 2026

OpenReview forum ids are random strings, so coverage that follows id order is random with respect to content.
`results/coverage_bias_iclr.csv` (first-character distribution) and `results/coverage_strata_iclr.csv`
(by id stratum) show:

- **2026 (26.1%)**: every extracted id starts with `0–9` or `A–F` (plus 91 ids starting with `G`); no
  ids from `H` onward. This is a prefix-truncated crawl in ASCII order: 16 of 62 first characters ≈ 26%,
  matching the card. Published share 27.4%, lengths in line with the trend. **Plausibly random**; the
  `G` stratum is partial but also id-ordered.
- **2025 (52.8%)**: three strata with different composition.
  - ids starting `0–P` (4,789 papers; ~190 per first character, about the full count expected from
    11,672 submissions): published 30.2%, mean 23.6 pages. Looks complete and unbiased.
  - ids starting `Q–z` (1,231 papers; ~30 per first character, i.e. roughly 15% of that range):
    published 43.7%, mean 25.8 pages. **Over-represents accepted (camera-ready) papers.**
  - 140 rows whose `paper_id` is a title slug (e.g. `A_General_Framework_for_Producing`), not an OpenReview
    forum id: **100% published**, mean 29.5 pages; evidently added from accepted-paper listings.
  - Overall 2025 published share 34.5% vs about 31–32% expected.
  Recommendation: use only the `0–P` stratum for 2025 (or reweight), and report the full-file result as a
  sensitivity check.
- 2024 (83.1%) has an uneven first-character distribution (chi-square 670 on 61 df) but the `0–P` and
  `Q–z` strata have the same published share (30.2% vs 30.8%) and length, so no evidence of bias.
- Withdrawn and desk-rejected papers cannot be told apart from rejected ones in the text.

## Text quality (sample of 5 papers each from 2017, 2020, 2024, 2027)

Main-body prose is generally clean and reads in order. Recurring artifacts:

- **Title and heading layout**: titles are uppercase and sometimes line-scrambled or split at small-caps
  hyphens ("…RECURRENT NET - / WORKS", "LAN - / GUAGE"). Section headings are uppercase lines (median
  7–8% of lines are all caps), occasionally emitted after the paragraph they head (2027 sample). Affects few
  tokens.
- **Inline math leaking as words**: residues not caught by `⟦math⟧`, e.g. "` 2 -normed", "k · k ∞",
  "f W i ,b i (x)", "p g and p d", subscript lines "(t)". These produce single-letter tokens and spurious
  n-grams like "p g". Lines of at most 2 characters are 7–11% of non-empty lines (falling over time).
- **Table cells leaking** from untruled tables: column headers one per line ("Method / PCC / SCC /
  PSNR / SSIM"), model names; the card lists this as a known issue.
- **Figure text leaking**: occasionally whole text samples inside figures (a 2017 paper has generated
  Wikipedia-style text in a figure).
- **Author blocks** (names, affiliations, emails) present in camera-ready versions only; footnote markers
  run into sentences ("for the first time. 5 A simple ...").
- **Running headers, page numbers, line numbers**: running headers are removed (they survive only in
  `direct`); no review-template line-number columns seen in ICLR. Bare-number lines are about 2–4% of lines
  (equation numbers, table cells), >10% of lines in only 0.6–2% of papers. NeurIPS camera-ready footers
  ("37th Conference on Neural Information Processing Systems") survive in omissions.
- **Citation style**: many 2024–2027 papers use bare author-year citations ("Wu et al. (2024)"); the
  tokenizer removes "(2024)" but leaves "Wu et al.", so name and "et al" tokens remain.
- **OCR**: 0–2% of papers have OCR'd pages (`direct.method`), about 2% in 2024–2026, 0.3% in 2027.

## Caveats

- ICLR 2027 papers are submissions under review, extracted in Sep/Oct 2026; "2027" is a submission cohort
  written mostly in 2026, and is all anonymous submissions (see version mix).
- ICLR 2025 (52.8%) and 2026 (26.1%) are partial; 2026 looks random (id-prefix truncation), 2025 is
  enriched with accepted papers outside the `0–P` id range.
- Papers are not verified to be human-written; this corpus says nothing about authorship.
- `title` is null in every config; the title is the first line(s) of `text`.
- Extraction quality varies; small-caps headings, pseudocode omitted as math and untruled tables leaking
  cells are known issues (dataset card).
