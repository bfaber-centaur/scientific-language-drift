"""Synthetic checks with hand-computed n-gram counts and denominators."""
import math
from collections import Counter

from mlngrams.count import GroupAccumulator, doc_counts
from mlngrams.filters import is_content
from mlngrams.tokenize import TokenizerConfig, tokenize


def test_basic_tokens_and_lowercase():
    assert tokenize("Neural Networks learn.") == [["neural", "networks", "learn"]]


def test_bigrams_do_not_cross_sentence_boundaries():
    c, ntok, npos = doc_counts("we propose a model. a model is good", 2)
    # segment 1: we propose a model -> 3 bigrams; segment 2: a model is good -> 3
    assert ntok == 8 and npos == 6
    assert c["a model"] == 2
    assert c["model a"] == 0


def test_commas_and_parentheses_do_not_break():
    assert tokenize("deep, (very) deep") == [["deep", "very", "deep"]]


def test_math_characters_break_segments():
    assert tokenize("let x = y + z hold") == [["let", "x"], ["y"], ["z", "hold"]]


def test_hyphenated_line_break_is_repaired():
    assert tokenize("represen-\ntation learning") == [["representation", "learning"]]


def test_internal_hyphen_kept():
    assert tokenize("state-of-the-art results") == [["state-of-the-art", "results"]]


def test_numbers_become_placeholder():
    assert tokenize("trained for 100 epochs") == [["trained", "for", "<num>", "epochs"]]


def test_citations_stripped_by_default_and_act_as_boundary():
    text = "as shown (Vaswani et al., 2017) attention works [3, 12] well"
    assert tokenize(text) == [["as", "shown"], ["attention", "works"], ["well"]]
    raw = tokenize(text, TokenizerConfig(strip_citations=False))
    assert ["vaswani", "et", "al"] == raw[0][2:5]


def test_parenthetical_without_year_is_kept():
    assert tokenize("a model (with dropout) works") == [["a", "model", "with", "dropout", "works"]]


def test_trigrams_and_unigrams():
    c3, _, n3 = doc_counts("a b c d", 3)
    assert c3 == Counter({"a b c": 1, "b c d": 1}) and n3 == 2
    c1, ntok, n1 = doc_counts("a b a", 1)
    assert c1["a"] == 2 and ntok == n1 == 3


def test_short_segment_contributes_no_bigram_positions():
    _, ntok, npos = doc_counts("alone. two words", 2)
    assert ntok == 3 and npos == 1


def test_group_normalization_and_document_frequency():
    acc = GroupAccumulator(n=2)
    docs = [
        "neural network. neural network",  # 2 occurrences, 2 positions
        "a neural network works",  # 1 occurrence, 3 positions
        "nothing here",  # 0 occurrences, 1 position
    ]
    for d in docs:
        acc.add(*doc_counts(d, 2))
    df = acc.to_frame("g").set_index("ngram")
    row = df.loc["neural network"]
    assert row["count"] == 3
    assert row["df"] == 2
    assert acc.positions == 6
    assert math.isclose(row["per_million"], 1e6 * 3 / 6)
    assert math.isclose(row["prevalence"], 2 / 3)
    assert acc.docs == 3 and acc.tokens == 4 + 4 + 2


def test_min_df_prunes_table_but_not_totals():
    acc = GroupAccumulator(n=2)
    acc.add(*doc_counts("rare phrase. common phrase", 2))
    acc.add(*doc_counts("common phrase", 2))
    t = acc.to_frame("g", min_df=2)
    assert list(t["ngram"]) == ["common phrase"]
    assert t["positions"].iloc[0] == 3  # denominator unaffected by pruning


def test_content_filter():
    assert is_content("neural network")
    assert not is_content("of the")
    assert not is_content("<num> epochs")
    assert not is_content("x y")
    assert not is_content("et al")


def test_omission_markers_are_boundaries_not_tokens():
    text = "the loss is ⟦math⟧ minimized by\n⟦equation omitted⟧\nwhere we"
    assert tokenize(text) == [["the", "loss", "is"], ["minimized", "by"], ["where", "we"]]


def test_urls_and_emails_are_boundaries():
    text = "code at https://github.com/a/b-c.git is public. mail me@x.org now"
    assert tokenize(text) == [["code", "at"], ["is", "public"], ["mail"], ["now"]]


def test_citation_residue_not_content():
    assert not is_content("wang et")
    assert not is_content("et al")
