# Negative results, false leads and methodological corrections

_Kept on purpose: each entry is something that looked like a result, or a method that looked fine, and
was not. Dates are 2026-10-14 unless noted._

## N1. The ICLR 2027 "AI use" risers were template text, not a linguistic trend

**What we first saw.** The first full longitudinal run (body text, statement removal v1) ranked 43 of
the top 100 content risers (2017–21 → 2025–27) as 2027-only bigrams: *generative ai*, *ai tools*,
*ai use*, *use statement*, *final content*, *text claims*, *take responsibility*, *ai-assisted work*.
Read naively, this was "a sudden 2027 surge of AI vocabulary in ML papers".

**How it was caught.** The longitudinal script flags `spike_2027` (2027 rate ≥ 8× the 2024–26 rate).
The flagged bigrams clustered into one phrase family, and "ai use statement" had 85% prevalence in
2027 bodies. A census of short heading lines in 2027 found `AI USE STATEMENT` as a heading in 351 of
400 sampled papers (plus variants: AI-USE STATEMENT, AI DISCLOSURE, USE OF AI TOOLS, STATEMENT ON THE
USE OF LARGE LANGUAGE MODELS, AI ASSISTANCE DISCLOSURE). ICLR 2027 requires this statement; statement
removal v1 only knew the 2026 LLM-usage wording.

**Fix.** `src/mlngrams/sections.py` v2 adds the 2027 headings (test:
`test_ai_use_statement_variants_removed`). On 1,000 sampled 2027 papers, prevalence after removal:
"generative ai" 73% → 3.5%, "ai use" 90% → 2.1%, "take full responsibility" 31% → 1.1%,
"reproducibility statement" 71% → 1.5% (residuals are in-text mentions). All counts were rerun.

**Status.** The v1 result is invalid and must not be quoted as a trend. The risers that remain after
the fix are in `docs/findings.md` (finding 3); they are different phrases.

## N2. Required statement sections inflated the 2024–2026 risers (pilot)

QA on the pilot found 7 of the top 25 prevalence risers were statement text (*reproducibility
statement* 49% of 2026 papers, *ethics statement* 34%, *llm usage* 21%, *iclr code*, *full
responsibility*, *personally identifiable*, *ensure reproducibility*). Fix: statement removal v1 and
boilerplate filter additions (`docs/qa.md`). This is why N1 was looked for at all.

## N3. Tokenizer defects that produced spurious n-grams (pilot, v1.2)

Found by QA (`docs/qa.md`, D1–D6), fixed in v1.3: "(LLMs)" produced the bigram *models llms* in 53% of
2026 papers; decimals split into two numbers and an extra boundary (27 per paper in 2018, 73 in 2026, so
the bias grew over time); "e.g."/"Fig." created false sentence boundaries; all-caps headings fused with
the next sentence (*introduction deep*); "naïve" split into "na ve"; "state-of-the-\nart" lost a hyphen.

## N4. Per-year pruning made "new in year X" undefined

The first count tables kept n-grams with df ≥ 3 per year, so absence in a year meant "0–2 papers", not
zero; all 40 naive top risers were "absent in 2018". Fix: keep the union of n-grams with df ≥ 3 in any
year, with exact rows for all years.

## N5. Appendix growth changes trends, including signs

Appendix share of text grew from 7% (2017) to 47% (2027). Between 2018 and 2026, body-only vs all-text
log2 changes: *batch size* −0.32 vs −0.86; *related work* −0.19 vs +0.05 (sign flips); *see appendix*
+0.30 vs +0.77. Headline analyses therefore use main-body text; all-text is a sensitivity run.

## N6. Version mix: affiliations "fall" in 2027 because 2027 has no camera-ready papers

*google brain*, *facebook ai*, *university*, *corresponding author* drop sharply in 2026→2027 mostly
because 2027 is 94% anonymous submissions. Within submissions only the drops shrink (e.g. *facebook ai*
log2 −4.0 instead of −6.7). Affiliation n-grams are not evidence of anything linguistic.

## N7. Workshop-track headers looked like the strongest fallers

*workshop track* and *track iclr* topped the pilot fallers; they come from workshop papers (~2% of 2018).
Now on the boilerplate list.

## N8. ICLR 2025 partial extraction is biased toward accepted papers

The 0–P id stratum looks complete (30.2% camera-ready); ids Q–z (43.7%) and title-slug ids (100%) are a
partial, accepted-heavy remainder. Using all of 2025 would have mixed in more camera-ready text. Fix:
year-level 2025 uses the 0–P stratum only.

## N9. Pre-registered predictions that failed

Main contrast (2017–21 → 2025–27): 17 of 36 predictions held. Most misses are stylistic phrases
predicted flat or up that came out down, because their 2027 rates collapse; the function-phrase control
*of the*, predicted flat, fell by about 1 bit. Excluding 2027 (2024–26 contrast): 30 of 36 held; misses:
*a novel* and *novel approach* (up, predicted flat), *furthermore* and *robust* (flat, predicted up),
*graph neural* (flat, peaked 2021), *generative adversarial* (steady decline, not a peak).
(`results/full/longitudinal/watchlist_evaluation.csv`; numbers from the first run, recheck after rerun.)

## N10. "of the" is not a stable baseline

The pre-registered function-phrase control moved: 8,784 → 3,338 per million (2017 → 2027). Any
per-million comparison of 2026/2027 with earlier years shares this shift (finding 4). Claims are made in
prevalence where possible.

## N11. Hypothesis weakened: "the 2027 shift is a cohort-wide editing pass"

If every 2027 paper had been run through the same rewriting, resubmitted papers would move with the
cohort. In 55 ICLR 2026 → 2027 resubmission pairs, "we propose" stays at 78% → 76% (cohort: 80% → 51%)
and stopword share barely moves (0.343 → 0.340). Caveat: pairs are matched by near-identical abstracts,
so heavily rewritten resubmissions are missed (`results/resubmission_summary.csv`).

## N12. Operational: a sensitivity run silently did not happen

The first all-text sensitivity run crashed at startup (the background shell lost its working directory)
and the analysis agent reported its sensitivity columns as empty. Runs are now launched with absolute
paths, and each run's completion is checked via its `run.json` before use.

## N13. AI-use classifier: "no AI use" class is nearly empty

Keyword classes of 2027 AI-use statements put only 42 of 12,000 papers in "none"; many statements that
deny substantive use also contain "we used ... for grammar". The "none" contrast is therefore not usable
without hand labels.
