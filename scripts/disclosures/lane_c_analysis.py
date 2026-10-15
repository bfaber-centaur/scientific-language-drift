"""Lane C analysis: disclosure categories vs paper-body language (ICLR 2027), as preregistered in
results/disclosures/lane_c_prereg.md.

Usage: python3 scripts/disclosures/lane_c_analysis.py [--boot 1000] [--perm 2000]

Inputs (from scripts/disclosures/lane_c_features.py): data/disclosures/lane_c_papers.parquet,
data/disclosures/lane_c_types.npz.

Writes to results/disclosures/:
  lane_c_groups.csv          papers per group
  lane_c_contrasts.csv       11 features x 3 contrasts: raw and topic/length-adjusted differences,
                             standardized effects with bootstrap CIs, within-stratum permutation p,
                             BH q per contrast, robustness subset (formulaic disclosures dropped)
  lane_c_disclosure_corr.csv disclosure length / specificity vs body features (rank, adjusted)
  lane_c_overlap.csv         disclosure/body vocabulary overlap: own vs matched vs unmatched bodies
  lane_c_scan.csv            exploratory word scan (CMH across topics, BH), plus a shuffled-label rerun
  fig_lane_c_heatmap.png, fig_lane_c_distributions.png, fig_lane_c_overlap.png
"""
from __future__ import annotations

import argparse
import json
import os

import numpy as np
import pandas as pd

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
DATA = os.path.join(ROOT, "data", "disclosures")
OUT = os.path.join(ROOT, "results", "disclosures")
SEED = 20271015
FEATURES = ["ai_words_p10k", "has_we_propose", "has_a_novel", "has_test_whether", "has_held_fixed",
            "has_results_support", "has_percentage_points", "func_share", "mean_tok_len", "mattr500", "bundle_rep"]
CONTRASTS = [("primary", "group", "drafting", "polish_only"),
             ("s1", "group", "other_use", "polish_only"),
             ("s2", "group2", "drafting", "polish_plus")]


def bh(p: np.ndarray) -> np.ndarray:
    p = np.asarray(p, float)
    n = len(p)
    o = np.argsort(p)
    q = p[o] * n / np.arange(1, n + 1)
    q = np.minimum.accumulate(q[::-1])[::-1]
    out = np.empty(n)
    out[o] = np.minimum(q, 1)
    return out


def dummies(df: pd.DataFrame) -> np.ndarray:
    """Intercept + topic and length-decile fixed effects (one level of each dropped)."""
    t = pd.get_dummies(df.topic.astype(int), drop_first=True, dtype=float).to_numpy()
    l = pd.get_dummies(df.len_decile.astype(int), drop_first=True, dtype=float).to_numpy()
    return np.hstack([np.ones((len(df), 1)), t, l])


def resid(D: np.ndarray, Y: np.ndarray) -> np.ndarray:
    beta, *_ = np.linalg.lstsq(D, Y, rcond=None)
    return Y - D @ beta


def adj_beta(D, x, Y):
    R = resid(D, np.column_stack([x, Y]))
    rx, RY = R[:, 0], R[:, 1:]
    return (rx @ RY) / (rx @ rx)


def pooled_sd(Y, x):
    a, b = Y[x == 1], Y[x == 0]
    return np.sqrt(((len(a) - 1) * a.var(0, ddof=1) + (len(b) - 1) * b.var(0, ddof=1)) / (len(a) + len(b) - 2))


def permute_within(x: np.ndarray, strata: np.ndarray, rng) -> np.ndarray:
    xp = x.copy()
    for idx in STRATA_IDX:
        xp[idx] = x[idx][rng.permutation(len(idx))]
    return xp


def contrast(df, col, a, b, boot, perm, rng, label):
    sub = df[df[col].isin([a, b])].reset_index(drop=True)
    x = (sub[col] == a).to_numpy(float)
    Y = sub[FEATURES].to_numpy(float)
    D = dummies(sub)
    sd = pooled_sd(Y, x)
    raw = Y[x == 1].mean(0) - Y[x == 0].mean(0)
    beta = adj_beta(D, x, Y)
    bs = np.empty((boot, len(FEATURES)))
    for k in range(boot):
        i = rng.integers(0, len(sub), len(sub))
        bs[k] = adj_beta(D[i], x[i], Y[i]) / pooled_sd(Y[i], x[i])
    # Within-stratum permutation (shuffled-label negative control).
    strata = (sub.topic.astype(int) * 10 + sub.len_decile.astype(int)).to_numpy()
    global STRATA_IDX
    STRATA_IDX = [np.flatnonzero(strata == s) for s in np.unique(strata)]
    RY = resid(D, Y)
    null = np.empty((perm, len(FEATURES)))
    for k in range(perm):
        rx = resid(D, permute_within(x, strata, rng)[:, None])[:, 0]
        null[k] = (rx @ RY) / (rx @ rx)
    p = (1 + (np.abs(null) >= np.abs(beta)).sum(0)) / (perm + 1)
    # Robustness: drop formulaic disclosures (>= 50% template tokens or in a near-duplicate cluster).
    keep = ((sub.template_share < 0.5) & ~sub.near_dup).to_numpy()
    rb = adj_beta(D[keep], x[keep], Y[keep]) / pooled_sd(Y[keep], x[keep])
    rbs = np.empty((boot // 2, len(FEATURES)))
    ik = np.flatnonzero(keep)
    for k in range(boot // 2):
        i = ik[rng.integers(0, len(ik), len(ik))]
        rbs[k] = adj_beta(D[i], x[i], Y[i]) / pooled_sd(Y[i], x[i])
    rows = []
    for j, f in enumerate(FEATURES):
        rows.append({"contrast": label, "a": a, "b": b, "feature": f, "n_a": int(x.sum()), "n_b": int((1 - x).sum()),
                     "mean_a": Y[x == 1, j].mean(), "mean_b": Y[x == 0, j].mean(), "diff_raw": raw[j], "d_raw": raw[j] / sd[j],
                     "diff_adj": beta[j], "d_adj": beta[j] / sd[j], "d_adj_lo": np.percentile(bs[:, j], 2.5),
                     "d_adj_hi": np.percentile(bs[:, j], 97.5), "p_perm": p[j],
                     "null_sd_d": null[:, j].std() / sd[j],
                     "robust_n": int(keep.sum()), "robust_d_adj": rb[j], "robust_lo": np.percentile(rbs[:, j], 2.5),
                     "robust_hi": np.percentile(rbs[:, j], 97.5)})
    out = pd.DataFrame(rows)
    out["q_bh"] = bh(out.p_perm.to_numpy())
    return out


def rank_resid(D, v):
    r = pd.Series(v).rank().to_numpy(float)
    return resid(D, r[:, None])[:, 0]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--perm", type=int, default=2000)
    args = ap.parse_args()
    rng = np.random.default_rng(SEED)
    df = pd.read_parquet(os.path.join(DATA, "lane_c_papers.parquet"))
    for f in FEATURES:
        df[f] = df[f].astype(float)
    z = np.load(os.path.join(DATA, "lane_c_types.npz"))
    summary = {}

    g = pd.concat([df.group.value_counts().rename("papers"), df.group2.value_counts().rename("papers")]).reset_index()
    g.columns = ["group", "papers"]
    g = g.drop_duplicates("group")
    g.to_csv(os.path.join(OUT, "lane_c_groups.csv"), index=False)
    print(g.to_string(), flush=True)

    res = pd.concat([contrast(df, col, a, b, args.boot, args.perm, rng, lab) for lab, col, a, b in CONTRASTS])
    res.round(5).to_csv(os.path.join(OUT, "lane_c_contrasts.csv"), index=False)
    print(res[["contrast", "feature", "n_a", "n_b", "mean_a", "mean_b", "d_raw", "d_adj", "d_adj_lo", "d_adj_hi", "p_perm", "q_bh", "robust_d_adj"]].round(4).to_string(), flush=True)

    # Disclosure length and specificity vs body features (rank-transformed, topic/length adjusted).
    D = dummies(df)
    spec = (df.n_cats.rank() + df.tool_named.astype(float).rank() + df.author_types_n.rank()) / 3
    rows = []
    for name, v in [("disc_words", df.disc_words), ("specificity", spec)]:
        rv = rank_resid(D, v.to_numpy(float))
        for f in ["ai_words_p10k", "func_share", "mean_tok_len", "mattr500", "bundle_rep"]:
            rf = rank_resid(D, df[f].to_numpy())
            r = float(np.corrcoef(rv, rf)[0, 1])
            n = len(df)
            t = r * np.sqrt((n - 2) / (1 - r * r))
            from scipy import stats
            rows.append({"disclosure_measure": name, "feature": f, "n": n, "rho_adj": r, "p": 2 * stats.t.sf(abs(t), n - 2)})
    corr = pd.DataFrame(rows)
    corr["q_bh"] = bh(corr.p.to_numpy())
    corr.round(5).to_csv(os.path.join(OUT, "lane_c_disclosure_corr.csv"), index=False)
    print(corr.round(4).to_string(), flush=True)

    # Disclosure/body overlap.
    bptr, body, aptr, auth = z["body_ptr"], z["body"], z["auth_ptr"], z["auth"]
    n = len(df)
    B = [np.sort(body[bptr[i] : bptr[i + 1]]) for i in range(n)]
    A = [auth[aptr[i] : aptr[i + 1]] for i in range(n)]
    V = len(z["vocab"])
    dfv = np.bincount(body, minlength=V)
    general = dfv >= 0.05 * n

    def frac(a, b):
        if len(a) == 0:
            return np.nan
        j = np.searchsorted(b, a)
        j[j >= len(b)] = len(b) - 1
        return float((b[j] == a).mean())

    strata = (df.topic.astype(int) * 10 + df.len_decile.astype(int)).to_numpy()
    by_s = {s: np.flatnonzero(strata == s) for s in np.unique(strata)}
    by_t = {t: np.flatnonzero(df.topic.to_numpy() == t) for t in np.unique(df.topic)}
    fw_b = z["body_fw"].astype(float)
    fw_d = z["disc_fw"].astype(float)
    fw_b /= np.linalg.norm(fw_b, axis=1, keepdims=True) + 1e-12
    fw_d /= np.linalg.norm(fw_d, axis=1, keepdims=True) + 1e-12
    recs = []
    K = 20
    for i in range(n):
        if len(A[i]) < 3:
            continue
        pool = by_s[strata[i]]
        if len(pool) < K + 1:
            pool = by_t[df.topic.iat[i]]
        pool = pool[pool != i]
        ctrl = rng.choice(pool, size=min(K, len(pool)), replace=False)
        rnd = rng.integers(0, n, K)
        rnd = rnd[rnd != i]
        ag = A[i][general[A[i]]]
        recs.append({
            "i": i, "group": df.group.iat[i], "group2": df.group2.iat[i], "n_types": len(A[i]), "n_general": len(ag),
            "own_all": frac(A[i], B[i]), "matched_all": np.mean([frac(A[i], B[j]) for j in ctrl]),
            "random_all": np.mean([frac(A[i], B[j]) for j in rnd]),
            "own_gen": frac(ag, B[i]) if len(ag) else np.nan,
            "matched_gen": np.mean([frac(ag, B[j]) for j in ctrl]) if len(ag) else np.nan,
            "random_gen": np.mean([frac(ag, B[j]) for j in rnd]) if len(ag) else np.nan,
            "own_fw": float(fw_d[i] @ fw_b[i]), "matched_fw": float((fw_b[ctrl] @ fw_d[i]).mean()),
            "random_fw": float((fw_b[rnd] @ fw_d[i]).mean()),
        })
    ov = pd.DataFrame(recs)
    orows = []
    for kind in ["all", "gen", "fw"]:
        for grp in ["ALL", "drafting", "polish_only", "polish_plus"]:
            s = ov if grp == "ALL" else ov[(ov.group == grp) | (ov.group2 == grp)]
            s = s.dropna(subset=[f"own_{kind}", f"matched_{kind}"])
            e = (s[f"own_{kind}"] - s[f"matched_{kind}"]).to_numpy()
            e2 = (s[f"matched_{kind}"] - s[f"random_{kind}"]).to_numpy()
            bsm = [e[rng.integers(0, len(e), len(e))].mean() for _ in range(500)]
            orows.append({"measure": {"all": "author word types (all)", "gen": "author word types in >=5% of bodies",
                                      "fw": "stopword-profile cosine"}[kind], "group": grp, "papers": len(s),
                          "own": s[f"own_{kind}"].mean(), "matched": s[f"matched_{kind}"].mean(), "random": s[f"random_{kind}"].mean(),
                          "enrichment_own_minus_matched": e.mean(), "ci_lo": np.percentile(bsm, 2.5), "ci_hi": np.percentile(bsm, 97.5),
                          "topic_effect_matched_minus_random": e2.mean(), "share_own_gt_matched": float((e > 0).mean())})
    # Does enrichment differ between drafting and polish_only papers?
    for kind in ["all", "gen", "fw"]:
        a = ov[ov.group == "drafting"].dropna(subset=[f"own_{kind}"])
        b = ov[ov.group == "polish_only"].dropna(subset=[f"own_{kind}"])
        ea = (a[f"own_{kind}"] - a[f"matched_{kind}"]).to_numpy()
        eb = (b[f"own_{kind}"] - b[f"matched_{kind}"]).to_numpy()
        diffs = [ea[rng.integers(0, len(ea), len(ea))].mean() - eb[rng.integers(0, len(eb), len(eb))].mean() for _ in range(500)]
        orows.append({"measure": {"all": "author word types (all)", "gen": "author word types in >=5% of bodies", "fw": "stopword-profile cosine"}[kind],
                      "group": "drafting minus polish_only", "papers": len(ea) + len(eb),
                      "enrichment_own_minus_matched": ea.mean() - eb.mean(), "ci_lo": np.percentile(diffs, 2.5), "ci_hi": np.percentile(diffs, 97.5)})
    ovr = pd.DataFrame(orows)
    ovr.round(5).to_csv(os.path.join(OUT, "lane_c_overlap.csv"), index=False)
    print(ovr.round(4).to_string(), flush=True)

    # Exploratory scan: word types in >= 1% of bodies (top 5,000 by df); CMH across topic clusters.
    from scipy import sparse, stats
    top = np.argsort(-dfv)[:5000]
    top = top[dfv[top] >= 0.01 * n]
    col = -np.ones(V, dtype=np.int64)
    col[top] = np.arange(len(top))
    rows_i = np.repeat(np.arange(n), np.diff(bptr))
    c = col[body]
    m = c >= 0
    X = sparse.csr_matrix((np.ones(m.sum()), (rows_i[m], c[m])), shape=(n, len(top)))
    vocab = z["vocab"]

    def scan(labels):
        sel = np.isin(labels, ["drafting", "polish_only"])
        x = (labels == "drafting")
        topics = df.topic.to_numpy()
        num = np.zeros(len(top))
        var = np.zeros(len(top))
        mh_n = np.zeros(len(top))
        mh_d = np.zeros(len(top))
        for t in np.unique(topics):
            ii = np.flatnonzero(sel & (topics == t))
            if len(ii) < 2:
                continue
            xt = x[ii]
            n1, N = xt.sum(), len(ii)
            n0 = N - n1
            if n1 == 0 or n0 == 0:
                continue
            Xt = X[ii]
            a = np.asarray(Xt[xt].sum(0)).ravel()
            mk = np.asarray(Xt.sum(0)).ravel()
            num += a - n1 * mk / N
            var += n1 * n0 * mk * (N - mk) / (N * N * (N - 1))
            b, cc = n1 - a, mk - a
            dd = n0 - cc
            mh_n += a * dd / N
            mh_d += b * cc / N
        chi = num ** 2 / np.maximum(var, 1e-12)
        return chi, stats.chi2.sf(chi, 1), mh_n / np.maximum(mh_d, 1e-12), num

    labels = df.group.to_numpy()
    chi, p, orr, num = scan(labels)
    q = bh(p)
    sel = np.isin(labels, ["drafting", "polish_only"])
    Xs = X[sel]
    xs = labels[sel] == "drafting"
    prev_a = np.asarray(Xs[xs].mean(0)).ravel()
    prev_b = np.asarray(Xs[~xs].mean(0)).ravel()
    scan_df = pd.DataFrame({"word": vocab[top], "df_all": dfv[top], "prev_drafting": prev_a, "prev_polish_only": prev_b,
                            "diff_pp": 100 * (prev_a - prev_b), "mh_odds_ratio": orr, "cmh_chi2": chi, "p": p, "q_bh": q})
    # Shuffled-label control: permute labels within topic clusters and count BH hits.
    sh_hits = []
    for k in range(5):
        lab2 = labels.copy()
        for t, idx in by_t.items():
            ii = idx[sel[idx]]
            lab2[ii] = labels[ii][rng.permutation(len(ii))]
        _, p2, _, _ = scan(lab2)
        sh_hits.append(int((bh(p2) < 0.05).sum()))
    scan_df = scan_df.sort_values("p")
    scan_df.head(200).round(6).to_csv(os.path.join(OUT, "lane_c_scan.csv"), index=False)
    summary["scan"] = {"words_tested": int(len(top)), "bh_hits_q05": int((q < 0.05).sum()),
                       "bh_hits_up_in_drafting": int(((q < 0.05) & (num > 0)).sum()),
                       "shuffled_label_bh_hits_5_runs": sh_hits}
    print(scan_df.head(40).round(4).to_string(), "\n", summary["scan"], flush=True)

    # Figures
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    piv = res.pivot(index="feature", columns="contrast", values="d_adj").loc[FEATURES, ["primary", "s1", "s2"]]
    qv = res.pivot(index="feature", columns="contrast", values="q_bh").loc[FEATURES, ["primary", "s1", "s2"]]
    fig, ax = plt.subplots(figsize=(6.5, 6))
    lim = max(0.15, np.nanmax(np.abs(piv.to_numpy())))
    im = ax.imshow(piv.to_numpy(), cmap="RdBu_r", vmin=-lim, vmax=lim, aspect="auto")
    ax.set_xticks(range(3), ["drafting vs\npolish_only", "other_use vs\npolish_only", "drafting vs\npolish_plus"])
    ax.set_yticks(range(len(FEATURES)), FEATURES)
    for r in range(len(FEATURES)):
        for cc in range(3):
            ax.text(cc, r, f"{piv.iat[r, cc]:+.2f}{'*' if qv.iat[r, cc] < 0.05 else ''}", ha="center", va="center", fontsize=8)
    fig.colorbar(im, label="standardized difference (topic and length adjusted)")
    ax.set_title("ICLR 2027 body features by self-reported AI use\n(* BH q < 0.05, within-stratum permutation)", fontsize=9)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_lane_c_heatmap.png"), dpi=130)

    cont = ["ai_words_p10k", "func_share", "mean_tok_len", "mattr500", "bundle_rep"]
    order = ["none", "polish_only", "polish_plus", "nonwriting", "drafting"]
    fig, axes = plt.subplots(1, len(cont), figsize=(15, 3.6))
    for ax, f in zip(axes, cont):
        data = [df.loc[df.group2 == o, f].dropna().to_numpy() for o in order]
        if f == "ai_words_p10k":
            data = [np.log10(d + 0.1) for d in data]
        ax.boxplot(data, showfliers=False)
        ax.set_xticks(range(1, len(order) + 1), [f"{o}\n(n={len(d)})" for o, d in zip(order, data)], fontsize=6, rotation=30)
        ax.set_title(("log10(0.1 + " + f + ")") if f == "ai_words_p10k" else f, fontsize=9)
    fig.suptitle("Body-text features by disclosure group (classifier v2; boxes = IQR, whiskers 1.5 IQR)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_lane_c_distributions.png"), dpi=130)

    fig, axes = plt.subplots(1, 3, figsize=(12, 3.6))
    for ax, kind, ttl in zip(axes, ["all", "gen", "fw"], ["author word types (all)", "author word types in >=5% of bodies", "stopword-profile cosine"]):
        s = ovr[(ovr.measure == ttl) & (ovr.group == "ALL")].iloc[0]
        ax.bar(["own body", "matched\n(topic, length)", "random"], [s.own, s.matched, s.random], color=["#444", "#999", "#ccc"])
        ax.set_title(f"{ttl}\nown - matched = {s.enrichment_own_minus_matched:+.3f} [{s.ci_lo:+.3f}, {s.ci_hi:+.3f}]", fontsize=8)
        lo = min(s.own, s.matched, s.random)
        ax.set_ylim(max(0, lo - 0.15 * (1 - lo)), None)
    fig.suptitle("Do disclosures share vocabulary with their own paper? (share of disclosure items found in body)", fontsize=10)
    fig.tight_layout()
    fig.savefig(os.path.join(OUT, "fig_lane_c_overlap.png"), dpi=130)

    summary.update({"boot": args.boot, "perm": args.perm, "seed": SEED, "papers": n})
    json.dump(summary, open(os.path.join(OUT, "lane_c_analysis_run.json"), "w"), indent=1)


STRATA_IDX: list = []

if __name__ == "__main__":
    main()
