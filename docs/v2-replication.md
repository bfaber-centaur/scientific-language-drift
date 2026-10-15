# V2 replication (Gate 2, Lane B)

_Lane B, thread "Lane B: V2 longitudinal replication". Dataset `woog/open-text-detector-papers` at
V2 pin `2c0dd192a3d3ba6605ed3f5ed5df145dddbdcb27`; V1 pin `cb5553e0c192c31c562a2822668c7f4ebbb9437a`
stays the default and untouched. Outputs: `results/v2/replication/`. V1 tables, figures and docs are
not modified._

## Pre-specified comparison rules

_Written and committed before any V2 estimate was computed._

**What can change.** Gate 0/1 established that every V1 record is byte-identical in V2 and that 52,128
records were added (`docs/v2-corpus-inventory.md`). For ICLR, only 2024, 2025 and 2026 gained records
(+1,154, +5,458, +14,565); 2017–2023 and 2027 are unchanged. Every V1/V2 difference therefore splits
into three terms, estimated separately:

1. **Modified records.** Expected to be zero. Tested by recounting the V1 records at the V2 pin with V1
   definitions (view `v1repro`) and requiring the V1 tables to reproduce exactly.
2. **Added records**, under V1's definitions unchanged (view `v2def`: every V2 record, ICLR 2025 still
   restricted to the 0-P id stratum). Split further by year (2024, then 2026) for the waterfall.
3. **Methodology.** One change only: ICLR 2025 is now 99.5% complete, so V1's restriction to the 0-P id
   stratum (made because the rest of V1's 2025 sample was biased toward accepted papers) is no longer
   needed. V2's primary view `v2main` uses the whole year minus the 140 title-slug ids. This is reported
   as a sensitivity term (`v2main` − `v2def`), not as a redefinition.

All other definitions are V1's: `omissions` config, tokenizer v1.3, content filter v1.2, statement
removal v2, main body = text before the first `⟦references omitted⟧`, version from V1's header rule,
add-5 smoothing, eligibility prevalence ≥ 1% and df ≥ 20 in the higher cohort, contrasts 2017–21 vs
2025–27 (main), 2024–26 and 2027.

**Verdicts.** For each V1 finding I take the effect V1 reported (a step, a contrast or a level change
relative to the baseline V1 used) and compare the `v2main` effect with it:

- **survives**: same direction, and the V2 effect is within ±25% of the V1 effect;
- **strengthened** / **weakened**: same direction, V2 effect more than 25% larger / smaller;
- **disappears**: the V2 effect falls below the threshold the finding used (e.g. |log2| < 0.5, or a
  step that is no longer larger than the year-to-year variation of 2017–2023);
- **reversed**: opposite direction.

For rankings (top risers and fallers), the finding survives if the Spearman correlation between V1 and
V2 log2 changes over V1's top 100 is ≥ 0.8, no V1 top-25 item changes sign, and ≥ 80% of V1's top 25
stay in V2's top 100.

Because the V1 records are a subset of V2, V1 and V2 estimates are not independent. The informative
comparison for "was V1's sample representative" is **V1 records vs added records** within the same
year, which are disjoint; those differences carry paper-level bootstrap intervals.

**Other venues.** V1's non-ICLR checks (`results/style_shift_checks.csv`) used ≤ 800-paper samples
of V1 records, which were accepted camera-ready papers only. They are compared with V2 **published-only**
cohorts, and ICML additionally without the papers whose title matches an ICLR submission of the same or
previous year (`iclr_overlap`, ~13% of ICML 2026). TMLR is split by version, and its year is treated as
provisional (Gate 1). Venue trajectories are compared within venue, not as cross-venue levels.

## Results

_Pending: the recount is running._
