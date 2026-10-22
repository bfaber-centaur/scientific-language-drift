# V3: team size and review outcomes, and a corpus-linguistics pass over ICLR 2017–2027

_2026-10-22, thread "V3 new data and exploration". Dataset `woog/open-text-detector-papers` at the V3 pin
`b9bfffba` (`docs/v3-corpus-inventory.md`: +165 records over V2, purely additive). Review metadata from
Paper Copilot's `paperlists` (commit `9fcfd12`), a third-party scrape of OpenReview. Every number cites
a table in `results/v3/`. **Fact**, **interpretation** and **hypothesis** are labelled where it matters.
Nothing here is evidence about who or what wrote any text._

## Summary

1. **Bigger teams get better reviews, and that has hardly changed in ten years (fact).** Each doubling of
   the author count goes with **+0.23 SD in the mean reviewer rating** and **+8 to 9 points in acceptance
   probability** among decided papers. That holds in every year from 2017 to 2026 (`slopes.csv`, spec
   `raw`). The pooled trend in the rating slope is −0.007 SD per year raw (p = 0.01) and zero once the
   prolific-author control is added (p = 0.76). An LLM-era break (2025–26 against 2017–24) is not
   detectable either: +0.007 SD, p = 0.58 (`pooled_trend.csv`).
2. **Most of it survives the obvious confounds (fact), but it is not causal (interpretation).**
   - With controls (the largest number of submissions by any one author on the paper, industry
     affiliation for 2021–24, primary area for 2024–26), the slope is about +0.10 to 0.20 SD in rating and
     +3 to 7 points in acceptance.
   - The same holds within one senior author: among papers sharing a last author in the same year, the
     larger-team paper still rates +0.10 to 0.15 SD higher per doubling, 2019–2026 (`last_fe`).
   - Larger teams are also cited more, holding the decision fixed: within accepted papers, +4 percentile
     points per doubling in 2017 and +12 in 2023–24 (`citations_within_decision.csv`). This is the one
     relation that grew.
   - Reverse causation is the main alternative. Promising projects attract more contributors, and more
     authors means more compute, experiments and polish. These data cannot separate the two.
3. **What did shift is who submits (fact).** Papers with 9 or more authors went from **2.2% of submissions
   (2017) to 14.6% (2026)**, and 12+ from 0.6% to 4.6%. The mean team grew from 3.7 to 5.7 authors
   (`coverage.csv`). Single-author papers fell further behind: their accept rate among decided papers was
   0.26 in 2017 and **0.155 in 2026**, about half the rate of a 4-author paper (`bins.csv`; 21 single-author
   papers in 2017, 430 in 2026). Larger teams used to withdraw less often. By 2026 that difference has
   gone (withdrawal slope from −0.067 in 2018 to +0.004 in 2026).
4. **ICLR 2026 is the one year where decisions favoured large teams beyond their scores (fact). The cause
   is unknown, but the review process changed that year (hypothesis).** Holding the mean rating fixed
   (a flexible spline), team size added 0 to 1.7 points of acceptance per doubling in 2019–2025 and
   **+2.4 ± 0.8 points in 2026** (`decision_given_rating.csv`; +2.0 with the prolific-author control).
   ICLR 2026's process was unusual. After the 2025-11-27 OpenReview leak, ICLR reset every score to its
   pre-rebuttal value, froze discussion, and gave affected papers new area chairs. Those chairs were asked
   to infer what discussion would have concluded ([ICLR blog](https://blog.iclr.cc/?p=1063),
   [retrospective](https://blog.iclr.cc/?p=1116)). The leak also exposed author identities. One reading:
   chairs working without the discussion leaned more on other signals. It is untested here.
5. **The corpus-linguistics pass finds a long, steady rise in promotional and "compressed" style. ICLR 2027
   then breaks it (fact; fig. `results/v3/style/fig_style_trends.png`).**
   Every series below is per 1,000 body tokens on ICLR rejected and withdrawn submissions (one version
   throughout), 2017 → 2023 → 2026, then ICLR 2027:

   | feature (method) | 2017 | 2023 | 2026 | 2027 |
   |---|---:|---:|---:|---:|
   | hype adjectives (Millar et al. 2022 style) | 2.2 | 3.6 | **5.7** | **1.9** |
   | Kobak-style LLM-excess words | 0.30 | 0.62 | 1.74 | 0.32 |
   | boosters (Hyland 2005) | 2.5 | 3.0 | 3.7 | 2.7 |
   | hedges (Hyland) | 5.6 | 4.8 | 4.6 | **3.5** |
   | attitude markers (Hyland) | 1.09 | 0.90 | 0.80 | **0.38** |
   | self-mention *we/our/us* (Hyland) | 23.7 | 25.1 | 20.8 | **13.9** |
   | reader engagement (Hyland) | 2.2 | 2.1 | 1.0 | 0.6 |
   | nominalisations (Biber's compressed style) | 49 | 53 | 64 | 63 |
   | passives (approx.) | 11.8 | 10.7 | 8.7 | 7.7 |
   | MTLD lexical diversity (McCarthy & Jarvis 2010) | 63 | 62 | **89** | **98** |
   | mean word length | 5.11 | 5.19 | 5.66 | 5.71 |

   - Hype rose every year since 2017, not only since ChatGPT. It accelerated in 2024–26 and is matched by
     accepted ICML and NeurIPS papers (4.6 and 5.3 in their 2026 and 2025 cohorts).
   - **ICLR 2027 (written mid-2026) drops back to 2017 levels of hype and LLM-excess words.** Its authors
     also step out of the text: half the self-mention, half the attitude markers, fewer hedges, shorter
     sentences. The compression features (nominalisations, word length, lexical diversity) stay at their
     2026 highs. "Novel" appears at least once in 64% of ICLR 2026 bodies and 15% of 2027 bodies. This
     extends V1 findings 2 and 3 (rhetorical burst fading, 2027 break) from single words to whole
     metadiscourse categories.
   - **MTLD jumps by 40% between 2025 and 2027** after six flat years. Lexical diversity is not independent
     of the function-word thinning (V2 Lane C): fewer function words raise any type-token measure. Read it
     as another view of that change, not as new evidence.
6. **Reviewers barely respond to style (fact; a negative result worth keeping).** Among submission
   versions with ratings, each feature (standardised within year) moves the rating by less than 0.1 SD,
   after controlling team size and length (`rating_slopes.csv`).
   - **Hype and LLM-excess words: about zero in every year** (2025: −0.01 / −0.03; 2026: +0.03 / +0.04).
   - Self-mention (+0.07 to 0.08) and boosters (+0.05 to 0.07) are slightly positive.
   - Passives (−0.05) and long sentences (−0.065) are slightly negative.
   - So whatever drives the team-size gradient in ratings, it is not visible in these style measures.
7. **Larger teams write in a more promotional, more compressed register, and that gradient grew (fact).**
   - Per doubling of authors (controls: length, decision), LLM-excess words rose +0.16 to 0.21 SD in
     2017–23 and +0.30 to 0.33 SD in 2025–26. Hype went from +0.13 to 0.18 to +0.25, and engagement
     markers from −0.1 to −0.2 (`team_slopes.csv`).
   - About a quarter of this is topic: with primary-area fixed effects in 2024–26 the LLM-marker slope
     falls from 0.30 to 0.22. Roughly half is "hub" authors: adding the largest per-author submission
     count halves it again. Papers that include an author with 17+ ICLR 2026 submissions use 1.6× the
     LLM-excess vocabulary of papers whose authors submitted once.
     (Interpretation: large, prolific groups converged faster on the new house style. It is not a claim
     about tool use.)
8. **Keyness (Dunning G², Hardie's Log Ratio), on the same document version (fact):**
   - ICLR 2026 against 2023 submissions is dominated by topic turnover (*qwen, llama, grpo, sft, cot,
     llm(s), reasoning*). The non-topical risers are *across, while, enabling, thereby, consistently,
     these*. The fallers are *the, can, will, there, note, have* (`keyness_iclr2026sub_vs_2023sub.csv`).
   - Withdrawn against rejected papers (2023 and 2026): withdrawn papers lean towards vision, video and
     multimodal applications. Rejected-but-not-withdrawn papers lean towards theory (*theorem, assumption,
     convergence, bound, proof*).
   - ICLR 2026's 905 desk rejects (70 in 2025) are topically off-centre: energy, quantum, sepsis, Afan
     Oromo, thermal.
   - **A warning in the data:** accepted against rejected keyness in 2026 is led by *university,
     institute, tsinghua, peking, internship*. Those words come from the camera-ready author blocks. Any
     accepted-against-rejected text comparison on this corpus measures the version difference unless both
     sides are submissions.

## Methods

- **Team size and review data** (`scripts/v3/review_meta.py`): ICLR main track, 2017–2026, 55,938 papers.
  - The outcomes: rating = mean reviewer score, z-scored within year (the scale changed in 2024 and
    2026); acceptance = linear probability among accept/reject (withdrawn and desk-rejected excluded);
    withdrawal; citations = Google Scholar percentile within year (no counts for 2026).
  - The author key is the OpenReview profile id where present (2021–24), otherwise the name. 2025–26
    carry names only. A name-against-id refit on 2021–24 changes no slope by more than 0.02
    (`name_collision_check.csv`).
  - Industry: affiliation domain or name on a fixed list. Known only for 2021–24, because 2017–20
    affiliations are empty and 2025–26 have none.
  - 2026 ratings are pre-rebuttal (the reset above). 2025 and earlier are as scraped, presumably final.
  - Model: `scripts/v3/authors_quality.py`.
- **Style** (`scripts/v3/style_features.py`): omissions config, body before the reference list, template
  statement sections cut, tokenizer v1.3. Papers under 500 tokens are dropped.
  - The word lists are fixed in the script. They are subsets in the spirit of Hyland (2005,
    *Metadiscourse*), Millar, Batalo & Budgell (2022, *JAMA Netw Open*) for hype, and Kobak et al. (2025,
    *Sci Adv*) for excess vocabulary. They are not the authors' exact lists.
  - MTLD uses threshold 0.72 (forward/backward mean) and MATTR a 500-token window. Passives are
    approximated as a be-form plus a participle.
  - Analysis and keyness: `scripts/v3/style_analyze.py`.
- **Version.** The omissions text has no venue header, so ICLR decision stands in for version. Checked
  against `scripts/v2/version_mix.py` on ICLR 2019 and 2024 (`results/v3/style/version_proxy_check.csv`):
  accepted papers are camera-ready in 96–98% of cases (most of the rest match no header), and rejected or withdrawn ones are submissions in
  98–99.8%. (Running `version_mix.py` overwrites `results/v2/inventory/version_mix.csv`, which was
  restored. Pass a different working copy if you rerun it.)

## Negative results and caveats

- No change in the team-size → rating or → acceptance relation over 2017–2026, and no LLM-era break.
- Style features do not predict ratings beyond ±0.1 SD. Hype and LLM-excess vocabulary are not penalised.
- The style-to-rating sample is restricted to non-accepted papers to keep the version fixed. That cuts
  off the top of the rating range and attenuates slopes.
- The review data are a third-party scrape. The decisions match OpenReview's public counts (accept rates
  and withdrawal counts per year look right), but no row was checked against OpenReview itself.
- The first-author fixed-effect estimates are noisy before 2021 and are not interpreted.
- ICLR 2027 has no authors or reviews yet, so points 1–4 and 6–7 stop at 2026.
- Lexicon rates are per-token counts of fixed words. They miss sense (e.g. *critical* point, *robust*
  statistics) and are topic-sensitive. That is why the team-size gradients were also fitted with area
  fixed effects.

## Next steps worth doing

- ICLR 2027 reviews (due late 2026): first test of whether the 2027 register shift is rewarded or
  penalised, and whether the 2026 decision-stage team-size effect persists without a leak.
- Biber-style multidimensional analysis with a proper tagger (spaCy), to replace the approximate passive
  and nominalisation counts.
- Collocation shifts (log-Dice) for *novel*, *robust* and *across*, to see whether meaning moved or only
  frequency.

## Reproduce

    python3 scripts/v3/review_meta.py --src <paperlists checkout>
    python3 scripts/v3/authors_quality.py
    python3 scripts/v3/style_features.py --jobs 4      # ~100 min on 4 cores, downloads ~4 GB
    python3 scripts/v3/style_analyze.py
