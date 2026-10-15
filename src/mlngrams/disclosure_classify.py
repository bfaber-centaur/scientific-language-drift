"""Negation-aware rule classifier for AI-use disclosures (rubric v1).

Replaces the withdrawn keyword classifier (negative result N13), which read
negated template lists ("We have not used generative AI tools for ... assist in
the writing of proofs") as claims of use. Here a disclosure is split into
clauses, each clause gets a polarity, and only task phrases in affirmative
clauses count. Categories follow results/disclosures/labels/rubric.md:
none, polish, drafting, coding, literature, other, ambiguous, plus the flag
writing_unspecified.

Pipeline (classifier v1, rules developed on the 60-statement dev set only):
  1. Sentences; sentences that only assert oversight, responsibility or
     authors' ownership ("All AI-assisted code was reviewed", "the ideas are the
     authors' own") are skipped: they describe checks, not uses.
  2. Clauses: split at ";", at "but / however / whereas / while / although /
     rather than", and before a negated subject ("..., and we did not use ...").
  3. Polarity: a clause is negative if it contains a negation cue (not, no,
     never, neither, nor, without, n't, "not applicable", "does not apply").
     Text after "except (for) / beyond / other than / apart from / besides /
     only" inside a negative clause is affirmative ("not used beyond polishing").
  4. Task items: affirmative clauses are cut at commas and " and "; very short
     items borrow the next item's object ("drafting and editing text").
     Each item is matched against the category lexicons below.
  5. Decision: categories found -> those categories. None found, but a
     global non-use statement or only negative clauses -> none. A use verb with
     no recognisable task -> ambiguous (abstain). writing_unspecified when a
     generic "writing" item is found without a polish or drafting cue in it.
"""
from __future__ import annotations

import re

CLASSIFIER_VERSION = "v2"  # v1 = commit 26e8539 (failed Gate 3); v2 rules developed on dev + round-1 test
CATEGORIES = ("none", "polish", "drafting", "coding", "literature", "other", "ambiguous")

_SENT = re.compile(r"(?<=[.!?])\)?\s+(?=[A-Z(\"“])|(?<=[a-z])\s+(?=We used )")
# Template meta text and parentheticals that carry a negation but no claim ("(with no direct editing)").
_META = re.compile(r"\((?:this section|this statement)[^)]*\)|this statement should not be more than[^.]*\.|see the iclr 2027 ai policy[^.]*\.", re.I)
_PAREN = re.compile(r"\([^()]{0,120}\)")
_OVERSIGHT = re.compile(
    r"\bresponsib|\baccountab|\b(?:reviewed|verified|checked|validated|tested|inspected|double-checked|re-derived|recomputed|traced)\b"
    r"|\b(?:are|remain|were|is) (?:entirely |solely |fully )?(?:the )?authors['’]? own\b|\bour own\b|\b(?:we|authors?)\b[^.,;]{0,30}\b(?:verify|review|check|validate|proofread)\b"
    r"|\bhuman (?:contributions|effort)|\bby humans\b|\bentirely (?:ours|human)\b"
    r"|\b(?:conceived|designed|developed|written|conducted|carried out|produced|made|determined|performed|set)\b[^.]{0,40}\bby (?:the |human )?authors\b"
    r"|^(?:the )?authors? (?:set|developed|designed|conceived|wrote|made|defined|conducted|retain|directed)",
    re.I,
)
_USE_VERB = re.compile(
    r"\b(?:used?|using|usage|employ\w*|utili[sz]\w*|leverag\w*|assist\w*|help\w*|support\w*|aid\w*|relied|rely|consult\w*|"
    r"generat\w*|draft\w*|provid\w*|suggest\w*|propos\w*|implement\w*|wr(?:ote|itten)|produc\w*|condens\w*|edit\w*|"
    r"developed|formulated|designed|interpreted|served?|perform\w*|contribut\w*)\b",
    re.I,
)
_NEG = re.compile(
    r"\b(?:not|never|n't)\b(?:\s+[\w-]+){0,3}?\s+(?:use|used|using|employ\w*|utili[sz]\w*|leverag\w*|rel(?:y|ied)|involv\w*|assist\w*|contribut\w*|appl(?:y|ied)|generat\w*|draft\w*|writ\w*|produc\w*|creat\w*|for|to|with|in|by|as)\b"
    r"|\bno\b|\bnone\b|\bneither\b|\bnor\b|\bnever\b|\bwithout (?!\w+ing\b)|not applicable|do(?:es)? not apply|\bn/a\b|\bnot (?:relevant|part of|involved)",
    re.I,
)
# Negations inside relative clauses modify a task, they do not deny use ("brainstorming that did not involve ...").
_REL_NEG = re.compile(r"\b(?:that|which|who)\s+(?:did|does|do|was|were|is|are|had|has|have)?\s*(?:not|never)\b[^,;]*", re.I)
_EXCEPT = re.compile(r"\b(?:except(?: for)?|beyond|other than|apart from|aside from|besides|only|solely|limited to|restricted to|confined to)\b", re.I)
_CLAUSE_SPLIT = re.compile(
    r";|\s*\b(?:but|however|whereas|while|although|rather than)\b\s*|(?=,\s*(?:and\s+|but\s+)?not\s+(?:with|for|to|in)\b)"
    r"|,?\s+and\s+(?=(?:all|every|each|the authors|we (?:have )?(?:reviewed|verified|checked|tested))\b)"
    r"|,?\s*(?:and\s+)?(?=\b(?:we|they|the authors|it|these tools|generative ai|ai(?: tools)?|llms?)\s+(?:have\s+|has\s+|did\s+|do\s+|does\s+|were\s+|was\s+)?(?:not|never)\b)",
    re.I,
)
_GLOBAL_NONE = re.compile(
    r"\bno (?:generative |large language model |gen-?ai |ai[- ]based )?(?:ai|llms?|large language models?|language models?|tools?)\b[^.]{0,60}\b(?:used|employed|involved|were|was)\b"
    r"|\b(?:did|do|have|has) not (?:use|used|employ|employed|rely on) (?:any )?(?:generative |gen-?ai )?(?:ai|llms?|large language models?|language models?|tools)\b(?![^.]{0,40}\b(?:to|for)\b)"
    r"|\bnot (?:been )?used (?:any )?(?:generative )?(?:ai|llms?)\b(?![^.]{0,40}\b(?:to|for)\b)"
    r"|\bwithout (?:the )?(?:use|aid|assistance) of (?:any )?(?:generative )?(?:ai|llms?|large language)",
    re.I,
)

_CODE_OBJ = r"(?:code|coding|codebase|script|scripts|software|program|programs|implementation|scaffold\w*|kernels?|functions?|pipelines?|harness\w*|tests?)"
LEX = {
    "coding": re.compile(
        r"\b" + _CODE_OBJ + r"\b|\bdebug\w*|\bimplement\w*|\bprogramm\w*|\bexperiment(?:s|al)? (?:infrastructure|automation|tracking|execution|management|pipeline|setup)"
        r"|\brun(?:ning)? (?:the )?experiments|\bexecut\w*|\bdata (?:processing|analysis|cleaning|conversion|generation|preprocessing|curation|pipeline|filtering|annotation|labell?ing)"
        r"|\bsynthetic (?:data|datasets?|samples|examples|tasks)|\bgenerat\w* (?:synthetic |the )?(?:data|datasets?|labels|responses|prompts|questions|samples|tasks)\b"
        r"|\b(?:clean\w*|reformat\w*|process\w*) (?:and \w+ )?(?:the )?(?:data|datasets?)\b|\banaly[sz]\w*(?: of)? (?:the )?(?:data|results|experiment\w*|logs|trajectories)|\bstatistic\w*"
        r"|\binterpret\w*|\bplot\w*|\b(?:result|results|experimental|statistical|data|quantitative) analys\w*|\bvisuali[sz]ation (?:code|scripts)|\bbaselines?\b|\bagentic|\bcoding agents?|\bjudges?\b|\bannotat\w*"
        r"|\bcomponents? of (?:the|our)|\bpart of (?:the|our) (?:method|pipeline|benchmark|framework|experiments?)|\bbenchmark construction|\bevaluation pipeline"
        r"|\bthematic data analysis|\bqualitative (?:data )?analysis|\barithmetic|\bcalculations?\b|\bnumerical (?:summaries|checks)",
        re.I,
    ),
    "literature": re.compile(
        r"\bliterature|\brelated work|\bprior work|\brelevant (?:papers|work|references|studies)|\bpapers? (?:search|discovery|retrieval)"
        r"|\b(?:search\w*|sourcing)(?:/searching)? (?:for )?(?:information|papers|references|relevant)|\bsourcing/searching|\bcandidate references|\bcitation discovery"
        r"|\bsummari[sz]\w* (?:existing |prior |related |the )?(?:literature|papers|work|methodologies)|\bresearch gaps?|\bdiscover\w* research topics|\bline of work|\bcitation search\w*|\bidentify\w*(?: and \w+)? (?:relevant )?references|\bprior (?:papers|art)",
        re.I,
    ),
    "drafting": re.compile(
        r"\bdraft(?:ing|ed)\b|(?<!the )(?<!initial )(?<!original )(?<!our )(?<!earlier )(?<!first )(?<!on )(?<!each )(?<!every )(?<!of )(?<!their )(?<!a )(?<!paper )(?<!manuscript )\bdrafts?\b(?! (?:were|was|versions?)\b)|\brewrit\w*|\brestructur\w*|\breorgani[sz]\w*|\bcondens\w*|(?<![-\w])wr(?:ite|iting|ote|itten) (?:up |the |parts? of |portions? of |sections?|paragraphs?|text|prose|initial|an? |our )"
        r"|\binitial (?:text|skeleton)|\bgenerat\w* (?:the )?(?:text|prose|paragraphs?|sections?|captions?)\b|\bproduc\w* (?:initial )?text"
        r"|\b(?:paragraph|manuscript|paper) structure\b|\bstructure of (?:the )?(?:manuscript|paper|paragraphs)",
        re.I,
    ),
    "polish": re.compile(
        r"\bgrammar|\bgrammatical|\bspell\w*|\btypo\w*|\bpunctuation|\bproofread\w*|\bpolish\w*|\bwording|\breword\w*|\bphras\w*|\brephras\w*|\bparaphras\w*"
        r"|\bproof[- ]?read\w*|\bfluen\w*|\breadab\w*|\bclarity|\bconcis\w*|(?<![-\w])styl(?:e|istic|istically)\b|\btone\b|\blanguage (?:editing|refinement|improvement|revision|correction|check\w*|polish\w*|assistance|quality|use|edits)"
        r"|\benglish|\bcopy-?edit\w*|\bedit\w* (?:the |our |of the |of our |for )?(?:text|manuscript|paper|prose|writing|language|sentences?|draft|readability|clarity)"
        r"|\b(?:improv\w*|refin\w*|revis\w*|correct\w*) (?:the )?(?:text|writing|language|manuscript|prose|sentences?|presentation|exposition|wording)"
        r"|\btranslat\w*|\bterminology|\bsentence (?:structure|level)|\btext (?:editing|refinement|polishing|revision|improvement)|\bmanuscript (?:editing|refinement|polishing)"
        r"|\b(?:editing|edits) (?:and|or) (?:polish\w*|proofread\w*)|\blanguage editing|^\W*(?:text |manuscript |prose |paper )?(?:editing|edits)\W*$",
        re.I,
    ),
    "other": re.compile(
        r"\bideat\w*|\bresearch ideas?|\bbrainstorm\w*|\bhypothes\w*|\btheor\w*|\bproofs?\b|\bproving|\bmathematical|\bderivations?|\bconceptual|\bframeworks?\b"
        r"|\bmethodolog\w*|\bexperiment(?:al)? design|\bdesign\w* (?:or provide feedback on |of )?(?:the )?(?:research |experiments?|methodolog|protocol|study)|\bfeedback|\bcritique|\bpeer[- ]review"
        r"|\bl ?a ?tex|\bformat\w*|\bbibliograph\w*|\bbibtex|\breferences?\b|\bcitations?\b|\bfigures?\b|\btables?\b|\billustrat\w*|\bdiagrams?|\bimages?\b|\btitles?\b|\bkeywords?"
        r"|\bconsisten\w*|\bfact|\boutline|\btemplate|\bparameters|\bhyperparameters|\bconfigurations?|\bablations?|\bpresentation of (?:the )?(?:\w+ )?(?:results|figures|data|experiments|methods?|research)|\bdocumentation|\borgani[sz]ation|\bstructure\b"
        r"|\bsurvey questions|\binterview|\btranscri\w*|\bartifacts?\b|\bexposition|\bpage (?:count|limit)|\bsubmission requirements|\bresearch (?:directions?|questions?)",
        re.I,
    ),
}
_WRITING = re.compile(r"\bwriting\b|\bwriting assistan\w*|\bmanuscript (?:preparation|revision)|\brevis\w* (?:of )?the manuscript|\bpreparation of (?:the|this) (?:manuscript|paper)|\bpaper writing|\bmanuscript writing|\bwriting aid", re.I)
_TEXTY = re.compile(r"\b(?:text|prose|paper|manuscript|sections?|paragraphs?|abstract|captions?|introduction|appendix|exposition|passages?|statements?|skeleton|sentences?)\b", re.I)
_CODEY = re.compile(r"\b" + _CODE_OBJ + r"\b|\bexperiments?\b|\brules?\b|\bcriteria\b|\bprotocols?\b|\bquestions?\b|\bprompts?\b|\bdata\b", re.I)


_RELEVANT = re.compile(
    r"\b(?:ai|a\.i\.|llms?|language models?|generative|chatgpt|gpt[-\w.]*|claude|opus|sonnet|gemini|codex|copilot|cursor|deepseek|qwen|kimi|glm|grok|llama|tools?|assistants?|agents?|models?)\b"
    r"|\b(?:they|them|these|it|such|assisted)\b|:",
    re.I,
)
# "other" cues that stand on their own even inside a coding or literature item.
_OTHER_STRONG = re.compile(r"\bideat|\bbrainstorm|\bhypothes|\btheor|\bproofs?\b|\bmathematical|\bfeedback|\bla ?tex|\bbibliograph|\btitles?\b|\bkeywords?|\bexperiment(?:al)? design|\bdesign\w* (?:or provide feedback on )?(?:the )?(?:research|experiments?)", re.I)


def _items(clause: str) -> list[str]:
    parts = [p.strip() for p in re.split(r",|\band\b|\bas well as\b|\(|\)|:|•|\(\w\)|\b[ivx]+\)", clause) if p.strip()]
    out = []
    for i, p in enumerate(parts):
        if len(p.split()) <= 2 and i + 1 < len(parts):
            nxt = parts[i + 1].split()
            p = p + " " + " ".join(nxt[1:] if len(nxt) > 1 else nxt)
        out.append(p)
    return out


def _polarity_text(c: str) -> str:
    """Clause text used for the negation test: parentheticals and relative-clause negations removed."""
    return _REL_NEG.sub(" ", _PAREN.sub(" ", c))


def _clauses(sentence: str) -> list[tuple[str, bool]]:
    """(clause, affirmative) pairs; negative clauses with an exception keep the excepted part."""
    out = []
    for c in _CLAUSE_SPLIT.split(sentence):
        if not c or not c.strip():
            continue
        pt = _polarity_text(c)
        n = _NEG.search(pt)
        if n:
            m = _EXCEPT.search(c)
            if m and m.start() > n.start():
                out.append((c[: m.start()], False))
                out.append(("used for " + c[m.end():], True))  # the excepted part is a use claim
            else:
                out.append((c, False))
        else:
            out.append((c, True))
    return out


_USE_BYPASS = re.compile(
    r"\b(?:we|i)\s+(?:also\s+)?(?:used?|employ\w*|utili[sz]ed|leverag\w*)\b|\b(?:were|was|are|is)\s+(?:also\s+|primarily\s+|mainly\s+|only\s+)?used\b|\bassisted (?:with|in)\b",
    re.I,
)
_AI_ANY = re.compile(r"\b(?:ai|llms?|language models?|generative|chatgpt|gpt[-\w.]*|claude|gemini|codex|copilot|assistants?|agents?|tools?)\b", re.I)
_EDIT_ONLY = re.compile(r"\b(?:edit\w*|revis\w*)\b", re.I)
_POLISH_EXPLICIT = re.compile(r"grammar|polish|readab|clarity|proof[- ]?read|language|wording|spell|typo|fluen|concis|phras|translat|style", re.I)


def _item_cats(item: str) -> set[str]:
    cats = {k for k, pat in LEX.items() if pat.search(item)}
    if "drafting" in cats and _CODEY.search(item) and not _TEXTY.search(item):
        cats.discard("drafting")
        cats.add("coding")
    if "drafting" in cats and re.search(r"\bproofs?\b|\bderivations?|\btheorems?|\bla ?tex\b|\bl ?a ?tex\b|\ba tex\b|\bstructure\b|\boutline", item, re.I) and not re.search(r"\b(?:text|prose|paper|manuscript|sections?|paragraphs?)\b", item, re.I):
        cats.discard("drafting")
        cats.add("other")
    if "drafting" in cats and re.search(r"\bsentences?\b", item, re.I) and re.search(r"rewrit|rephras|reword", item, re.I):
        cats.discard("drafting")
        cats.add("polish")
    if "coding" in cats and "other" in cats and re.search(r"\bfigures?\b|\btables?\b|\bplots?\b", item) and re.search(r"\b" + _CODE_OBJ + r"\b|\bplot", item):
        cats.discard("other")
    if "polish" in cats and "other" in cats and re.fullmatch(r".*\b(?:presentation|structure|organi[sz]ation)\b.*", item) and not re.search(r"figure|table|latex|format|reference", item, re.I):
        cats.discard("other")
    if "other" in cats and cats & {"coding", "literature"} and not _OTHER_STRONG.search(item):
        cats.discard("other")
    return cats


def classify(text: str) -> dict:
    """Return {"labels": set of categories, "writing_unspecified": bool, "evidence": [(category, item)]}."""
    text = _META.sub(" ", text or "")
    from mlngrams.disclosures import looks_like_bibliography

    if not _AI_ANY.search(text) or looks_like_bibliography(text[:600]):  # not a disclosure (extraction residue such as a reference list)
        return {"labels": {"ambiguous"}, "writing_unspecified": False, "evidence": []}
    labels: set[str] = set()
    evidence = []
    writing_unspec = False
    any_use = any_neg = global_none = False
    for sent in _SENT.split(text):
        if _GLOBAL_NONE.search(sent):
            global_none = True
        if not _RELEVANT.search(sent):
            continue
        for clause, affirmative in _clauses(sent):
            if _OVERSIGHT.search(clause) and not _USE_BYPASS.search(clause):
                continue
            if not affirmative:
                any_neg = True
                continue
            if not _USE_VERB.search(clause) and not labels and not re.search(r"\bfor\b|:", clause):
                continue
            found_here = False
            clause_cats: set[str] = set()
            polish_items = []
            for item in _items(clause):
                cats = _item_cats(item)
                if not cats & {"polish", "drafting"} and _WRITING.search(item) and not re.search(r"proofs?|code|script", item, re.I):
                    writing_unspec = True
                    found_here = True
                if "polish" in cats:
                    polish_items.append(item)
                if cats:
                    found_here = True
                    clause_cats |= cats
                    evidence += [(k, item.strip()[:80]) for k in sorted(cats)]
            # Rubric rule 1: "drafting and editing" is drafting; editing adds polish only with explicit polish words.
            if "drafting" in clause_cats and polish_items and all(_EDIT_ONLY.search(i) and not _POLISH_EXPLICIT.search(i) for i in polish_items):
                clause_cats.discard("polish")
            labels |= clause_cats
            if _USE_VERB.search(clause) and _AI_ANY.search(clause):
                any_use = True
    # The flag matters only where it is the sole writing claim (no polish or drafting found).
    writing_unspec = writing_unspec and not labels & {"polish", "drafting"}
    if labels:
        return {"labels": labels, "writing_unspecified": writing_unspec, "evidence": evidence}
    if writing_unspec:
        return {"labels": set(), "writing_unspecified": True, "evidence": evidence}
    if global_none or (any_neg and not any_use):
        return {"labels": {"none"}, "writing_unspecified": False, "evidence": [("none", "")]}
    return {"labels": {"ambiguous"}, "writing_unspecified": False, "evidence": []}
