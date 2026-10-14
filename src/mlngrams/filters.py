"""Content-bearing n-gram filter (documented in README.md "Filtering rule").

An n-gram is content-bearing iff EVERY token
  1. is not in STOPWORDS (the NLTK English list, frozen here for reproducibility),
  2. is not the number placeholder <num>,
  3. has at least 2 characters (single letters are almost always math
     variables or broken abbreviations such as "e g", "i e", "et al"),
  4. is not "et" or "al": residue of textual citations "Wang et al. (2023)",
     which the tokenizer does not strip ("wang et" ranked in the 2026 pilot).
Additionally the n-gram must not be in ARTIFACT_NGRAMS, a short hand-curated
list of non-prose boilerplate (e.g. "et al", "arxiv preprint") that is
reported separately rather than silently dropped.

Raw tables are always kept; this filter only produces an additional view.
"""
from __future__ import annotations

FILTER_VERSION = "v1.2"  # v1.1: rule 4 (et/al); v1.2: abbreviation tokens, QA boilerplate additions

STOPWORDS = frozenset(
    """i me my myself we our ours ourselves you you're you've you'll you'd your
    yours yourself yourselves he him his himself she she's her hers herself it
    it's its itself they them their theirs themselves what which who whom this
    that that'll these those am is are was were be been being have has had
    having do does did doing a an the and but if or because as until while of
    at by for with about against between into through during before after above
    below to from up down in out on off over under again further then once here
    there when where why how all any both each few more most other some such no
    nor not only own same so than too very s t can will just don don't should
    should've now d ll m o re ve y ain aren aren't couldn couldn't didn didn't
    doesn doesn't hadn hadn't hasn hasn't haven haven't isn isn't ma mightn
    mightn't mustn mustn't needn needn't shan shan't shouldn shouldn't wasn
    wasn't weren weren't won won't wouldn wouldn't""".split()
)

# Boilerplate n-grams from citations / PDF furniture. Kept in raw tables,
# excluded from the content view, and listed in results so the choice is visible.
ARTIFACT_NGRAMS = frozenset(
    {
        "et al",
        "arxiv preprint",
        "preprint arxiv",
        "conference paper",  # ICLR running header; already removed upstream (QA: 0% of papers)
        # Added 2026-10-14 from the QA review (docs/qa.md): workshop-track header and
        # reference-list residue (venue names) that survive outside the omitted list.
        "workshop track",
        "track iclr",
        "international conference",
        "information processing",
        "neural information",
        "processing systems",
        # Template statement headings; the sections themselves are removed by
        # mlngrams.sections.strip_statements, these catch in-text mentions.
        "reproducibility statement",
        "ethics statement",
        "llm usage",
        "impact statement",
        "broader impact",
        "iclr code",
    }
)  # v1 seed list; extended only after inspecting real text, with each addition noted


# Citation residue and abbreviation tokens produced by tokenizer v1.3 ("e.g." -> "eg").
CITATION_TOKENS = frozenset(
    {"et", "al", "eg", "ie", "wrt", "fig", "figs", "eq", "eqs", "sec", "secs", "tab", "tabs",
     "vs", "cf", "resp", "approx", "ref", "refs", "thm", "lem", "alg", "def", "prop", "app"}
)


def is_content(ngram: str) -> bool:
    if ngram in ARTIFACT_NGRAMS:
        return False
    for tok in ngram.split(" "):
        if tok in STOPWORDS or tok in CITATION_TOKENS or tok == "<num>" or len(tok) < 2:
            return False
    return True
