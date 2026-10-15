"""Lane D (V2): score the machine labels against Bobby's hand labels.

Usage:
    python3 scripts/v2/score_labels.py <dir of labels/*.json exported from the labelling page>

Writes results/v2/disclosures/labelling/human_labels.csv (item, stance, uses, note length; no text) and
results/v2/disclosures/labelling/agreement.csv:
  * group agreement (none / polish_only / drafting / other_use / unknown) for classifier v2 vs human,
    and for the V1.5 Claude coder-1 labels vs human on part A (the owed human spot check)
  * drafting and polish_only precision / recall of classifier v2 against the human labels, with Wilson CIs
  * stance agreement: the V2 sentence-stance rules (paper level) vs the human stance
"""
from __future__ import annotations

import glob
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "disclosures"))

import pandas as pd  # noqa: E402

from eval_groups import group  # noqa: E402
from evaluate import wilson  # noqa: E402

OUT = os.path.join(ROOT, "results", "v2", "disclosures", "labelling")
STANCE_MAP = {"use_only": "use", "use_and_denial": "mixed", "denial_only": "deny", "placeholder_only": "noclaim",
              "hypothetical_only": "noclaim", "no_claim": "noclaim"}


def human_group(stance, uses):
    if stance == "deny":
        return "none"
    if stance in ("noclaim", "notdisc") or not stance:
        return "unknown"
    u = set(uses or []) - {"unclear"}
    return group(u) if u else "unknown"


def main():
    rows = []
    for f in glob.glob(os.path.join(sys.argv[1], "**", "*.json"), recursive=True):
        j = json.load(open(f))
        d = j.get("data", j)
        rows.append({"item": os.path.basename(f)[:-5], "stance": d.get("stance"), "uses": ";".join(sorted(d.get("uses") or [])),
                     "note_chars": len(d.get("note") or "")})
    h = pd.DataFrame(rows)
    s = pd.read_csv(os.path.join(OUT, "sample.csv"))
    m = s.merge(h, on="item", how="inner")
    m["human_group"] = [human_group(a, (b or "").split(";") if isinstance(b, str) and b else []) for a, b in zip(m.stance, m.uses)]
    m[["item", "part", "cohort", "doc_id", "stance", "uses", "note_chars", "human_group"]].to_csv(os.path.join(OUT, "human_labels.csv"), index=False)
    out = []
    for name, sel in (("all statements (A-C)", m[m.part != "D"]), ("A: ICLR 2027 test2", m[m.part == "A"]),
                      ("B: ICLR 2026", m[m.part == "B"]), ("C: COLM/ICML 2026", m[m.part == "C"])):
        if sel.empty:
            continue
        r = {"set": name, "n": len(sel), "classifier_group_agree": (sel.cls_group == sel.human_group).mean()}
        if name.startswith("A"):
            r["coder1_group_agree"] = (sel.coder1_group == sel.human_group).mean()
        st = sel.stance_v2.map(STANCE_MAP)
        r["stance_rules_agree"] = (st == sel.stance).mean()
        for g in ("drafting", "polish_only"):
            tp = int(((sel.cls_group == g) & (sel.human_group == g)).sum())
            npred, ntrue = int((sel.cls_group == g).sum()), int((sel.human_group == g).sum())
            r[f"{g}_precision"] = tp / npred if npred else None
            r[f"{g}_precision_ci"] = wilson(tp, npred) if npred else None
            r[f"{g}_recall"] = tp / ntrue if ntrue else None
            r[f"{g}_n_true"] = ntrue
        out.append(r)
    d = m[m.part == "D"]
    if len(d):
        out.append({"set": "D: in-text sentences", "n": len(d), "share_human_says_disclosure": (~d.stance.isin(["notdisc"])).mean()})
    pd.DataFrame(out).to_csv(os.path.join(OUT, "agreement.csv"), index=False, float_format="%.3f")
    print(pd.DataFrame(out).to_string())
    print(pd.crosstab(m[m.part != "D"].cls_group, m[m.part != "D"].human_group))


if __name__ == "__main__":
    main()
