"""Removal of template statement sections (documented in README.md "Statement sections").

ICLR began requiring short administrative sections in later years (ethics and
reproducibility statements; from 2026 an LLM-usage disclosure). Their wording is
largely formulaic and dominated the 2024–2026 risers in the pilot QA review
(docs/qa.md), so by default they are cut before counting. Acknowledgments and
author-contribution sections are cut too: they are administrative prose at every
year, so cutting them keeps the comparison uniform.

A section starts at a heading line whose whole text (after an optional section
number) matches HEADING, case-insensitively. It ends at the next heading-like
line (a short line with no lowercase letters, or a bare section number such as
"A" or "A.1"), at an omission marker for the reference list, or after MAX_CHARS,
whichever comes first.
"""
from __future__ import annotations

import re

SECTIONS_VERSION = "v2"  # v2: ICLR 2027 "AI use statement" and AI-disclosure variants
MAX_CHARS = 5000

_NAMES = (
    r"(?:statement on )?(?:the\s+)?(?:use|usage) of (?:generative )?(?:ai(?: tools)?|large language models?|llms?)"
    r"(?:\s*\(llms?\))?(?: statement| disclosure)?"
    r"|(?:generative )?(?:ai|llms?|large language models?)[- ](?:usage|use|assistance)(?: statement| disclosure| declaration)?"
    r"|(?:generative )?ai disclosure"
    r"|llm statement"
    r"|reproducibility(?: statement| information)?"
    r"|ethics(?: statement)?|ethical (?:statement|considerations)"
    r"|broader impacts?(?: statement)?|impact statement"
    r"|acknowledge?ments?"
    r"|author contributions?"
)
HEADING = re.compile(r"^[ \t]*(?:[A-Z]?\d*(?:\.\d+)*\.?[ \t]+)?(?:" + _NAMES + r")[ \t]*:?[ \t]*$", re.I | re.M)
_NEXT_HEADING = re.compile(r"^(?:(?=[^\n]*[A-Z][^\n]*[A-Z])[^a-z\n]{2,80}|[A-Z]?\d*(?:\.\d+)*)$|⟦references omitted⟧", re.M)


def strip_statements(text: str) -> tuple[str, int]:
    """Return (text without statement sections, number of characters removed)."""
    out, pos, removed = [], 0, 0
    while (m := HEADING.search(text, pos)) is not None:
        out.append(text[pos : m.start()])
        body_start = m.end()
        nxt = _NEXT_HEADING.search(text, body_start + 1)
        end = min(nxt.start() if nxt else len(text), body_start + MAX_CHARS)
        removed += end - m.start()
        out.append("\n\n")
        pos = end
    out.append(text[pos:])
    return "".join(out), removed
