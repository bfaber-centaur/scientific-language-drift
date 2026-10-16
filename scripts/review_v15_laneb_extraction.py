"""Lane D (v1.5 review): audit of Lane B's recovered disclosures (extractor v1).

Usage: python3 scripts/disclosures/extract.py --out <dir>    (Lane B's script, branch claude/project-thread-955ai1)
       python3 scripts/review_v15_laneb_extraction.py <dir>/iclr2027.parquet

Checks on the clean tier: bibliography entries inside a disclosure (any one citation-entry pattern, stricter
than Lane B's >= 3-line flag), disclosures whose last three sentences mention neither AI nor authorship
(overrun into following sections), sentence-polarity cues that misfire (the ICLR instruction sentence
"(This section is required and does not count toward the page limit.)" glued to the next sentence because
the split needs [.!?] directly before the space; "without" as the only negation cue), and reconstruction of
three trigram counts. Prints aggregates and short (<= 200 char) tails with paper ids; writes nothing.
"""
import re
import sys

import pandas as pd

sys.path.insert(0, "src")
from mlngrams.tokenize import tokenize  # noqa: E402

BIB = re.compile(r"arXiv:\d|arXiv preprint|In Proceedings|In Advances in|\bdoi: ?10\.|URL https?://(?:arxiv|proceedings|openreview|doi)"
                 r"|Curran Associates|\b(?:19|20)\d\d\. URL|pp\. \d+[–-]\d+")
AI = re.compile(r"\b(ai|llms?|language models?|generative|chatgpt|gpt|claude|gemini|copilot|assist|tools?)\b", re.I)
NEG = re.compile(r"\b(?:not|never|no|none|neither|nor|without)\b|\bn't\b|not applicable|refrain|did not|have not|were not|was not", re.I)


def offtopic_tail(t: str) -> int:
    s = re.split(r"(?<=[.!?])\s+", t)
    if len(s) < 4:
        return 0
    return sum(not AI.search(x) and not re.search(r"author|responsib|review|verif", x, re.I) for x in s[-3:])


def main() -> None:
    d = pd.read_parquet(sys.argv[1])
    f = d[(d.found == True) & (d.tier == "clean")]  # noqa: E712
    print("clean", len(f))
    b = f.text_clean.str.count(BIB)
    print("bibliography entry inside clean disclosure: %.4f" % (b > 0).mean(), "| ending at references: %.4f"
          % (b[f.end_reason == "references"] > 0).mean())
    off = f.text_clean.apply(offtopic_tail)
    print("last three sentences off-topic: %.4f (%d)" % ((off == 3).mean(), (off == 3).sum()))
    for _, x in f[off == 3].sample(8, random_state=15).iterrows():
        print("  --", x.doc_id, x.end_reason, "|", x.text_clean[-200:])
    instr = f.text_clean.str.contains("this section is required and does not count", case=False)
    print("ICLR instruction sentence left in: %d (%.4f)" % (instr.sum(), instr.mean()))
    sents = [s for t in f.text_clean for s in re.split(r"(?<=[.!?])\s+", t)]
    neg = [s for s in sents if NEG.search(s)]
    wo = [s for s in neg if re.search(r"\bwithout\b", s, re.I) and not re.search(r"\b(?:not|never|no|n't)\b", s, re.I)]
    print("sentences", len(sents), "non-use", len(neg), "only cue 'without'", len(wo))
    for g in [("generative", "ai", "tools"), ("take", "full", "responsibility"), ("by", "the", "authors")]:
        c = dc = 0
        for t in f.text_clean:
            k = sum(tuple(s[i:i + 3]) == g for s in tokenize(t) for i in range(len(s) - 2))
            c, dc = c + k, dc + (k > 0)
        print(" ".join(g), c, dc)


if __name__ == "__main__":
    main()
