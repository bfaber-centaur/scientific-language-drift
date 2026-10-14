"""Content-bearing n-gram filter (documented in README.md "Filtering rule").

An n-gram is content-bearing iff EVERY token
  1. is not in STOPWORDS (the NLTK English list, frozen here for reproducibility),
  2. is not the number placeholder <num>,
  3. has at least 2 characters (single letters are almost always math
     variables or broken abbreviations such as "e g", "i e", "et al").
Additionally the n-gram must not be in ARTIFACT_NGRAMS, a short hand-curated
list of non-prose boilerplate (e.g. "et al", "arxiv preprint") that is
reported separately rather than silently dropped.

Raw tables are always kept; this filter only produces an additional view.
"""
from __future__ import annotations

FILTER_VERSION = "v1"

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
        "conference paper",  # ICLR running header "published as a conference paper at iclr"
    }
)  # v1 seed list; extended only after inspecting real text, with each addition noted


def is_content(ngram: str) -> bool:
    if ngram in ARTIFACT_NGRAMS:
        return False
    for tok in ngram.split(" "):
        if tok in STOPWORDS or tok == "<num>" or len(tok) < 2:
            return False
    return True
