# AI-use disclosure rules by venue (retrieved 2026-10-15)

Used to decide which cohorts' statements are comparable. Quotes are short excerpts of the public pages.

| venue-year | rule | statement template in the LaTeX style? | source |
|---|---|---|---|
| ICLR 2026 | Optional unless significant: "if LLMs played a significant role in research ideation and/or writing to the extent that they could be regarded as a contributor, then authors should describe the precise role of the LLM in a separate section on LLM usage. This section can appear in the appendix". Non-disclosure of significant use "can lead to desk rejection". | **No** (`iclr2026_conference.tex` has no LLM section) | iclr.cc/Conferences/2026/AuthorGuide; github.com/ICLR/Master-Template iclr2026 |
| ICLR 2027 | **Mandatory** AI use statement in the paper, outside the page limit, with Required / Recommended task lists. | **Yes**: boilerplate with bracketed placeholders ("In this work, we used generative AI tools for [tasks with required disclosure]. ...") | iclr.cc/Conferences/2027/AIPolicyForAuthors (`results/disclosures/iclr2027_ai_policy.txt`); Master-Template iclr2027 |
| ICML 2026 | Encouraged only: "We encourage authors to explain any notable ways in which these tools were used in their research methodology." Authors "must take full responsibility". No required section. | not checked | icml.cc/Conferences/2026/CallForPapers ("Generative AI Considerations") |
| COLM 2026 | Not retrieved (colmweb.org now redirects to colm.cc, whose CFP page returned 404). Several COLM 2026 papers write "In accordance with COLM 2026 policy, we disclose ...", so some disclosure rule existed. **Unverified.** | unknown | in-text evidence only |
| NeurIPS 2023-2025, ICML 2023-2025, TMLR, CoRL 2025, EMNLP 2023 | Not checked for disclosure rules; measured prevalence of dedicated sections is the evidence (`inventory.csv`). | | |
