"""V2 disclosures: compare human and model readers with each other and with the machine labels.

Usage:
    python3 scripts/v2/compare_coders.py --sample results/v2/disclosures/labelling/sample.csv \
        --out results/v2/disclosures/labelling --human data/v2/labelling/export \
        opusA=data/v2/labelling/blind/opusA.json opusB=... sonnetA=... haikuA=...

Each model reader saw only the item texts and the labelling page's instructions (`codebook.md`), not
the classifier labels, the rule labels, the human labels or any other reader's. Reader names are
<model><run>; the model is the name without its final letter. The sample file needs `item`, `cls_group`
and `stance_v2`, and optionally `part`, `cohort`. Writes, with no text:
  <out>/coder_labels.csv               every reader's stance, uses and group per item
  <out>/coder_agreement.csv            pairwise agreement and Cohen's kappa (group, stance, exact use set)
  <out>/classifier_vs_consensus.csv    classifier v2 and the stance rules against reference readers
"""
from __future__ import annotations

import argparse
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


def kappa(a, b):
    a, b = list(a), list(b)
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pe = sum((a.count(c) / n) * (b.count(c) / n) for c in set(a) | set(b))
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


def majority(values):
    for g in set(values):
        if values.count(g) * 2 > len(values):
            return g
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--human")
    ap.add_argument("--statements-only", action="store_true", help="drop part D (single in-text sentences) from agreement")
    ap.add_argument("readers", nargs="+", help="name=labels.json")
    a = ap.parse_args()

    src = {}
    if a.human:
        src["human"] = load_human(a.human)
    for spec in a.readers:
        name, path = spec.split("=", 1)
        src[name] = load_coder(path)
    s = pd.read_csv(a.sample)
    for name, lab in src.items():
        missing = set(s.item) - set(lab)
        assert not missing, (name, sorted(missing)[:5], len(missing))
        s[f"{name}_stance"] = s.item.map(lambda i: lab[i][0])
        s[f"{name}_uses"] = s.item.map(lambda i: ";".join(lab[i][1]))
        s[f"{name}_group"] = [human_group(lab[i][0], lab[i][1]) for i in s.item]
    s["rules_stance"] = s.stance_v2.map(STANCE_MAP)
    models = sorted({n[:-1] for n in src if n != "human"})
    runs = {m: [n for n in src if n != "human" and n[:-1] == m] for m in models}
    # one vote per model (its first run), so a model read twice does not count twice
    first = [runs[m][0] for m in models]
    s["model_majority_group"] = [majority([r[f"{n}_group"] for n in first]) for _, r in s.iterrows()]
    s["model_majority_stance"] = [majority([r[f"{n}_stance"] for n in first]) for _, r in s.iterrows()]
    keep = [c for c in ("item", "part", "cohort", "cls_group", "cls_labels", "rules_stance") if c in s]
    keep += [f"{n}_{k}" for n in src for k in ("stance", "uses", "group")] + ["model_majority_group", "model_majority_stance"]
    os.makedirs(a.out, exist_ok=True)
    s[keep].to_csv(os.path.join(a.out, "coder_labels.csv"), index=False)

    sel = s[s.part != "D"] if (a.statements_only and "part" in s) else s
    readers = list(src)
    out = []
    for x, y in itertools.combinations(readers + ["classifier"], 2):
        gx = sel.cls_group if x == "classifier" else sel[f"{x}_group"]
        gy = sel.cls_group if y == "classifier" else sel[f"{y}_group"]
        r = {"pair": f"{x} vs {y}", "n": len(sel), "group_agree": (gx == gy).mean(), "group_kappa": kappa(gx, gy)}
        sx = sel.rules_stance if x == "classifier" else sel[f"{x}_stance"]
        sy = sel.rules_stance if y == "classifier" else sel[f"{y}_stance"]
        sx, sy = sx.fillna("none"), sy.fillna("none")
        r.update(stance_agree=(sx == sy).mean(), stance_kappa=kappa(sx, sy))
        if "classifier" not in (x, y):
            r["uses_exact"] = (sel[f"{x}_uses"].fillna("") == sel[f"{y}_uses"].fillna("")).mean()
        r["kind"] = ("same model" if x[:-1] == y[:-1] and "human" not in (x, y) and "classifier" not in (x, y)
                     else "machine labels" if "classifier" in (x, y) else "human" if "human" in (x, y) else "across models")
        out.append(r)
    pd.DataFrame(out).to_csv(os.path.join(a.out, "coder_agreement.csv"), index=False, float_format="%.3f")

    refs = ["model_majority_group"] + [f"{n}_group" for n in readers]
    res = []
    for ref in refs:
        t = sel[sel[ref].notna()]
        r = {"reference": ref.removesuffix("_group"), "n": len(t), "classifier_group_agree": (t.cls_group == t[ref]).mean()}
        rs = ref.replace("_group", "_stance")
        r["rules_stance_agree"] = (t.rules_stance == t[rs]).mean()
        for g in ("drafting", "polish_only"):
            tp = int(((t.cls_group == g) & (t[ref] == g)).sum())
            npred, ntrue = int((t.cls_group == g).sum()), int((t[ref] == g).sum())
            r[f"{g}_precision"] = tp / npred if npred else None
            r[f"{g}_precision_ci"] = wilson(tp, npred) if npred else None
            r[f"{g}_recall"] = tp / ntrue if ntrue else None
            r[f"{g}_recall_ci"] = wilson(tp, ntrue) if ntrue else None
            r[f"{g}_n_true"] = ntrue
        res.append(r)
    pd.DataFrame(res).to_csv(os.path.join(a.out, "classifier_vs_consensus.csv"), index=False, float_format="%.3f")
    with pd.option_context("display.width", 220, "display.max_columns", 30):
        print(pd.DataFrame(out).to_string())
        print(pd.DataFrame(res)[["reference", "n", "classifier_group_agree", "rules_stance_agree", "drafting_precision",
                                 "drafting_recall", "polish_only_precision", "polish_only_recall"]].to_string())


if __name__ == "__main__":
    main()
