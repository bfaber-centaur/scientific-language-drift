"""Recovery of AI-use disclosure sections (ICLR 2027 "AI use statement").

Statement removal (mlngrams.sections) cuts these sections so they cannot
contaminate body n-grams. This module does the opposite: it locates the
section and returns its text, so the disclosures can be studied as their own
corpus (docs/ai-disclosures.md).

Rules (extractor v1), applied to text from the `omissions` config:
  * A disclosure starts at a heading that names AI use: a line that is only a
    heading ("AI USE STATEMENT", "4.2 Use of Large Language Models (LLMs):"),
    or a run-in heading that starts a line and is followed by text on the same
    line ("AI Use Statement. Generative AI tools were ..."). A heading must
    contain an AI term (AI, LLM, large language model, generative, ChatGPT,
    ...) and a use term (use, usage, statement, disclosure, declaration,
    assistance, ...), be at most 12 words, and contain no finite-verb clue
    ("were", "we", "is", ...), so prose sentences mentioning AI never match.
  * It ends at the first of: the next heading-like line (all-caps short line,
    a bare section number, or a known statement heading in any case, whole-line
    or run-in), a run-in statement heading after a sentence end on the same line
    ("... for the paper. Ethics Statement. We ..."), an omission marker for the
    reference list, or MAX_CHARS.
  * When several headings match, the first one with a non-empty body is used;
    the number of candidates is reported so duplicates can be audited.
The end reason is recorded for every disclosure ("heading", "inline_heading",
"references", "max_chars", "end_of_text") because boundary errors are the main
risk: text from a following ethics or reproducibility statement leaking in.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

EXTRACTOR_VERSION = "v1"
MAX_CHARS = 4000

_AI = r"(?:a\.?i\.?|artificial intelligence(?:\s*\(ai\))?|gen(?:erative)?[- ]?ai|generative|llms?|large[- ]language[- ]models?|language models?|chatgpt|ai[- ]assist\w*)"
_USE = r"(?:use|usage|statement|disclosures?|declaration|assistance|assistants?)"
_NUM = r"(?:(?:[A-Z]|\d+)(?:\.\d+)*\.?[ \t]+)?"
_VERB_CLUE = re.compile(r"\b(?:were|was|is|are|we|our|i|has|have|did|this|these|used to|in this)\b", re.I)

_LINE = re.compile(r"^[^\n]*$", re.M)
_NUM_PREFIX = re.compile(r"^[ \t]*" + _NUM)
# Run-in heading: heading words, then "." or ":" and text ("AI Use Statement. Generative ...").
_RUN_IN = re.compile(r"^(?P<h>[A-Z(][^\n.:]{2,110}?)[ \t]*[:.][ \t]+(?P<rest>\S[^\n]*)$")
_HAS_AI = re.compile(r"\b" + _AI + r"\b", re.I)
_HAS_USE = re.compile(r"\b" + _USE + r"\b", re.I)

_STATEMENT_NAMES = (
    r"ethics(?: statement)?|ethical (?:statement|considerations)|reproducibility(?: statement)?"
    r"|acknowledge?ments?|author contributions?|broader impacts?(?: statement)?|impact statement"
    r"|limitations?|references|bibliography|appendix|appendices|funding|conflicts? of interest"
    r"|code of ethics|declaration of competing interests?"
)
_NEXT_HEADING = re.compile(
    r"^(?:(?=[^\n]*[A-Z][^\n]*[A-Z])[^a-z\n]{2,80}|[A-Z]?\d*(?:\.\d+)*)$"  # all-caps line / bare number
    r"|^[ \t]*" + _NUM + r"(?:" + _STATEMENT_NAMES + r")[ \t]*[:.]?[ \t]*$"  # known heading, any case
    r"|⟦references omitted⟧",
    re.M | re.I,
)
# Run-in statement heading: at line start, or after a sentence end on the same line.
_INLINE_NEXT = re.compile(
    r"(?:^|(?<=[.!?)])[ \t]+)(?-i:(?=[A-Z]))(?:" + _STATEMENT_NAMES + r")(?: statement)?[ \t]*[:.][ \t]+(?-i:[A-Z])",
    re.M | re.I,
)


@dataclass(frozen=True)
class Disclosure:
    heading: str
    form: str  # "line", "run_in", "heading_after" or "headless" (see extract)
    text: str
    start: int  # offset of the heading in the source text
    body_start: int
    end: int
    end_reason: str
    n_candidates: int


def _is_ai_heading(h: str) -> bool:
    words = h.split()
    if not (1 <= len(words) <= 12) or not (h[0].isupper() or h[0] == "("):
        return False
    if not (_HAS_AI.search(h) and _HAS_USE.search(h)):
        return False
    # Prose clue words disqualify, except inside all-caps headings ("STATEMENT ON THE USE OF AI").
    if _VERB_CLUE.search(h) and re.search(r"[a-z]", h):
        return False
    return True


_FUNCTION_WORDS = {"of", "the", "on", "and", "for", "in", "by", "a", "an", "to"}
# A heading phrase used without punctuation before the text: "AI use statement We used ...".
_BARE_RUN_IN = re.compile(r"^(?P<h>(?:ai|llm|generative ai)[- ]use statement|ai usage statement|ai disclosure)[ \t]+(?P<rest>[A-Z][^\n]*)$", re.I)
# Openers of a disclosure whose heading was lost in extraction (template opener and common variants).
_OPENER = re.compile(
    r"^(?:In this (?:work|paper|submission|study|manuscript),? (?:we|the authors) (?:have )?(?:used|use|did not use|have not used|do not use)"
    r" (?:generative ai|ai|llms?|large language models?)"
    r"|(?:No )?(?:generative )?ai(?:-based)? (?:tools|assistants|models|systems)(?: \(llms?\))? (?:were|was|have been) (?:used|not used)"
    r"|(?:Large language models|LLMs)(?: \(llms?\))? (?:were|was|have been|are) used to)",
    re.I,
)
_DISCLOSURE_CLUE = re.compile(r"responsib|polish|proofread|grammar|readability|disclos|reviewed all|verified|writing|editing", re.I)


def candidates(text: str) -> list[tuple[int, int, str, str]]:
    """(heading start, body start, heading text, form) for every AI-use heading."""
    out = []
    for m in _LINE.finditer(text):
        line = m.group(0)
        head = line[:160]
        if not _HAS_AI.search(head):
            continue
        pre = _NUM_PREFIX.match(line)
        off = pre.end() if pre else 0
        body = line[off:].rstrip()
        whole = body.rstrip(" \t:.").strip()
        if whole and len(whole) <= 110 and "." not in whole and ":" not in whole and _is_ai_heading(whole):
            out.append((m.start() + off, m.end(), whole, "line"))
            continue
        r = _RUN_IN.match(body[:160]) or _BARE_RUN_IN.match(body[:160])
        if not r:
            continue
        h = r.group("h").strip()
        if not _is_ai_heading(h) or not re.search(r"(?i)statement|disclosure|declaration|usage|\buse\b|assistance", h):
            continue
        # A run-in heading's words are capitalized or function words ("AI use statement" allowed).
        lower = sum(w[0].islower() for w in h.split() if w.lower() not in _FUNCTION_WORDS)
        if lower > 2 or (lower == 2 and not re.search(r"(?i)(statement|disclosure|declaration)$", h)):
            continue
        out.append((m.start() + off, m.start() + off + r.start("rest"), h, "run_in"))
    return out


def _end_of(text: str, body_start: int) -> tuple[int, str]:
    limit = min(len(text), body_start + MAX_CHARS)
    best, reason = limit, ("max_chars" if limit < len(text) else "end_of_text")
    m = _NEXT_HEADING.search(text, body_start + 1, limit)
    if m:
        g = m.group(0)
        best, reason = m.start(), ("references" if g.startswith("⟦") else "heading" if g.strip() else "blank_line")
    m2 = _INLINE_NEXT.search(text, body_start + 1, best)
    if m2:
        best, reason = m2.start(), "inline_heading"
    return best, reason


def _block_before(text: str, pos: int) -> tuple[int, str]:
    """Text between the previous heading-like line and pos, skipping heading lines right above pos."""
    while True:
        prev_nl = text.rfind("\n", 0, max(0, pos - 1))
        last = text[prev_nl + 1 : pos].strip()
        if prev_nl < 0 or not (last == "" or re.fullmatch(r"[A-Z]?\d*(?:\.\d+)*|[^a-z]{1,80}", last)):
            break
        pos = prev_nl + 1
    window_start = max(0, pos - MAX_CHARS)
    starts = [window_start] + [h.end() for h in _NEXT_HEADING.finditer(text, window_start, pos) if h.group(0).strip()]
    s = max(starts)
    return s, text[s:pos].strip()


def extract(text: str) -> Disclosure | None:
    """Return the AI-use disclosure section of a paper, or None if none is found.

    Forms: "line" / "run_in" (heading then text); "heading_after" (the heading is
    followed directly by another heading, and the disclosure text sits just
    above it, a PDF reading-order inversion); "headless" (no heading survived
    extraction; a paragraph opens with a disclosure formula and contains a
    disclosure clue word). The last two are flagged so they can be excluded.
    """
    text = text or ""
    cands = candidates(text)
    for start, body_start, h, form in cands:
        end, reason = _end_of(text, body_start)
        body = text[body_start:end].strip()
        if body:
            return Disclosure(h, form, body, start, body_start, end, reason, len(cands))
    for start, body_start, h, form in cands:
        bstart, body = _block_before(text, start)
        if body and _HAS_AI.search(body) and _DISCLOSURE_CLUE.search(body) and len(body) < MAX_CHARS:
            return Disclosure(h, "heading_after", body, start, bstart, start, "heading_after", len(cands))
    for m in _LINE.finditer(text):
        line = m.group(0).lstrip()
        if _OPENER.match(line):
            # Paragraph start: previous line is blank, a bare number, a heading, or ends a sentence.
            prev = text[max(0, m.start() - 200) : m.start()].rstrip("\n").rsplit("\n", 1)[-1].strip()
            if prev and not (re.fullmatch(r"[A-Z]?\d*(?:\.\d+)*", prev) or not re.search(r"[a-z]", prev) or prev.endswith((".", ":"))):
                continue
            end, reason = _end_of(text, m.start())
            body = text[m.start() : end].strip()
            if _DISCLOSURE_CLUE.search(body):
                return Disclosure("", "headless", body, m.start(), m.start(), end, reason, 0)
    return None


_BIB_LINE = re.compile(r"(?:arXiv:\d|arXiv preprint|In Proceedings|\bdoi:|, (?:19|20)\d\d\.\s*$)", re.M)


def looks_like_bibliography(body: str) -> bool:
    """True when the section ran into an un-omitted reference list (extraction residue)."""
    return len(_BIB_LINE.findall(body)) >= 3


_HYPHEN_BREAK = re.compile(r"(\w)-\s*\n\s*(?=[a-z])")


def clean(body: str) -> str:
    """Join PDF line breaks for reading and phrase analysis ("dis-\\ncussions" -> "discussions")."""
    body = _HYPHEN_BREAK.sub(r"\1", body)
    return re.sub(r"\s+", " ", body).strip()
