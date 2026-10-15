# AI-use disclosures in ICLR 2027 submissions (Lane B)

Status: Gate 2 (inventory) done; Gate 3 (validated categories) passed on the second classifier,
narrowly. Population-level use of the labels is in `docs/disclosure-body-analysis.md` (Lane C).

Source: `woog/open-text-detector-papers`, revision `cb5553e0c192c31c562a2822668c7f4ebbb9437a`,
`omissions` config, ICLR 2027 (42,344 papers). Disclosure text is recovered into
`data/disclosures/iclr2027.parquet` (git-ignored). The repository keeps aggregates, ids and short
excerpts (25 words or fewer) only.

Reproduce:

```
python3 scripts/disclosures/extract.py        # recovery -> data/disclosures/, results/disclosures/extraction_*.csv
python3 scripts/disclosures/phrases.py        # phrase tables, template attribution, duplicates, length
python3 scripts/disclosures/taxonomy.py       # rhetorical moves, named tools
python3 scripts/disclosures/sample_labels.py [--round 2]   # stratified label samples
python3 scripts/disclosures/evaluate.py --set test2         # per-category P/R, Wilson CIs
python3 scripts/disclosures/eval_groups.py --set test2      # group confusion matrix + Gate 3 rule
```

## 1. Recovery

`mlngrams.disclosures.extract` (extractor v1) finds the heading ("AI use statement",
"Use of LLMs", "Declaration of generative AI", ...) line by line, as a run-in heading, as a heading
that the PDF reading order placed *after* its body, or (rarely) as a headless opener formula. The
body ends at the next heading, the references marker, an inline "Ethics Statement." run-in, a
blank line after a complete paragraph, or 4,000 characters.

| | papers | % |
|---|---:|---:|
| ICLR 2027 papers | 42,344 | |
| disclosure found | 41,006 | 96.8 |
| clean tier (used below) | 39,351 | 92.9 |
| suspect tier (bibliography residue, multiple candidates, max-length cut, ...) | 1,655 | 3.9 |
| found, under-review versions | | 97.1 |
| found, published versions | | 81.0 |

Forms: heading on its own line 39,854; heading after body 694; run-in 429; headless 29.
Length (clean tier): words P10/P25/P50/P75/P90 = 34/53/78/120/169, mean 93.5, CV 0.66.

**Defect found (preserved, not silently fixed):** 1,700 disclosures (4.0% of 2027 papers) sit in
the main body but were *not* removed by statement removal v2 (`mlngrams.sections`), mostly because
the heading was run-in or placed after its body (`results/disclosures/extraction_leakage.csv`).
Earlier main-body n-gram results for 2027 therefore contain some disclosure text. See
`docs/negative-results.md` N14. Lane C cuts these spans itself.

## 2. Template versus author wording

The ICLR 2027 policy page (`results/disclosures/iclr2027_ai_policy.txt`, retrieved 2026-10-15)
offers an example statement plus Required and Recommended task lists. Each disclosure token is
attributed to:
- **template** if covered by a 4-gram of the policy text (each pasted list item counts on its own);
- **stock** if not template but covered by a 6-gram found in 50 or more disclosures (shared
  community wording);
- **author** otherwise.

Mean shares per disclosure are 19% template, 22% stock and 58% author. Pooled over tokens they are
21.9% template and 18.6% stock. 10,592 disclosures (27%) contain no template 4-gram at all, 4,032
are at least half template, and 168 are at least 90% template. The most frequent trigrams are
almost all template: "used generative ai" (99% template), "the final content" (99.6%), "take
responsibility for" (97%). The exceptions are "by the authors" (0% template; 65% stock, 35%
author) and "ai tools to" (98% stock), so the community converged on wording the template does
not contain. The top author-attributed trigrams are "by the authors", "of the manuscript", "parts
of the", "to assist with", "the authors reviewed" and "experimental results and".

Tables: `results/disclosures/phrases_n{2,3,4}.csv`, each with template, stock and author
percentages; `*_author_only.csv`; phrase frames (`frames.csv`, for example "for the * content":
final 97%, then paper's, scientific, entire); `template_coverage.csv`.

## 3. Copies and formulations

- 37,096 distinct exact texts across 39,351 papers. 3,789 papers fall in 1,534 exact-duplicate
  groups (largest 21), mostly multiple submissions by the same authors.
- MinHash near-duplicates (5-gram Jaccard ≥ 0.8): 1,818 clusters containing 4,566 papers (largest
  24). That leaves 36,603 distinct formulations.
- Several large clusters have zero template share, so the copying is of a lab's or group's own
  wording rather than the policy's (`duplicates.csv`).

## 4. Admission versus disclaimer phrases

Sentences were split into use (156,346) and non-use (27,201) by a negation cue, and compared with
Monroe log-odds (`polarity_phrases.csv`). Use sentences are marked by *reviewed, final, take,
responsibility, ai-assisted, manuscript, text, code, verified*. Non-use sentences are dominated by
the policy's Required list, which authors negate ("formulate mathematical claims", "thematic data
analysis", "conceptual frameworks"). This list is why the earlier keyword classifier (N13) failed:
"we have not used ... to assist in the writing of proofs" contains "writing".

## 5. Taxonomy of moves (non-exclusive, per paper)

| move | % of papers | example (id: excerpt) |
|---|---:|---|
| use declaration | 94.8 | 0MiTxo4j9d: "We used generative AI tools to assist with code implementation and to correct grammar ..." |
| responsibility | 86.5 | 0GCxw4jqE5: "We take full responsibility for the final content of this paper, including its text, claims, code ..." |
| human oversight | 72.3 | 0THBONJE24: "All AI-generated or AI-modified code was reviewed by the authors." |
| non-use declaration | 41.6 | 0GCxw4jqE5: "We did not use generative AI tools to generate synthetic data, develop the capability taxonomy ..." |
| scope limit ("only", "solely") | 15.0 | 2BshioL4kN: "we used generative AI tools solely for language polishing ..." |
| not applicable | 14.6 | 2eoMtzq03h: "... the remaining required disclosure tasks do ..." |
| tool named | 14.2 | 0yk2k2LvaI: "... specifically Claude Code and Codex coding agents." |
| author ownership | 5.3 | 9Xbi0b1Dg7: "All scientific ideas ... were solely conceived and conducted by the authors." |
| placement meta (pasted instructions) | 2.0 | 67TYXrYPBb: "(This section is required and does not count toward the page limit.) ..." |
| AI as object of study | 1.4 | LEJgdrUKxo: "large language models are the primary subject of study ..." |

The patterns are regexes in `scripts/disclosures/taxonomy.py`. Reading 10 matches per move gave
roughly 6/10 to 10/10 precision, so these percentages are approximate. Named tools: ChatGPT, GPT
or OpenAI 9.7%; Claude or Anthropic 5.6%; Codex 4.1%; Gemini 1.7%; DeepSeek 0.9%; any tool 14.4%
(`tools_named.csv`).

## 6. Classification (Gate 3)

Rubric: `results/disclosures/labels/rubric.md`, fixed before labelling. Categories are none /
polish / drafting / coding / literature / other / ambiguous. They are non-exclusive, except that
`none` and `ambiguous` exclude all others. The rubric has 8 decision rules for recurring borderline
cases, and a `writing_unspecified` flag for "help with writing" that does not say whether the help
was polishing or drafting. Only claims of use count. Negated items, not-applicable items, unfilled
placeholders and AI as the object of study get no category.

**Samples:**
- Round 1: dev 60 plus test 180, stratified over template-heavy, negation-heavy, short, long,
  drafting, coding and literature cues, global none, tool named, suspect tier and random
  (`sample.csv`).
- Round 2: test2 of 150, a fresh draw excluding round 1 (`sample_round2.csv`).

**Labellers:** coder 1 (this thread) and coder 2, a separate blind session given only the rubric.
Both are Claude, so the agreement shows the rubric is consistently applicable. It is not human
validation, and a human spot check of about 30 labels is the cheapest remaining check.

| set | exact agreement | per-category kappa |
|---|---:|---|
| test (180) | 0.983 | 0.97–1.00 |
| test2 (150) | 0.960 | 0.96–1.00 (`agreement_test2.csv`) |

**Classifier.** `mlngrams.disclosure_classify` is rule-based and works at clause level. It is
negation-aware: negation must be tied to a use verb, relative-clause and parenthetical negations are
ignored, and "except X" or "other than X" become use claims. It skips oversight clauses and
abstains (`ambiguous`) when there is no AI term or the text is bibliography residue. No LLM
classifier was used because no API access was available.

**Gate 3 rule** (`eval_groups.py`): drafting and polish_only groups each need precision ≥ 0.85 and
recall ≥ 0.80 on held-out labels. *Caveat:* this threshold was written after the v1 per-category
results were seen, though before v1's group results, which then failed it.

| classifier | held-out set | drafting P / R | polish_only P / R | exact match | rule |
|---|---|---|---|---:|---|
| v1 | test | 0.843 / 0.937 | 1.000 / 0.833 | 0.667 | **fail** |
| v1 | test2 | 0.786 / 0.863 | 0.933 / 0.778 | 0.567 | fail |
| v2 (frozen before test2 labels) | test2 vs coder 1 | 0.863 / 0.863 | 0.938 / 0.833 | 0.667 | pass |
| v2 | test2 vs coder 2 | 0.882 / 0.865 | 0.938 / 0.833 | 0.667 | pass |

(`gate3_summary.csv`, `eval_test2.csv`, `eval_groups_test2.csv`, `confusion_groups_test2.csv`.)

v2 was developed on all 240 round-1 labels, which makes the round-1 test set development data;
its in-sample exact match is 0.87. On the untouched test2 set v2 beats v1 on the same statements
(exact 0.67 vs 0.57; drafting precision 0.86 vs 0.79). The pass is narrow:
- the 95% Wilson lower bounds are 0.74 for drafting precision and 0.61 for polish_only recall;
- only 18 test2 statements are polish_only.

Per category on test2:
- polish F1 0.96
- coding 0.94
- literature 0.92
- other 0.88
- drafting 0.86
- `ambiguous` 0.29 (4 abstentions, 1 correct)

Remaining error types (from `--show-errors`):
- extraction residue (an abstract) read as use;
- "presentation" and "organization" read as `other`;
- "condense", "manage length" or "paraphrase paragraphs" missed as drafting;
- one sentence ending without punctuation, which disables all rules (DWxCJ9CV5U);
- implied use in oversight sentences ("AI-assisted code was inspected") not counted.

**Population (v2, clean tier, 39,351):**
- drafting 11,766 (29.9%)
- other_use 21,437 (54.5%): 18,260 polish plus non-writing uses, 3,177 non-writing only
- polish_only 5,358 (13.6%)
- unknown 537 (1.4%)
- none 253 (0.6%)

Explicit non-use is too rare to serve as a comparison group. About 1 in 7 papers claiming drafting
is expected to be misclassified, mostly from other_use.

## 7. What researchers say beyond the template (summary)

About 58% of disclosure tokens are the authors' own, and 27% of statements use no template wording
at all. What authors add beyond the template:
- **Verification claims.** These are the most common addition: "every reported number was
  regenerated by scripts from logged runs", "every reference was checked against arXiv", "proofs
  checked by the Lean kernel".
- **Named tools and models.** 14% name one, sometimes down to the model version and settings.
- **Scope limits.** "Solely for language polishing".
- **Role separation.** Distinguishing AI as a research object, a method component or an evaluation
  judge from AI as an authoring tool.
- **Long itemised accounts.** Some papers report AI involvement in hypotheses, proofs, experiment
  design and drafting the whole paper (for example adLpWqcybD, 584 words, "reconstructed from
  per-track activity logs").

Near-copies are common (4,566 papers in clusters), and most of them carry no template wording.
