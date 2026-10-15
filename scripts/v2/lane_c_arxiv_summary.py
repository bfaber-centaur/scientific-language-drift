"""Lane C (V2): summarise results/v2/function_words/arxiv_abstracts.csv into arxiv_summary.csv.

Pooled rates per million letter tokens in the dataset abstract (ds) and the arXiv metadata abstract (ax)
of the same matched papers, by cohort and by similarity band (all matched pairs; near-identical wording
>= 0.9). 95% intervals: 2,000 paper bootstraps of the arXiv-abstract rate.
"""
import os
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
F = os.path.join(ROOT, "results/v2/function_words")
d = pd.read_csv(os.path.join(F, "arxiv_abstracts.csv"))
d = d[d.arxiv_match & d.found_abstract & d.ds_tokens.notna()]
rng = np.random.default_rng(20261015)
rows = []
for band, sub in (("all_matched", d), ("similarity>=0.9", d[d.similarity >= 0.9])):
    for c, g in sub.groupby("cohort"):
        r = dict(cohort=c, subset=band, n=len(g), median_similarity=round(g.similarity.median(), 3),
                 median_arxiv_v1_date=sorted(g.published)[len(g) // 2])
        for w in ("of", "in", "we", "and"):
            for tag in ("ds", "ax"):
                r[f"{tag}_{w}"] = round(g[f"{tag}_{w}"].sum() / g[f"{tag}_tokens"].sum() * 1e6)
            idx = rng.integers(0, len(g), size=(2000, len(g)))
            x, t = g[f"ax_{w}"].to_numpy(float), g["ax_tokens"].to_numpy(float)
            bs = x[idx].sum(1) / t[idx].sum(1) * 1e6
            r[f"ax_{w}_lo"], r[f"ax_{w}_hi"] = np.percentile(bs, [2.5, 97.5]).round()
        rows.append(r)
out = pd.DataFrame(rows)
out.to_csv(os.path.join(F, "arxiv_summary.csv"), index=False)
print(out.to_string(index=False))
