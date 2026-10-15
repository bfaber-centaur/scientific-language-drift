# AI-use disclosure labelling rubric (v1, fixed 2026-10-15 before labelling)

Unit: one paper's recovered disclosure (`text_clean`). Labels record **claims of AI use made by the
authors**. Negated items ("we have not used generative AI tools for ..."), items declared not
applicable, hypothetical or example wording, unfilled template placeholders, and AI that is only the
*subject of study* are **not** use claims and get no category.

Categories are non-exclusive, except that `none` and `ambiguous` exclude every other category.

| Code | Category | Assign when the authors claim AI was used for ... |
|---|---|---|
| `none` | No AI use disclosed | nothing: the statement says no generative AI was used, or contains only non-use / not-applicable claims |
| `polish` | Language editing / polishing | surface changes to author-written text: grammar, spelling, typos, punctuation, wording or phrasing of sentences, fluency, clarity, readability, style, tone, terminology consistency, translating author text |
| `drafting` | Drafting or rewriting prose | producing manuscript prose: drafting or writing sections, paragraphs, abstracts, captions, appendix text; rewriting, restructuring, condensing or reorganising passages; turning notes into text |
| `coding` | Coding / experimentation / analysis | writing, editing or debugging code; implementing methods or baselines; running or scripting experiments; data processing or cleaning; generating synthetic data; statistical or data analysis; interpreting results; making plots or figures with code |
| `literature` | Literature search / summarisation | finding, discovering, retrieving, summarising, comparing or organising related work |
| `other` | Other assistance | ideation, brainstorming, hypotheses, theory, mathematical claims or proofs, methodology or experiment-design feedback, critique of the manuscript, LaTeX / table / reference formatting, figure design without code, titles or keywords, consistency or citation checking, outline or structure suggestions |
| `ambiguous` | Ambiguous / unclassifiable | use is claimed but no task can be identified ("AI tools were used in preparing this work"), the text is not a disclosure (extraction error), or it contradicts itself |

Flag (not a category): `writing_unspecified` — "writing assistance", "assist with writing", "aid
writing", "help with the paper" with no indication of polishing versus drafting. A clause flagged this
way adds neither `polish` nor `drafting`. If it is the only use claim, the categories are empty and the
statement is treated as unknown on the drafting / polishing axis (it is **not** `ambiguous`, which is
reserved for statements where no task at all can be identified). "Aid or polish writing" gets `polish`
plus the flag.

Flags recorded alongside: `template_only` (nothing beyond template sentences, pasted task-list
items or placeholders), `negated_list` (contains negated or not-applicable task items).

Decision rules for recurring borderline cases:
1. "Drafting and editing text" → `drafting` (plus `polish` only if polishing words also appear).
2. "Rephrasing sentences", "improving phrasing" → `polish`; "rewriting paragraphs/sections" → `drafting`.
3. "Manuscript organisation" / "structuring the paper": `other` if suggestions only ("suggest a
   structure"), `drafting` if the AI reorganised or restructured the text.
4. "Except for X", "beyond X", "only for X", "other than X" make X a use claim.
5. "Generated synthetic data", "implemented methods", "interpreted results" → `coding`.
6. "Feedback on the manuscript", "proofreading for errors of fact" → `other`; "proofreading" alone → `polish`.
7. LLMs used as a component of the proposed method or as evaluation judges are use claims → `coding`.
8. Figures or tables produced from code → `coding`; "create or modify figures" with no code mentioned → `other`.
