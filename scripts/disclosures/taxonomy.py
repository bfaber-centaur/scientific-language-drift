"""Rhetorical moves and named tools in AI-use disclosures (Lane B, Gate 2).

Usage: python3 scripts/disclosures/taxonomy.py [--data data/disclosures/iclr2027.parquet]

A small, descriptive taxonomy of what disclosure sentences do. Each sentence of a
clean-tier disclosure is tagged with every move whose pattern it matches (moves
are not exclusive). The patterns are deliberately simple and listed here; their
precision was checked by reading 10 matched sentences per move (docs/ai-disclosures.md).

Writes results/disclosures/moves.csv (papers and sentences per move, share of
move sentences that are template-covered) and results/disclosures/tools_named.csv
(papers naming each tool or vendor), plus one short excerpt id per move in
results/disclosures/move_examples.csv (ids and <= 25-word excerpts only).
"""
from __future__ import annotations

import argparse
import os
import random
import re
import sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))

import pandas as pd  # noqa: E402

OUT = os.path.join(ROOT, "results", "disclosures")
SEED = 20271015

MOVES = {
    "use_declaration": r"\b(?:we|i|authors?)\s+(?:have\s+)?(?:also\s+)?(?:used|use|employed|utili[sz]ed|leveraged|relied on)\b|\b(?:were|was|are|is|have been)\s+(?:primarily\s+|mainly\s+|also\s+|only\s+)?(?:used|employed|utili[sz]ed)\b|\bassisted (?:with|in)\b|\bhelped (?:with|to)\b",
    "nonuse_declaration": r"\b(?:have|has|did|do|were|was)\s+not\s+(?:been\s+)?(?:use|used|employ|employed|rely|involve|involved|contribute)|\bno\s+(?:generative\s+)?(?:ai|llms?|large language)|\bnot\s+used\b|\bwithout (?:the )?(?:use|aid|assistance) of\b",
    "not_applicable": r"not applicable|\bn/a\b|do(?:es)? not apply",
    "scope_limit": r"\b(?:only|solely|exclusively|limited to|restricted to|confined to|strictly)\b",
    "human_oversight": r"\b(?:reviewed|verified|checked|validated|inspected|double-checked|proofread|tested)\b[^.]{0,60}\b(?:by the authors|authors|manually|carefully|all)\b|\b(?:we|authors)\s+(?:have\s+)?(?:carefully\s+|manually\s+)?(?:reviewed|verified|checked|validated)\b",
    "responsibility": r"\bresponsib(?:le|ility)\b|\baccountab",
    "author_ownership": r"\b(?:all|the)\s+(?:core\s+|key\s+|scientific\s+|research\s+)?(?:ideas|contributions|conclusions|claims|research questions)\b[^.]{0,80}\b(?:authors|our own|human)\b|\bauthors'? own\b|\bwritten by the authors\b|\b(?:designed|conceived|conducted)\s+(?:entirely\s+)?by the authors\b",
    "tool_named": r"\b(?:chatgpt|gpt-?\d|openai|claude|anthropic|gemini|copilot|codex|cursor|grammarly|deepseek|qwen|llama|mistral|perplexity|deepl|writefull|overleaf|o\d\b|kimi|grok)\b",
    "ai_as_subject": r"\b(?:subject|object) of (?:study|evaluation|this work|our study)\b|\bevaluated (?:models|llms)\b|\bas part of (?:the|our) (?:method|pipeline|experiments)\b",
    "placement_meta": r"does not count toward|not count(?:ed)? towards? the page limit|this section is required|required by (?:the )?iclr|iclr 2027 (?:ai )?policy",
}
TOOLS = {
    "ChatGPT / GPT / OpenAI": r"\b(?:chatgpt|gpt-?\d[\w.-]*|openai|o[134](?:-mini)?)\b",
    "Claude / Anthropic": r"\b(?:claude|anthropic)\b",
    "Gemini / Google": r"\b(?:gemini|bard)\b",
    "GitHub Copilot": r"\bcopilot\b",
    "Codex": r"\bcodex\b",
    "Cursor": r"\bcursor\b",
    "Grammarly": r"\bgrammarly\b",
    "DeepSeek": r"\bdeepseek\b",
    "Qwen": r"\bqwen\b",
    "DeepL": r"\bdeepl\b",
    "Perplexity": r"\bperplexity\b",
    "Writefull / Overleaf AI": r"\b(?:writefull|overleaf)\b",
    "Grok": r"\bgrok\b",
    "Kimi": r"\bkimi\b",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=os.path.join(ROOT, "data", "disclosures", "iclr2027.parquet"))
    args = ap.parse_args()
    df = pd.read_parquet(args.data)
    df = df[(df.found == True) & (df.tier == "clean")].reset_index(drop=True)  # noqa: E712
    N = len(df)
    pats = {k: re.compile(v, re.I) for k, v in MOVES.items()}
    rows = {k: {"papers": set(), "sentences": 0} for k in MOVES}
    examples = {k: [] for k in MOVES}
    for doc, text in zip(df.doc_id, df.text_clean):
        for sent in re.split(r"(?<=[.!?])\s+", text):
            for k, p in pats.items():
                if p.search(sent):
                    rows[k]["papers"].add(doc)
                    rows[k]["sentences"] += 1
                    if len(examples[k]) < 400:
                        examples[k].append((doc, sent))
    out = [{"move": k, "papers": len(v["papers"]), "paper_pct": round(100 * len(v["papers"]) / N, 1), "sentences": v["sentences"]}
           for k, v in rows.items()]
    pd.DataFrame(out).to_csv(os.path.join(OUT, "moves.csv"), index=False)
    rng = random.Random(SEED)
    ex = []
    for k, lst in examples.items():
        for doc, sent in rng.sample(lst, min(10, len(lst))):
            words = sent.split()
            ex.append({"move": k, "doc_id": doc, "excerpt": " ".join(words[:25]) + (" ..." if len(words) > 25 else "")})
    # Excerpts are for the precision check only; the committed file keeps 2 per move.
    exdf = pd.DataFrame(ex)
    exdf.to_csv(os.path.join(os.path.dirname(args.data), "move_examples_check.csv"), index=False)
    exdf.groupby("move").head(2).to_csv(os.path.join(OUT, "move_examples.csv"), index=False)
    tool_rows = []
    for name, p in TOOLS.items():
        hits = df.text_clean.str.contains(p, case=False, regex=True)
        tool_rows.append({"tool": name, "papers": int(hits.sum()), "paper_pct": round(100 * hits.mean(), 2)})
    anyt = df.text_clean.str.contains("|".join(TOOLS.values()), case=False, regex=True)
    tool_rows.append({"tool": "any named tool", "papers": int(anyt.sum()), "paper_pct": round(100 * anyt.mean(), 2)})
    pd.DataFrame(tool_rows).to_csv(os.path.join(OUT, "tools_named.csv"), index=False)
    print(pd.DataFrame(out).to_string(), "\n", pd.DataFrame(tool_rows).to_string())


if __name__ == "__main__":
    main()
