# V2 findings

_Shared by the V2 lanes. Each lane edits only its own labeled section._

## Lane C (function words)

_Source: `docs/v2-function-words.md`, tables and figures in `results/v2/function_words/`._

- **The shift persists on V2.** Independent counter, full census: ICLR submissions' main-body prose
  "of" −48%, "in" −42%, "we" −45%, "and" +39% from 2023 to 2027; abstract "of" −52% from 2024. The
  52k added ICLR 2024–2026 papers have the same rates as V1's records.
- **It is not ICLR-only.** ICML 2026 −32%, TMLR 2026 −28%, COLM 2026 −36% (since 2024), NeurIPS 2025
  and CoRL 2025 −18% in prose "of" since 2023. Placed at their submission deadlines, the venues follow
  one decline that starts in 2024 (figure 3b). The ICLR 2027 step has no non-ICLR cohort to test
  against yet.
- **It is in the authors' text.** Abstracts posted to arXiv (no PDF extraction) show the same rates as
  the dataset's abstracts: "of" 24.3k (ICLR 2024 papers) → 12.6k (2027) per million.
- **It is set at drafting.** Same papers moved from ICLR 2026 to an ICML 2026 camera-ready keep their
  prose rates (−0.5%); resubmissions change in proportion to how much they were rewritten.
- **Construction:** the *the X of Y* pattern falls 62% (2023→2027) while hyphenated compound modifiers
  rise by half. ICLR 2027 also differs in kind: "to" −32% and ", and" +65% in one year, shorter
  sentences, and the em dash halves after rising everywhere through 2026.
- No cause is identified, and none of this is evidence about writing tools.

## Lane B (replication)

_Source: `docs/v2-replication.md`; tables and figures in `results/v2/replication/`._

- **Every per-year V1 finding survives on the complete corpus** (75 of 75 effects within the
  pre-specified ±25%): the 2024 burst and fade, the 2027 break (all versions and submissions only),
  function words, stopword share, "across". The 21k papers added to ICLR 2024–2026 match V1's records
  in the same year. V1's records reproduce V1's tables exactly, except one 2027 paper now deduplicated
  against an identical added 2026 paper.
- **V1's pooled corpus-weighted contrasts were mostly 2027.** ICLR 2027 was 81% of V1's 2025–27
  cohort and is 58% of V2's. Corpus-weighted log2 changes move by a median 0.5 bits; year-balanced ones
  by 0.02. Seven watchlist verdicts flip (pre-registered hits 17 → 24 of 36), e.g. *a novel* and
  *we propose* change from "down" to the predicted "flat".
- **The 2027 register appears in other venues' 2026-written cohorts**: *a novel* 59 → 33% (ICML
  2025 → 2026, ICLR-overlap papers removed), 41 → 18% (COLM), 53 → 25% (TMLR submissions); *test
  whether* 3 → 10%, 9 → 30%, 6 → 21%. Smaller than ICLR 2027 (62 → 9%, 2 → 23%) and larger the later
  the text was written. Hypothesis: the ICLR 2027 step is partly a calendar effect. Descriptive only.
- **The 2024 vocabulary burst and its staggered reversal replicate** in complete ICML, NeurIPS, COLM and
  TMLR published cohorts, with NeurIPS a year early on several words.
