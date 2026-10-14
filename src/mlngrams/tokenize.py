"""Tokenization for lexical n-gram counting.

Every rule here is deliberate and documented in README.md ("Tokenization").
The pipeline is: normalize -> clean -> split into segments -> tokenize.
N-grams never cross a segment boundary.

Rules (v1):
  * Unicode NFKC normalization, lowercase, ligatures folded by NFKC.
  * Line-break hyphenation repaired: "represen-\\ntation" -> "representation".
  * Segment boundaries: sentence punctuation [.!?;:], blank lines, and
    math-like characters [= + \\ { } ^ _ $ | < > ~ * / #]. Commas, quotes and
    parentheses do NOT break n-grams; they are simply dropped.
  * Tokens: alphabetic words, optionally with internal hyphens/apostrophes
    ("state-of-the-art", "model's"). Digit runs become the placeholder <num>.
    Anything else is dropped (and is not a boundary unless listed above).
  * Optional citation stripping (on by default): parenthetical author-year
    citations "(Smith et al., 2020; Doe, 2019)" and numeric brackets "[3, 12]"
    are removed and replaced with a segment boundary.
  * Omission markers from the `omissions` config ("⟦table omitted⟧", "⟦math⟧", ...)
    are replaced with a segment boundary (v1.1).
  * URLs (http(s)://..., www....) and e-mail addresses are replaced with a
    segment boundary (v1.2).
  * v1.3 (fixes from the QA review, docs/qa.md): diacritics folded ("naïve" ->
    "naive"); decimals stay one number ("0.5" -> <num>); abbreviations e.g., i.e.,
    w.r.t., et al., Fig., Eq., Sec., Tab., vs., cf., ... do not end a segment
    (e.g. -> "eg"); heading lines with no lowercase letters are their own segment;
    parenthetical acronyms "(LLMs)" are boundaries; "state-of-the-\\nart" keeps
    its hyphen.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Iterator

TOKENIZER_VERSION = "v1.3"  # v1.1 omission markers; v1.2 URLs/emails; v1.3 QA fixes D1-D6 (docs/qa.md)

_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(\w)")
# A line-end hyphen inside an already-hyphenated compound is a real hyphen: "state-of-the-\nart".
_COMPOUND_BREAK = re.compile(r"((?:\w+-)+\w+)-\s*\n\s*(\w)")
# Heading lines: no lowercase letter, at least two capitals, short ("1 INTRODUCTION", "A.1 PROOFS").
_HEADING_LINE = re.compile(r"^(?=[^\n]*[A-Z][^\n]*[A-Z])[^a-z\n]{2,80}$", re.M)
# Parenthetical acronyms "(LLMs)", "(RL)", "(GPT-4)": dropping only the parentheses would
# create bigrams like "models llms", so the whole parenthetical becomes a boundary.
_PAREN_ACRONYM = re.compile(r"\(\s*[A-Z][\w-]*[A-Z][\w-]*\s*\)")
# Abbreviations whose periods must not end a segment (applied after lowercasing).
_ABBREV = [
    (re.compile(r"\be\.\s?g\.,?"), "eg"),
    (re.compile(r"\bi\.\s?e\.,?"), "ie"),
    (re.compile(r"\bw\.r\.t\."), "wrt"),
    (re.compile(r"\bet al\.,?"), "et al"),
    (re.compile(r"\b(figs?|eqs?|secs?|tabs?|vs|cf|resp|approx|refs?|thm|lem|alg|def|prop|app)\."), r"\1"),
]
_DECIMAL_POINT = re.compile(r"(?<=\d)\.(?=\d)")
_BLANK_LINE = re.compile(r"\n\s*\n")
# Placeholders inserted by the dataset's `omissions` config, e.g. "⟦equation omitted⟧",
# "⟦math⟧". They stand for removed non-prose and must never form or join n-grams.
_OMISSION_MARKER = re.compile(r"⟦[^⟧]{0,80}⟧")
# URLs and e-mail addresses (code links, footnotes, author blocks) are not prose.
_URL = re.compile(r"(?:https?://|www\.)\S+|\S+@\S+\.\w+")
_SEGMENT_BREAK = re.compile(r"[.!?;:=+\\{}^_$|<>~*/#•·]")
# Parenthetical containing a 4-digit year (optionally with suffix letter) and
# something name-like, e.g. "(Vaswani et al., 2017)" or "(see Doe 2019a; Roe, 2020)".
_CITE_PAREN = re.compile(r"\((?:[^()]{0,200}?(?:19|20)\d\d[a-z]?)(?:[^()]{0,200})\)")
_CITE_BRACKET = re.compile(r"\[\s*\d+(?:\s*[,–-]\s*\d+)*\s*\]")
_TOKEN = re.compile(r"[a-z]+(?:['’-][a-z]+)*|\d+(?:[.,]\d+)*")

BOUNDARY = "\n\n"


@dataclass(frozen=True)
class TokenizerConfig:
    strip_citations: bool = True


def fold_diacritics(text: str) -> str:
    """NFKC, then strip combining marks: "naïve" -> "naive"."""
    text = unicodedata.normalize("NFD", unicodedata.normalize("NFKC", text))
    return unicodedata.normalize("NFC", "".join(ch for ch in text if unicodedata.category(ch) != "Mn"))


def normalize(text: str) -> str:
    text = fold_diacritics(text)
    text = _COMPOUND_BREAK.sub(r"\1-\2", text)
    text = _HYPHEN_BREAK.sub(r"\1\2", text)
    # Case-sensitive rules run before lowercasing.
    text = _HEADING_LINE.sub(lambda m: BOUNDARY + m.group(0) + BOUNDARY, text)
    text = _PAREN_ACRONYM.sub(BOUNDARY, text)
    return text.lower()


def segments(text: str, cfg: TokenizerConfig = TokenizerConfig()) -> Iterator[str]:
    text = normalize(text)
    text = _OMISSION_MARKER.sub(BOUNDARY, text)
    text = _URL.sub(BOUNDARY, text)
    if cfg.strip_citations:
        text = _CITE_PAREN.sub(BOUNDARY, text)
        text = _CITE_BRACKET.sub(BOUNDARY, text)
    for pat, rep in _ABBREV:
        text = pat.sub(rep, text)
    text = _DECIMAL_POINT.sub("", text)
    text = _SEGMENT_BREAK.sub(BOUNDARY, text)
    for seg in _BLANK_LINE.split(text):
        if seg.strip():
            yield seg


def tokenize_segment(seg: str) -> list[str]:
    out = []
    for m in _TOKEN.finditer(seg):
        tok = m.group(0)
        out.append("<num>" if tok[0].isdigit() else tok.replace("’", "'"))
    return out


def tokenize(text: str, cfg: TokenizerConfig = TokenizerConfig()) -> list[list[str]]:
    """Return a list of token segments; n-grams are formed within each segment."""
    return [toks for seg in segments(text, cfg) if (toks := tokenize_segment(seg))]
