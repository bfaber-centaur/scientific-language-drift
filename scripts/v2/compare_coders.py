"""V2 disclosures: Bobby's labels vs two blind Claude Opus coders vs the machine labels.

Usage:
    python3 scripts/v2/compare_coders.py <human export dir> <coder A labels.json> <coder B labels.json>

The coders saw only the item texts (from the labelling page) and the labelling page's own
instructions, not the classifier labels, Bobby's labels or each other's. Writes, with no text:
  results/v2/disclosures/labelling/coder_labels.csv   item, part, cohort, each source's stance/uses/group
  results/v2/disclosures/labelling/coder_agreement.csv  pairwise agreement and Cohen's kappa
  results/v2/disclosures/labelling/classifier_vs_consensus.csv  classifier v2 against the 2-of-3 majority
"""
from __future__ import annotations

import glob
import itertools
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "scripts", "disclosures"))
sys.path.insert(0, HERE)

import pandas as pd  # noqa: E402

from evaluate import wilson  # noqa: E402
from score_labels import STANCE_MAP, human_group  # noqa: E402

OUT = os.path.join(ROOT, "results", "v2", "disclosures", "labelling")
USES = ["polish", "drafting", "coding", "literature", "other", "unclear"]


def kappa(a, b):
    a, b = list(a), list(b)
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    cats = set(a) | set(b)
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in cats)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0


def load_human(d):
    rows = {}
    for f in glob.glob(os.path.join(d, "**", "*.json"), recursive=True):
        j = json.load(open(f))
        v = j.get("data", j)
        rows[os.path.basename(f)[:-5]] = (v.get("stance"), sorted(v.get("uses") or []))
    return rows


def load_coder(p):
    return {r["item"]: (r["stance"], sorted(r.get("uses") or [])) for r in json.load(open(p))}


def main():
    src = {"human": load_human(sys.argv[1]), "opusA": load_coder(sys.argv[2]), "opusB": load_coder(sys.argv[3])}
    s = pd.read_csv(os.path.join(OUT, "sample.csv"))
    for name, lab in src.items():
        missing = set(s.item) - set(lab)
        assert not missing, (name, sorted(missing))
        s[f"{name}_stance"] = s.item.map(lambda i: lab[i][0])
        s[f"{name}_uses"] = s.item.map(lambda i: ";".join(lab[i][1]))
        s[f"{name}_group"] = [human_group(lab[i][0], lab[i][1]) for i in s.item]
    s["rules_stance"] = s.stance_v2.map(STANCE_MAP)
    keep = ["item", "part", "cohort", "cls_group", "cls_labels", "rules_stance", "coder1_group"]
    keep += [f"{n}_{k}" for n in src for k in ("stance", "uses", "group")]
    s[keep].to_csv(os.path.join(OUT, "coder_labels.csv"), index=False)

    st = s[s.part != "D"]  # statements; part D are single in-text sentences
    out = []
    for subset, sel in (("statements A-C", st), ("all 45", s)):
        groups = {"human": sel.human_group, "opusA": sel.opusA_group, "opusB": sel.opusB_group,
                  "classifier": sel.cls_group}
        stances = {"human": sel.human_stance, "opusA": sel.opusA_stance, "opusB": sel.opusB_stance,
                   "rules": sel.rules_stance}
        for x, y in itertools.combinations(groups, 2):
            if subset == "all 45" and "classifier" in (x, y):
                continue
            out.append({"subset": subset, "measure": "group", "pair": f"{x} vs {y}", "n": len(sel),
                        "agree": (groups[x] == groups[y]).mean(), "kappa": kappa(groups[x], groups[y])})
        for x, y in itertools.combinations(stances, 2):
            if subset == "all 45" and "rules" in (x, y):
                continue
            a, b = stances[x].fillna("none"), stances[y].fillna("none")
            out.append({"subset": subset, "measure": "stance", "pair": f"{x} vs {y}", "n": len(sel),
                        "agree": (a == b).mean(), "kappa": kappa(a, b)})
        if subset == "statements A-C":
            for u in USES:
                tags = {n: sel[f"{n}_uses"].fillna("").str.split(";").map(lambda t, u=u: u in t) for n in src}
                for x, y in itertools.combinations(tags, 2):
                    out.append({"subset": subset, "measure": f"use tag: {u}", "pair": f"{x} vs {y}", "n": len(sel),
                                "agree": (tags[x] == tags[y]).mean(), "kappa": kappa(tags[x], tags[y]),
                                "x_positive": int(tags[x].sum()), "y_positive": int(tags[y].sum())})
    a = s[s.part == "A"]
    for n in src:
        out.append({"subset": "A: ICLR 2027 test2", "measure": "group", "pair": f"{n} vs V1.5 coder1", "n": len(a),
                    "agree": (a[f"{n}_group"] == a.coder1_group).mean(), "kappa": kappa(a[f"{n}_group"], a.coder1_group)})
    pd.DataFrame(out).to_csv(os.path.join(OUT, "coder_agreement.csv"), index=False, float_format="%.3f")

    # 2-of-3 majority of the three readers (human, opusA, opusB); ties left out.
    def maj(r):
        v = [r.human_group, r.opusA_group, r.opusB_group]
        for g in set(v):
            if v.count(g) >= 2:
                return g
        return None
    st = st.assign(consensus=st.apply(maj, axis=1), opus_pair=[a if a == b else None for a, b in zip(st.opusA_group, st.opusB_group)])
    res = []
    for ref in ("consensus", "opus_pair", "human_group"):
        sel = st[st[ref].notna()]
        r = {"reference": ref, "n": len(sel), "classifier_group_agree": (sel.cls_group == sel[ref]).mean()}
        for g in ("drafting", "polish_only"):
            tp = int(((sel.cls_group == g) & (sel[ref] == g)).sum())
            npred, ntrue = int((sel.cls_group == g).sum()), int((sel[ref] == g).sum())
            r[f"{g}_precision"] = tp / npred if npred else None
            r[f"{g}_precision_ci"] = wilson(tp, npred) if npred else None
            r[f"{g}_recall"] = tp / ntrue if ntrue else None
            r[f"{g}_recall_ci"] = wilson(tp, ntrue) if ntrue else None
            r[f"{g}_n_true"] = ntrue
        res.append(r)
    pd.DataFrame(res).to_csv(os.path.join(OUT, "classifier_vs_consensus.csv"), index=False, float_format="%.3f")
    with pd.option_context("display.width", 200):
        print(pd.DataFrame(out).query("measure in ['group','stance']").to_string())
        print(pd.DataFrame(res).to_string())
        print(pd.crosstab(st.cls_group, st.consensus.fillna("tie")))


if __name__ == "__main__":
    main()
