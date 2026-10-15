"""Synthetic tests for disclosure extraction and the negation-aware classifier."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mlngrams.disclosure_classify import classify  # noqa: E402
from mlngrams.disclosures import extract  # noqa: E402


def test_extract_heading_line_and_end_at_next_heading():
    t = "Conclusion text.\nAI USE STATEMENT\nWe used ChatGPT to polish the text.\nETHICS STATEMENT\nNo humans."
    d = extract(t)
    assert d.text == "We used ChatGPT to polish the text." and d.form == "line" and d.end_reason == "heading"


def test_extract_run_in_ends_at_inline_statement_heading():
    t = "x\nAI Use Statement. AI assisted with code. Ethics Statement. We used public data.\n"
    d = extract(t)
    assert d.form == "run_in" and d.text == "AI assisted with code."


def test_extract_ignores_prose_mentioning_ai():
    assert extract("We used LLMs to generate candidate answers for the benchmark.\n") is None


def test_negated_template_list_is_not_use():
    t = ("In this work, we used generative AI tools for language polishing. We have not used generative AI tools "
         "for formulating mathematical claims, assisting in the writing of proofs, or drafting sections of the paper.")
    assert classify(t)["labels"] == {"polish"}


def test_global_non_use():
    assert classify("No generative AI tools were used in conducting this research or preparing this manuscript.")["labels"] == {"none"}


def test_exception_inside_negation_is_use():
    assert classify("Generative AI was not used for anything other than grammar correction.")["labels"] == {"polish"}


def test_mixed_use():
    out = classify("We used Claude to draft parts of the introduction and to debug our training code.")
    assert out["labels"] == {"drafting", "coding"}


def test_generic_writing_flag():
    out = classify("LLMs were used to assist with writing.")
    assert out["labels"] == set() and out["writing_unspecified"]
