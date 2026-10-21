# V2 findings

_Shared by the V2 lanes. Each lane edits only its own labeled section._

## Lane C (function words)

_Source: `docs/v2-function-words.md`, tables and figures in `results/v2/function_words/`._

- **The shift persists on V2.** Independent counter, full census: ICLR submissions' main-body prose
  "of" −48%, "in" −42%, "we" −45%, "and" +39% from 2023 to 2027; abstract "of" −52% from 2024. The
  52k added ICLR 2024–2026 papers have the same rates as V1's records.
- **It is not ICLR-only.** ICML 2026 −32%, TMLR 2026 −28%, COLM 2026 −36% (since 2024), NeurIPS 2025
  and CoRL 2025 −18% in prose "of" since 2023. Placed at their submission deadlines, each venue,
  indexed to its own 2024 rate, declines in parallel from 2024 (figure 3b); published TMLR papers
  decline quarter by quarter from 2025 Q2 to October 2026 with no single step (Lane E, E10). The ICLR 2027 step has no mid-2026 non-ICLR cohort,
  but its distinctive markers ("to" falling, "the" reversing, em dash falling) already move in 2026-drafted
  ICML, COLM and TMLR cohorts, more so the later the deadline.
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
  2025 → 2026), 41 → 17% (COLM), 53 → 23% (TMLR submissions), ICLR-overlap papers removed in all
  three; *test whether* 3 → 10%, 9 → 30%, 6 → 22%. Lane E's quarterly series for published TMLR shows
  "of" falling every quarter from 2025 Q2 with no single step. Smaller than ICLR 2027 (62 → 9%, 2 → 23%) and larger the later
  the text was written. Hypothesis: the ICLR 2027 step is partly a calendar effect. Descriptive only.
- **The 2024 vocabulary burst and its staggered reversal replicate** in complete ICML, NeurIPS, COLM and
  TMLR published cohorts, with NeurIPS a year early on several words.

## Lane D (appendices and disclosures)

_Source: `docs/v2-appendices-disclosures.md`; tables in `results/v2/appendices/` and `results/v2/disclosures/`._

- **The 7% → 47% rise is verified** (median raw post-reference share, ICLR 2017 → 2027). V1.5's
  appendix tables reproduce exactly on V1 records (297/297 rows); the completed ICLR 2024–2026 years
  match V1's partial samples.
- **Every 2026-written cohort shows its venue's largest one-year appendix step with a flat or falling
  main body:** ICLR submissions 2026 → 2027 +1,672 median tokens, ICML +818, COLM +942, TMLR +584 with ICLR-overlap
  papers (title or text match) excluded
  (TMLR with an unchanged cohort size, so cohort doubling is not the whole story for ICLR 2027).
- **Within the same paper the step is not larger:** ICLR resubmissions gain +913 appendix tokens into
  2027 and +1,120 into 2026, so the 2027 jump is mostly between papers.
- **Growth is experimental material** (implementation details, additional results, data, ablations);
  proofs plateau, and examples/prompts rise to about a quarter of ICLR and ICML papers.
- **ICLR 2026 is a new disclosure corpus:** 58% of papers (about 62% with in-text statements) carry an
  LLM section although the policy required one only for "significant" use; 87% sit after the
  references; provisional groups are polish-centred (46% polish-only, 7% drafting vs 14% / 30% in
  2027). COLM 2026 26%, ICML 2026 5%, TMLR 2026 5%.
- **Shared wording in 2027 is mostly the template** (22% of 2027 tokens vs 0.5% in 2026); denials
  appear in 38–41% of ICML and ICLR 2026 statements with no template slot.
- **Validation (2026-10-21):** on 45 items labelled by Bobby and two blind Claude Opus coders, the
  classifier's groups agree with the Opus coders on 34/40 statements (drafting precision 0.89,
  polish-only 1.0; the two coders agree on every item, so they are one machine reader) and with Bobby
  on 25/40. Groups are usable for group-level description; stance (denial) shares are probably
  undercounts. Bobby rates himself an inexperienced annotator.
