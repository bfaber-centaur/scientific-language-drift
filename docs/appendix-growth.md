# Appendix growth: what actually grew (Lane A)

_Lane A of the appendices / disclosures follow-up, 2026-10-15. Corpus: `woog/open-text-detector-papers`
at revision `cb5553e0c192c31c562a2822668c7f4ebbb9437a`, `omissions` config. Scripts:
`scripts/appendix_scan.py` (scan v1) → `scripts/appendix_analyze.py`; spot checks in
`scripts/appendix_checks.py`. Tables and figures: `results/appendix/`. Seed 20261015. Everything here
is descriptive: it says what is in the PDFs, not why authors put it there._

## Gate 1 answer

The "appendix explosion" is real appendix material, and it is essentially all of the growth. Between
ICLR 2017 and ICLR 2027 the median PDF grew from 13 to 24 pages. The main body stayed at 8.5–10 pages
and ~4,300–5,100 prose tokens, tracking the page limit; the reference list grew by about half a page;
the appendix grew from 1.5 to 12 pages (median 372 → 4,151 tokens). Of the growth in mean prose per
paper (5,535 → 9,812 tokens), the appendix accounts for more than all of it, because main-body prose
fell slightly (−424 tokens). The same holds within submission versions only, within resubmitted papers,
and in NeurIPS, TMLR, COLM and CoRL wherever the appendix is inside the PDF.

| Question (directive) | Answer | Evidence |
|---|---|---|
| Has the main body stayed roughly constant? | **Yes in pages, nearly in tokens.** Median 8.5–9 pages (2017–2024), 10 in 2025 (10-page limit), 9.5 in 2026–27; tokens 4,612 (2017) → 4,967 (2022) → 5,090 (2025) → 4,289 (2027). | `length_quantiles_iclr.csv`, fig 1 |
| Few enormous papers, or everyone? | **Everyone.** P25 of appendix tokens went 0 → 2,195, P10 0 → 931. The top decile's share of all appendix tokens fell from 41% to 32% and the Gini coefficient from 0.65 to 0.45: growth became *less* concentrated. | `prevalence_iclr.csv`, fig 2, fig 3 |
| Is post-reference text really appendix? | **Yes, ≥ 97% of it in ICLR.** 63 hand-checked papers; bibliography residue 0.3–1.5% of post-reference characters, statements 0–1.2%, checklists ≈ 0. NeurIPS is the exception: its checklist is 50–75% of post-reference text in 2021–22. | `post_region_audit.csv`, `prevalence_iclr.csv`, `diagnostics_venues.csv` |
| What grew inside appendices? | **Everything, roughly in proportion.** Implementation/experimental details (19% of 2017→2027 growth), additional results (17%), proofs/theory (10%), data/benchmark descriptions (8%), examples/prompts (6%), ablations (3%); related work, limitations and notation went from ~0 to 1–2% each. | `composition_iclr.csv`, fig 4 |
| Did page limits or supplementary rules change? | ICLR always allowed an unlimited appendix in the same PDF; its main-text cap moved (8 suggested → 10 max → 8 → 9 → 10 → 9). NeurIPS moved the appendix *into* the PDF (separate file 2019–21, optional 2022, expected 2024+). | "Page limits" below |
| Continuous or change points? | **Steady compounding growth with a fast start and a 2027 jump.** Log median appendix tokens: ~+50%/year 2017–19, ~+18%/year 2019–26 (best one-hinge model, break 2019), then +40% in 2026→27 (+65% in submissions), the largest year-over-year change. | `changepoints_iclr.csv`, `yoy_median_change_iclr.csv` |

## Definitions

Per paper, from the `omissions` text (pages separated by `\f`; one `⟦references omitted⟧` marker per
reference-list page):

- **body**: text before the first references marker (the study's `main_body()`).
- **main**: body minus statement sections (ethics, reproducibility, AI/LLM use, acknowledgments;
  `sections.py` v2) minus any lettered appendix placed *before* the references.
- **appendix**: text after the last references marker, minus statement sections, NeurIPS-style
  checklists and the leading block of unmasked bibliography entries, plus any pre-reference appendix.
- **Lengths** in characters, tokenizer v1.3 tokens (the n-gram study's tokens; tables, display
  equations, inline math and figure text are omission markers and do not count) and pages at half-page
  resolution (reference pages lose their text to markers, so a page with > 300 prose characters next to a
  marker counts as half a page). Omission markers per region are counted as a measure of non-prose
  content.
- **Population**: ICLR 2017–2027 papers not flagged short/template in `results/paper_flags_iclr.csv`,
  ICLR 2025 restricted to the unbiased 0–P id stratum (75,119 papers). Version strata from the running
  header: `under_review` (submission), `published` (camera-ready). Other venues: all rows ≥ 2,000 chars.

## Is the post-reference text really appendix?

**Hand checks.** 63 papers drawn with fixed seeds (ICLR 2017, 2020, 2023, 2027; NeurIPS 2022, 2024;
TMLR 2024), each inspected at the body end, the reference zone, the start and end of the post-reference
text and the detected headings (`post_region_audit.csv`, ids and verdicts only). In ICLR every non-empty
post-reference region was appendix material. The checks found six scanner defects, all fixed before the
final run (see "Defects found and corrected").

**Measured contamination in ICLR** (`prevalence_iclr.csv`, share of post-reference characters):

| | 2017 | 2020 | 2023 | 2026 | 2027 |
|---|---|---|---|---|---|
| leading bibliography residue | 1.2% | 1.2% | 0.9% | 0.6% | 0.3% |
| statement sections (ethics, reproducibility, LLM use) | 0% | 0% | 0.1% | 1.2% | 0.2% |
| papers with a statement after the references | 0.4% | 0.3% | 1.8% | **46%** | 7.7% |
| checklist | 0 | 0 | 0 | 0 | 0 |
| papers with the appendix before the references | 0.2% | 0.2% | 0% | 0.1% | 0% |

ICLR 2026 allowed the new LLM-usage section to sit in the appendix, and 46% of 2026 papers put a
statement after the references; ICLR 2027 asked for it in the main text and only 7.7% did. Both are
removed from the appendix measure. The earlier study's raw measure (share of characters after the first
marker) and the cleaned appendix ratio agree to within 2.5 points in every year (median 7.2% vs 7.1% in
2017, 46.9% vs 49.3% in 2027; `raw_post_ratio` vs `appx_ratio`). Lane D's independent baseline
(`docs/v1.5-review.md` §0) reached the same conclusion (bibliography residue ~1%,
statements first after the references in 2–3% of 2026–27 papers).

**The other direction, main body contaminated by references.** Bibliography entries that the
omissions config left *before* its first marker are counted as main body. A trailing-block check on 500
papers per year (`body_tail_residue.csv`) puts them at 1.0–1.9% of body characters in 2017–2025 and
0.5% / 0.3% in 2026 / 2027. This slightly inflates main-body length in earlier years and explains at most
~1.5 points of the 2025→2027 drop in main-body tokens.

**Extraction is not manufacturing growth.** Page counts come from the PDFs' page breaks and do not
depend on what the omissions config masks. In pages, main bodies are flat and appendices grow eightfold,
the same picture as in tokens. Omission markers grow inside appendices too (median tables after the
references 0 → 10, display equations 0 → 10), so prose tokens understate, not overstate, appendix growth.

## What grew: lengths by year (ICLR, medians)

| year | papers | pages | main pages | appendix pages | main tokens | appendix tokens | appendix ratio |
|---|---|---|---|---|---|---|---|
| 2017 | 486 | 13 | 8.5 | 1.5 | 4,612 | 372 | 0.07 |
| 2018 | 983 | 14 | 9 | 2.5 | 4,712 | 573 | 0.11 |
| 2019 | 1,549 | 15 | 8.5 | 4 | 4,678 | 943 | 0.17 |
| 2020 | 2,545 | 16 | 8.5 | 4 | 4,647 | 1,122 | 0.19 |
| 2021 | 2,965 | 17 | 8.5 | 5.5 | 4,719 | 1,527 | 0.25 |
| 2022 | 3,362 | 18 | 9 | 6 | 4,967 | 1,820 | 0.27 |
| 2023 | 4,820 | 19 | 9 | 6.5 | 4,932 | 1,846 | 0.27 |
| 2024 | 6,145 | 20 | 9 | 7 | 4,823 | 2,045 | 0.30 |
| 2025 | 4,781 | 22 | 10 | 8 | 5,090 | 2,354 | 0.32 |
| 2026 | 5,160 | 23 | 9.5 | 10 | 4,622 | 2,961 | 0.39 |
| 2027 | 42,323 | 24 | 9.5 | 12 | 4,289 | 4,151 | 0.49 |

P10/P25/P50/P75/P90 and means for every measure (tokens, characters, pages, tables, figures,
equations), for all papers, submissions and camera-ready versions: `length_quantiles_iclr.csv`. The
reference list itself grew from a median of 2 to 3–3.5 pages (2.5 in 2027).

**Prevalence.** Papers with any appendix (≥ 100 tokens): 62% → 95%. With a substantial one
(≥ 1,000 tokens): 30% → 89%. With ≥ 10 appendix pages: 5% → 60%. With an appendix at least as long as
the main body: 1.4% → 48.5%.

**Main body versus appendix per paper** (fig 3). In 2017–19 the main body is a tight band around 4,700
tokens and a third of papers have no appendix; in 2025–27 the main body is the same band, shifted
slightly down, and the appendix cloud has moved up by an order of magnitude, centred on the
"appendix = main body" diagonal. Appendix length is nearly independent of main-body length within a
cohort.

## Comparable populations

**Submissions only.** 2027 is almost entirely submissions, earlier years ~30% camera-ready. Within
`under_review` papers the growth is the same or larger: appendix median 137 → 4,158 tokens (1 → 12
pages), main body 4,448 → 4,287 tokens (8.5 → 9.5 pages). Camera-ready versions carry larger
appendices than submissions of the same year (2024: 3,337 vs 1,514 tokens), consistent with material
added after review, so all-paper medians before 2027 are inflated relative to 2027 and the
submission-only series is the fair comparison for 2026→2027.

**Within the same paper.** 305 cross-year near-duplicate pairs (resubmissions, `duplicates_iclr.csv`;
`resubmission_lengths_iclr.csv`): from one year to the next the main body changed by a median of +24
tokens (ratio 1.007), the appendix by +253 tokens (ratio 1.20 where the earlier version had one); 66% of
appendices grew, 56% of main bodies did. Papers being revised grow their appendices, not their main text.

## Change points

On log yearly medians (11 points, so this is description, not inference; `changepoints_iclr.csv`):

- Appendix tokens: one-hinge model best by BIC in both strata, break at 2019. Slope 0.50 log/year before
  (×1.6 per year) and 0.17 after (×1.18 per year); submissions 0.84 then 0.19. A level-step model fits
  worse.
- 2026 → 2027 is the largest year-over-year change in the series: +1,190 median tokens (95% bootstrap CI
  1,095–1,281) in all papers, **+1,642 (1,536–1,739) in submissions**, against +20–420 in other years
  (`yoy_median_change_iclr.csv`). Extrapolating the 2019–2026 trend predicts ~3,500 tokens for 2027
  (submissions ~3,000); observed 4,151 (4,158).
- 2022 → 2023 and 2023 → 2024 are flat in submissions (+83, +34 tokens, CIs include 0).
- Main-body tokens: flat to 2024, +5% in 2025 (the 10-page limit), then −9% (2026) and −7% (2027) at an
  unchanged 9.5-page median. Fewer prose tokens on the same number of pages: not explained by more
  tables, figures or equations (median counts per main body unchanged); bibliography residue explains
  ~1.5 points. Open.

Caveats: 2025 and 2026 are partial extractions (2025 restricted to its unbiased stratum, 2026 a
prefix-truncated but plausibly random 26%), and the 2027 cohort doubled to 42k submissions, so the
2027 jump may reflect who submitted as much as how papers were written.

## What is in the appendices

**Method.** Top-level appendix sections are lettered (A, B, C, ...); the scanner accepts a heading only
when its letter is the next expected one, skips appendix tables of contents, and records second-level
"A.1" subsections. Headings are mapped to 13 categories by keyword rules (`CATEGORIES` in
`appendix_analyze.py`); generic containers ("APPENDIX") are replaced by their subsections. Headings that
name only the paper's own topic ("ORTHOGONAL BASIS") fall back to marker density: ≥ 3 math markers per
1,000 characters → *other (math)*, ≥ 0.5 tables/figures → *other (tables/figures)*, else *other
(prose)*. Text outside any detected heading is *unsectioned* (16–26% of post-reference characters).

**Validation.** 154 top-level headings (14 per year, seeded) were labelled by hand
(`heading_audit.csv`, `heading_audit_summary.csv`). The rules agree with the hand label on 85% (83% of
headings that name a genre). Precision is ≥ 0.95 for proofs/theory, additional results,
implementation, examples, ablation and containers; recall is lower for additional results (0.79) and
background/notation (1 of 3). Of 35 headings sent to the marker fallback, 20 were genuinely topic-only
and 15 had a genre the keywords missed. Good enough for coarse composition, not for fine shares.

**Result** (mean characters per paper, all ICLR papers; `composition_iclr.csv`, fig 4):

| category | 2017 | 2021 | 2024 | 2027 | share of 2017→27 growth | share 2017 → 2027 |
|---|---|---|---|---|---|---|
| implementation / experimental details | 808 | 2,553 | 2,997 | 7,019 | 19.5% | 17% → 19% |
| additional results | 542 | 2,009 | 3,026 | 5,785 | 16.5% | 11% → 16% |
| unsectioned | 1,220 | 1,776 | 2,015 | 5,802 | 14.4% | 26% → 16% |
| proofs / theory | 387 | 2,285 | 2,349 | 3,404 | 9.5% | 8% → 9% |
| other (prose) | 544 | 1,050 | 1,208 | 3,181 | 8.3% | 11% → 9% |
| data / benchmarks | 210 | 931 | 1,322 | 2,714 | 7.9% | 4% → 7% |
| other (tables/figures) | 307 | 634 | 669 | 2,285 | 6.2% | 6% → 6% |
| examples / prompts | 193 | 463 | 1,344 | 2,119 | 6.1% | 4% → 6% |
| ablation | 57 | 317 | 474 | 1,037 | 3.1% | 1% → 3% |
| related work | 22 | 192 | 529 | 746 | 2.3% | 0.5% → 2% |
| other (math) | 346 | 741 | 784 | 1,049 | 2.2% | 7% → 3% |
| background / notation | 28 | 139 | 265 | 544 | 1.6% | 0.6% → 1.5% |
| limitations / discussion | 16 | 137 | 515 | 467 | 1.4% | 0.3% → 1.3% |
| algorithm | 79 | 260 | 259 | 309 | 0.7% | 2% → 1% |
| statements (removed from the appendix measure) | 1 | 12 | 63 | 92 | 0.3% | 0% → 0.3% |
| **total post-reference characters** | 4,759 | 13,498 | 17,818 | 36,554 | | |

Readings: no single kind of material drove the growth. Experimental material (implementation details,
additional results, data/benchmarks, ablations, examples) is about half of it. Proofs grew fastest to
2022 (papers with a proof section: 10% → 31%), then plateaued in absolute terms. Examples and prompts
doubled in 2024 (1 in 4 papers in 2026), plausibly LLM-era prompt listings. Extended related work and
limitations sections, near absent before 2020, moved into appendices (11–15% of papers by 2024–27).
Shares in submissions only are nearly identical (`composition_iclr.csv`, `stratum = under_review`).

## Page limits and supplementary-material rules

From the venues' own calls for papers and author guides (paths under `https://iclr.cc/Conferences/` and
`https://neurips.cc/Conferences/`). The Wayback Machine was not reachable, so rules for years whose pages
are gone are marked unverified.

| Venue / year | Main-text limit at submission | Appendix in the same PDF? | Separate supplementary file | Statements outside the limit | Source |
|---|---|---|---|---|---|
| ICLR 2017–2018 | 8 pages "strongly recommended", no strict limit | yes, unlimited, single PDF | not mentioned | – | iclr.cc archive `iclr2017:callforpapers`; `2018/CallForPapers` |
| ICLR 2019–2020 | 8 recommended, **strict max 10** | yes, after the bibliography; reviewers need not read it | 2020: code field | – | `2019/CallForPapers`; `2020/CallForPapers`, `2020/AuthorGuide` |
| ICLR 2021 | **strict 8** (+1 for rebuttal/camera-ready) | yes | yes, either allowed | – | `2021/CallForPapers`, `2021/AuthorGuide` |
| ICLR 2022–2024 | strict 9 (camera-ready 9) | yes; single file "encouraged" | yes | optional ethics and reproducibility statements, before the references, ≤ 1 page each | `2022`–`2024/CallForPapers`, `/AuthorGuide` |
| ICLR 2025 | **6–10 pages**, strict | yes; recommended for camera-ready | code | ethics, reproducibility (optional) | `2025/CallForPapers`, `2025/AuthorGuide` |
| ICLR 2026 | strict 9 (+1 for rebuttal/camera-ready) | yes; single file recommended | code | ethics, reproducibility; **new LLM-usage section, may sit in the appendix** | `2026/AuthorGuide`; template `iclr2026_conference.tex` |
| ICLR 2027 | 9, over-length = desk reject (+1 camera-ready) | yes | code | **required AI use statement**; ethics, reproducibility optional | `2027/AuthorGuidelines` |
| NeurIPS 2019–2021 | 8 (2019–20), 9 (2021) | **no**: appendix "must be submitted in a separate file" | yes | 2021: checklist in the PDF after the references | `2019`–`2021/CallForPapers`, `/PaperInformation/NeurIPS-FAQ` |
| NeurIPS 2022 | 9 | allowed (optional) | yes | checklist in the PDF after the references | `2022/CallForPapers`, `2022/PaperInformation/NeurIPS-FAQ` |
| NeurIPS 2023 | 9 | **no at submission**, yes at camera-ready | yes | checklist in OpenReview, not in the PDF | `2023/PaperInformation/NeurIPS-FAQ`, `/StyleFiles` |
| NeurIPS 2024–2025 | 9 | **expected** in the main PDF (2025: optional) | ZIP for code/data | checklist in the PDF (2024 after the appendix; 2025 usually right after the references) | `2024`–`2025/CallForPapers`, `2024/PaperInformation/NeurIPS-FAQ` |
| TMLR | no page limit | yes | up to 100 MB | broader-impact statement if needed | jmlr.org/tmlr/author-guide.html |
| COLM 2024–2025 | strict 9 | yes, unlimited | not mentioned | ethics, reproducibility, acknowledgments optional | colmweb.org/2024/cfp.html, colmweb.org/2025/cfp.html |
| CoRL 2021 | 8 | not stated; supplementary as a separate zip | yes | – | 2021.corl.org/author-information/submission-instructions |
| CoRL 2022–2023 | unverified | unverified | – | 2023: limitations section required | corl2023.org/call-for-papers |
| CoRL 2024 | 8 | either at submission; **at the end of the PDF at camera-ready** | zip | – | 2024.corl.org/contributions/instruction-for-authors |
| ICML 2025 | 8, single file | yes, unlimited | no separate deadline | impact statement | icml.cc/Conferences/2025/CallForPapers |
| EMNLP 2023 | 8 (long papers) | yes, after the bibliography | optional archive | limitations section required | 2023.emnlp.org/calls/main_conference_papers/ |

What this explains and what it does not: ICLR's main body follows its limit (8.5 pages in the 8-page
years, 9 in 2022–24, 10 in 2025, 9.5 in 2026–27), but ICLR never changed where appendices go, so its
appendix growth is not a rule artifact. No ICLR rule change lines up with the 2019 hinge or the 2027
jump (2026 and 2027 have the same limit). The NeurIPS and CoRL step from ~0 to thousands of tokens in
2023 is a rule artifact: their appendices moved from separate files into the PDF.

## Other venues

Medians (`length_quantiles_venues.csv`, `diagnostics_venues.csv`, fig 5). Version mix was not checked
for these venues; NeurIPS 2023 shows in-PDF appendices although submissions could not include them,
so its file is probably camera-ready versions.

| venue | years | main pages | main tokens | appendix pages | appendix tokens | note |
|---|---|---|---|---|---|---|
| NeurIPS | 2021–22 | 9.5–10 | 5,450–5,560 | 0 | 0 | appendix in a separate file; post-reference text is 50–75% checklist |
| NeurIPS | 2023 → 2025 | 10 | 5,454 → 5,023 | 7 → 9 | 2,194 → 3,127 | checklist removed (6.5–7.5 pages per paper in 2024–25) |
| TMLR | 2022 → 2026 | 12.5 | 6,532 → 6,171 | 8 → 10 | 2,118 → 2,736 | no page limit, yet appendices still grow |
| COLM | 2024 → 2025 | 10 | 4,848 → 4,720 | 7.5 → 10 | 2,451 → 3,004 | |
| CoRL | 2021–22 → 2023–24 | 8 | 4,755 → 4,257 | 0 → 6.5–7 | 0 → 2,126–2,438 | appendix moved into the PDF in 2023 |
| ICML | 2025 | 9 | 5,440 | 10.5 | 3,504 | single year |
| EMNLP | 2023 | 8.5 | 4,806 | 3.5 | 1,258 | single year; NLP venue |

Where the appendix is inside the PDF, every venue shows a flat or shrinking main body and a growing
appendix. TMLR, with no page limit, has the longest main bodies (12.5 pages) and still adds about half a
page of appendix per year, so a page cap is not the only pressure. The raw post-reference share
overstates NeurIPS appendices by up to 7 points in 2022 (pure checklist) and is close to the cleaned
ratio elsewhere.

## Defects found and corrected

Found by hand checks before the final run; each is fixed in `appendix_scan.py` v1 and recorded in
`post_region_audit.csv`. None changes the ICLR conclusions; two matter for NeurIPS.

1. **NeurIPS checklists counted as appendix.** The heading is often not extracted (2022: "Checklist";
   2024–25: only "Answer: [Yes] / Justification:" lines survive). Detection now anchors on the first
   checklist question or the first of ≥ 3 answer lines. Before the fix NeurIPS 2022 looked like it had a
   7% appendix share; it is a checklist.
2. **NeurIPS 2025 checklist sits between the references and the appendix.** Cutting "checklist to end
   of PDF" removed the whole appendix (median appendix 0 tokens). The checklist now ends after its last
   answer's justification or at the next lettered heading.
3. **Unmasked bibliography after the last marker** (e.g. a 2023 paper opens its post-reference text with
   ~2k characters of references). Removed as a leading block; an earlier version that dropped every
   bibliography-like line also removed in-text citations from appendix prose (7–12% of characters) and
   was discarded.
4. **Appendix before the references** (a 2020 paper with 26 appendix pages counted as main body).
   Detected as lettered sections A, B, C (each ≥ 200 characters) in the body; a looser first version
   matched main-body subsections titled "A ..." and was tightened. Affects 0–0.3% of ICLR papers per year.
5. **Appendix tables of contents** produced dozens of empty "sections" and hid the real headings. Runs
   of ≥ 3 contents-like entries are skipped.
6. **Reference-page accounting.** Offsets inside a reference page say nothing about how much of the page
   the list filled; pages are counted at half-page resolution instead of fractional offsets.

## Limitations and open questions

- Tokens measure prose only; appendix tables and equations are counted as markers (`post_tables`,
  `post_equations`), so token growth understates appendix growth.
- Heading categories are coarse (85% agreement with hand labels); 16–26% of appendix text is outside any
  detected lettered heading (numbered or untitled appendices).
- Version strata exist only for ICLR. Other venues' files are partial samples of unknown version mix.
- Why ICLR 2026–27 main bodies carry fewer prose tokens on the same number of pages is open.
- The 2027 appendix jump coincides with a doubled submission cohort, the new AI-use statement and the
  2027 phrasing shift (findings §3). This analysis cannot separate a new population of submitters from
  a change in how papers are written or assembled.

## Reproduction

```bash
python3 scripts/appendix_scan.py --out data/appendix          # ~45 min on 4 cores; ids, lengths, headings
python3 scripts/appendix_analyze.py data/appendix results/appendix
python3 scripts/appendix_checks.py results/appendix/body_tail_residue.csv
```

`data/appendix/` (per-paper rows and section headings, ~25 MB) is git-ignored. `heading_audit.csv` and
`post_region_audit.csv` are hand-made; `appendix_analyze.py` only creates `heading_audit.csv` when it is
absent.
