"""Independent QA (Agent D): synthetic documents with hand-computed counts.

Expected values below were derived by hand from the README rules, not by running
the tokenizer. Tests marked xfail(strict=True) document current defects: they
fail today and will start "passing" (and so error, because strict) once fixed.
Update 2026-10-14: defects D1-D6 fixed in tokenizer v1.3; those tests are now plain tests.
"""
import hashlib
import math
import os
import subprocess
import sys

import pandas as pd
import pytest

from mlngrams.count import GroupAccumulator, doc_counts
from mlngrams.filters import is_content
from mlngrams.tokenize import tokenize

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOC_A = (
    "Published as a conference paper at ICLR 2018\n"
    "We propose a neural network (Smith et al., 2020). The neural network is ⟦math⟧ "
    "robust, e.g. to noise. See https://github.com/x/y for code.\n\n"
    "The neu-\nral network uses 3 layers."
)
DOC_B = "Smith et al. (2020) showed the neural network works.\x0cNeural network training is hard; i.e. slow."
DOC_E = "Efficient ﬁne-tuning of LLMs."

# Hand derivation.
SEGS_A = [
    "published as a conference paper at iclr <num> we propose a neural network".split(),
    "the neural network is".split(),
    ["robust", "eg", "to", "noise"],  # v1.3: "e.g." is not a boundary
    ["see"],
    ["for", "code"],
    "the neural network uses <num> layers".split(),
]
SEGS_B = [
    ["smith", "et", "al"],
    "showed the neural network works".split(),
    "neural network training is hard".split(),
    ["ie", "slow"],  # v1.3: "i.e." is not a boundary
]
SEGS_E = [["efficient", "fine-tuning", "of", "llms"]]
TOKENS = {"A": 30, "B": 15, "E": 4}
POS = {  # n -> per doc (updated by hand for tokenizer v1.3 abbreviation rule)
    1: {"A": 30, "B": 15, "E": 4},
    2: {"A": 24, "B": 11, "E": 3},
    3: {"A": 19, "B": 7, "E": 2},
}


def test_hand_segmentation_matches():
    assert tokenize(DOC_A) == SEGS_A
    assert tokenize(DOC_B) == SEGS_B
    assert tokenize(DOC_E) == SEGS_E


@pytest.mark.parametrize("n", [1, 2, 3])
def test_doc_positions(n):
    for name, text in (("A", DOC_A), ("B", DOC_B), ("E", DOC_E)):
        _, ntok, npos = doc_counts(text, n)
        assert ntok == TOKENS[name]
        assert npos == POS[n][name]


def test_group_accumulator_exact():
    accs = {n: GroupAccumulator(n=n) for n in (1, 2, 3)}
    for t in (DOC_A, DOC_B, DOC_E):
        for n, acc in accs.items():
            acc.add(*doc_counts(t, n))
    t2 = accs[2].to_frame("g").set_index("ngram")
    assert accs[2].positions == 38 and accs[2].docs == 3 and accs[2].tokens == 49
    r = t2.loc["neural network"]
    assert (r["count"], r["df"]) == (5, 2)
    assert math.isclose(r["per_million"], 1e6 * 5 / 38)
    assert math.isclose(r["prevalence"], 2 / 3)
    assert t2.loc["et al", "count"] == 1
    assert "network the" not in t2.index  # sentence boundary
    assert "is robust" not in t2.index  # ⟦math⟧ boundary
    assert "network smith" not in t2.index and "network we" not in t2.index  # citation boundary
    t1 = accs[1].to_frame("g").set_index("ngram")
    assert (t1.loc["<num>", "count"], t1.loc["<num>", "df"]) == (2, 1)
    assert (t1.loc["the", "count"], t1.loc["the", "df"]) == (3, 2)
    assert "efficient" in t1.index and "fine-tuning" in t1.index  # ligatures folded
    t3 = accs[3].to_frame("g").set_index("ngram")
    assert accs[3].positions == 28
    assert t3.loc["the neural network", "count"] == 3
    assert t3.loc["neural network training", "df"] == 1


def _write_cache(tmp_path):
    def row(pid, text, sha=None):
        return {
            "paper_id": pid,
            "openreview_id": pid,
            "title": "t",
            "conference": "ICLR",
            "year": 9999,
            "pdf_sha256": "p" + pid,
            "text": text,
            "text_sha256": sha or hashlib.sha256(text.encode()).hexdigest(),
            "source_clean_text_sha256": "",
            "omission_counts_json": "{}",
            "omissions_json": "[]",
            "chars_clean": len(text),
            "chars_after": len(text),
        }

    rows = [row("A", DOC_A), row("B", DOC_B), row("C", DOC_A), row("D", "   "), row("E", DOC_E)]
    d = tmp_path / "cache" / "omissions"
    d.mkdir(parents=True)
    pd.DataFrame(rows).to_parquet(d / "iclr-9999.parquet", index=False)
    return tmp_path / "cache"


def test_count_script_end_to_end(tmp_path):
    cache = _write_cache(tmp_path)
    out = tmp_path / "out"
    env = dict(os.environ, MLNGRAMS_CACHE=str(cache))
    subprocess.run(
        [sys.executable, os.path.join(ROOT, "scripts", "count_ngrams.py"), "--years", "9999",
         "--min-df", "2", "--workers", "1", "--out", str(out)],
        check=True, env=env, capture_output=True,
    )
    docs = pd.read_parquet(out / "docs.parquet").set_index("doc_id")
    assert sorted(docs.index) == ["A", "B", "E"]
    for n in (1, 2, 3):
        for k in ("A", "B", "E"):
            assert docs.loc[k, f"positions_{n}"] == POS[n][k]
    dups = pd.read_csv(out / "duplicates.csv").set_index("doc_id")
    assert dups.loc["C", "reason"] == "duplicate_text" and dups.loc["C", "same_as"] == "A"
    assert dups.loc["D", "reason"] == "empty_text"
    tot = pd.read_csv(out / "totals.csv").set_index("n")
    assert list(tot["positions"]) == [49, 38, 28] and set(tot["docs"]) == {3}
    assert set(tot["tokens"]) == {49}
    n2 = pd.read_parquet(out / "ngrams_n2.parquet").set_index("ngram")
    assert set(n2["df"]) == {2}  # min_df=2 prunes table ...
    assert "et al" not in n2.index
    assert set(n2["positions"]) == {38}  # ... but not the denominator
    assert sorted(n2.index) == ["neural network", "the neural"]
    r = n2.loc["neural network"]
    assert r["count"] == 5 and math.isclose(r["per_million"], 1e6 * 5 / 38)
    assert math.isclose(r["prevalence"], 2 / 3)
    n1 = pd.read_parquet(out / "ngrams_n1.parquet").set_index("ngram")
    assert n1.loc["the", "count"] == 3 and "<num>" not in n1.index  # <num> has df 1


def test_content_filter_cases():
    assert not is_content("conference paper")
    assert not is_content("smith et")
    assert is_content("fine-tuning llms")
    assert not is_content("<num> b")


# ---- Documented defects (strict xfail) ----


def test_decimal_is_one_number():
    assert tokenize("accuracy of 0.5 on it") == [["accuracy", "of", "<num>", "on", "it"]]



def test_diacritics_do_not_split_words():
    assert tokenize("a naïve model") == [["a", "naive", "model"]]


def test_page_break_inside_sentence_joins():
    # Deliberate: in this corpus \x0c mostly sits inside running sentences (running headers are
    # already removed upstream), so joining across it is correct.
    assert tokenize("the model\x0c\nlearns fast") == [["the", "model", "learns", "fast"]]



def test_heading_line_does_not_join_prose():
    segs = tokenize("1\nINTRODUCTION\nDeep learning works")
    assert ["introduction", "deep"] not in [s[i:i + 2] for s in segs for i in range(len(s) - 1)]



def test_parenthetical_acronym_not_joined():
    segs = tokenize("large language models (LLMs) can reason")
    assert "llms" not in [t for s in segs for t in s] or ["models", "llms"] not in [s[i:i + 2] for s in segs for i in range(len(s) - 1)]



def test_abbreviation_not_split():
    assert tokenize("see Fig. 2 for details") == [["see", "fig", "<num>", "for", "details"]]



def test_compound_hyphen_at_line_end():
    assert tokenize("state-of-the-\nart model") == [["state-of-the-art", "model"]]
