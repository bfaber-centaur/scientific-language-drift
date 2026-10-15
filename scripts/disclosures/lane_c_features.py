"""Per-paper inputs for Lane C (disclosure categories vs paper-body language), ICLR 2027.

Usage: python3 scripts/disclosures/lane_c_features.py [--workers 4] [--limit N]

Implements the body definition and the 11 features fixed in results/disclosures/lane_c_prereg.md:
body = main body (before the references marker) -> statement removal v2 -> the disclosure span that
mlngrams.disclosures.extract finds in that body is cut too. Bodies under 1,000 tokens are dropped.

Writes (git-ignored, no text):
  data/disclosures/lane_c_papers.parquet  one row per clean-tier paper: v2 labels and group,
      disclosure length/specificity/template share/near-duplicate flag, body features, topic text
      is NOT stored (only the 40-way topic cluster and the length decile).
  data/disclosures/lane_c_types.npz       per-paper body word-type ids and disclosure author
      word-type ids (for the overlap analysis and the exploratory scan), plus the vocabulary.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import sys
from concurrent.futures import ProcessPoolExecutor

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.dirname(__file__))

import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import pyarrow.parquet as pq  # noqa: E402

from mlngrams.disclosure_classify import CLASSIFIER_VERSION, classify  # noqa: E402
from mlngrams.disclosures import extract  # noqa: E402
from mlngrams.filters import STOPWORDS  # noqa: E402
from mlngrams.load import fetch, main_body  # noqa: E402
from mlngrams.sections import strip_statements  # noqa: E402
from mlngrams.tokenize import tokenize  # noqa: E402
from phrases import STOCK_DF, cover, minhash_clusters, template_ngrams  # noqa: E402
from eval_groups import group  # noqa: E402

DATA = os.path.join(ROOT, "data", "disclosures")
SEED = 20271015
MIN_TOKENS = 1000
AI_WORDS = re.compile(r"^(?:delv(?:e|es|ed|ing)|intricate(?:ly)?|pivotal|underscor(?:e|es|ed|ing)|showcas(?:e|es|ed|ing)|realms?)$")
PHRASES = ["we propose", "a novel", "test whether", "held fixed", "results support", "percentage points"]
FW = sorted(STOPWORDS)
FW_INDEX = {w: i for i, w in enumerate(FW)}
TOOL = re.compile(r"\b(?:chatgpt|gpt-?\d[\w.-]*|openai|claude|anthropic|gemini|bard|copilot|codex|cursor|grammarly|deepseek|qwen|deepl|perplexity|writefull|overleaf|grok|kimi)\b", re.I)
WORD = re.compile(r"^[a-z][a-z-]{2,}$")


def mattr(toks: list[str], w: int = 500) -> float:
    if len(toks) < w:
        return len(set(toks)) / len(toks)
    c = collections.Counter(toks[:w])
    tot = len(c)
    s = tot
    for i in range(w, len(toks)):
        out, inn = toks[i - w], toks[i]
        c[out] -= 1
        if c[out] == 0:
            del c[out]
        c[inn] += 1
        s += len(c)
    return s / (len(toks) - w + 1)


def body_features(text: str) -> dict | None:
    body = strip_statements(main_body(text or ""))[0]
    d = extract(body)
    cut = False
    if d is not None:
        body = body[: d.start] + "\n" + body[d.end :]
        cut = True
    segs = tokenize(body)
    toks = [w for s in segs for w in s]
    n = len(toks)
    if n < MIN_TOKENS:
        return None
    joined = " " + " | ".join(" ".join(s) for s in segs) + " "
    grams4 = collections.Counter(tuple(s[i : i + 4]) for s in segs for i in range(len(s) - 3))
    n4 = sum(grams4.values())
    fw = np.zeros(len(FW), dtype=np.int32)
    for w in toks:
        j = FW_INDEX.get(w)
        if j is not None:
            fw[j] += 1
    letters = [len(w) for w in toks if w != "<num>"]
    out = {
        "body_tokens": n,
        "disclosure_cut_from_body": cut,
        "ai_words_p10k": 1e4 * sum(bool(AI_WORDS.match(w)) for w in toks) / n,
        **{"has_" + p.replace(" ", "_"): f" {p} " in joined for p in PHRASES},
        "func_share": float(fw.sum()) / n,
        "mean_tok_len": float(np.mean(letters)) if letters else float("nan"),
        "mattr500": mattr(toks),
        "bundle_rep": sum(c for c in grams4.values() if c >= 3) / max(1, n4),
        "fw_profile": fw,
        "types": " ".join(sorted({w for w in toks if WORD.match(w)})),
        "topic_text": body[:3000],
    }
    return out


def work(batch: list[dict]) -> list[tuple[str, dict | None]]:
    return [(r["paper_id"], body_features(r["text"])) for r in batch]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    # Disclosures: v2 labels, length, specificity, template share, near-duplicates, author word types.
    disc = pd.read_parquet(os.path.join(DATA, "iclr2027.parquet"), columns=["doc_id", "title", "found", "tier", "text", "text_clean", "n_words"])
    disc = disc[(disc.found == True) & (disc.tier == "clean")].reset_index(drop=True)  # noqa: E712
    if args.limit:
        disc = disc.head(args.limit)
    tmpl = template_ngrams(4)
    docs = [tokenize(t) for t in disc.text]
    df6 = collections.Counter()
    for segs in docs:
        df6.update({tuple(s[i : i + 6]) for s in segs for i in range(len(s) - 5)})
    stock6 = {g for g, c in df6.items() if c >= STOCK_DF}
    rows, auth_types, shingles, dfw = [], [], [], []
    for i, segs in enumerate(docs):
        ntok = ttok = 0
        at, sh = set(), set()
        fw = np.zeros(len(FW), dtype=np.int32)
        for s in segs:
            ct = cover(s, tmpl, 4)
            cs = cover(s, stock6, 6) & ~ct
            ntok += len(s)
            ttok += int(ct.sum())
            for j, w in enumerate(s):
                if not (ct[j] or cs[j]) and WORD.match(w) and w not in STOPWORDS:
                    at.add(w)
                k = FW_INDEX.get(w)
                if k is not None:
                    fw[k] += 1
            for j in range(len(s) - 4):
                sh.add(int.from_bytes(hashlib.blake2b(" ".join(s[j : j + 5]).encode(), digest_size=7).digest(), "little"))
        out = classify(disc.text_clean[i])
        labs = out["labels"]
        rows.append({"doc_id": disc.doc_id[i], "labels": ";".join(sorted(labs)), "group": group(labs),
                     "writing_unspecified": out["writing_unspecified"], "n_cats": len(labs - {"none", "ambiguous"}),
                     "tool_named": bool(TOOL.search(disc.text_clean[i])), "disc_words": int(disc.n_words[i]),
                     "disc_tokens": ntok, "template_share": ttok / max(1, ntok), "author_types_n": len(at)})
        auth_types.append(sorted(at))
        shingles.append(sh)
        dfw.append(fw)
    clusters = minhash_clusters(shingles)
    csize = collections.Counter(clusters)
    meta = pd.DataFrame(rows)
    meta["near_dup"] = [csize[c] > 1 for c in clusters]
    g = meta.group
    meta.loc[(g == "other_use") & meta.labels.str.contains("polish"), "group2"] = "polish_plus"
    meta.loc[(g == "other_use") & ~meta.labels.str.contains("polish"), "group2"] = "nonwriting"
    meta["group2"] = meta.group2.fillna(meta.group)
    print(meta.group.value_counts().to_string(), "\n", meta.group2.value_counts().to_string(), flush=True)

    # Bodies (streamed in bounded chunks; word types are mapped to int ids as they arrive).
    del docs, shingles
    want = set(meta.doc_id)
    pf = pq.ParquetFile(fetch("omissions", "iclr", 2027))
    vocab: dict[str, int] = {}
    res = {}

    def take(out):
        for pid, f in out:
            if f is not None:
                f["types"] = np.array([vocab.setdefault(w, len(vocab)) for w in f["types"].split()], dtype=np.int32)
                res[pid] = f

    with ProcessPoolExecutor(args.workers) as ex:
        pending, k = [], 0
        for b in pf.iter_batches(batch_size=200, columns=["paper_id", "text"]):
            rs = [r for r in b.to_pylist() if r["paper_id"] in want]
            if rs:
                pending.append(ex.submit(work, rs))
            while len(pending) >= 2 * args.workers:
                take(pending.pop(0).result())
                k += 1
                if k % 20 == 0:
                    print(f"batch {k}: {len(res)} bodies", flush=True)
        for fut in pending:
            take(fut.result())
    keep = meta.doc_id.isin(res).to_numpy()
    print(f"bodies kept: {keep.sum()} of {len(meta)} (dropped < {MIN_TOKENS} tokens or missing)", flush=True)
    meta = meta[keep].reset_index(drop=True)
    auth_types = [a for a, k in zip(auth_types, keep) if k]
    dfw = [a for a, k in zip(dfw, keep) if k]
    titles = dict(zip(disc.doc_id, disc.title))

    feat_cols = ["body_tokens", "disclosure_cut_from_body", "ai_words_p10k"] + ["has_" + p.replace(" ", "_") for p in PHRASES] + \
        ["func_share", "mean_tok_len", "mattr500", "bundle_rep"]
    for c in feat_cols:
        meta[c] = [res[d][c] for d in meta.doc_id]

    # Topic clusters (fixed in the preregistration) and length deciles.
    from sklearn.cluster import KMeans
    from sklearn.feature_extraction.text import TfidfVectorizer
    topic_text = [(titles.get(d) or "") + " " + res[d]["topic_text"] for d in meta.doc_id]
    vec = TfidfVectorizer(sublinear_tf=True, stop_words="english", min_df=20, max_features=20000)
    X = vec.fit_transform(topic_text)
    km = KMeans(n_clusters=40, random_state=SEED, n_init=4).fit(X)
    meta["topic"] = km.labels_
    meta["len_decile"] = pd.qcut(meta.body_tokens, 10, labels=False)
    terms = np.array(vec.get_feature_names_out())
    order = km.cluster_centers_.argsort(axis=1)[:, ::-1]
    topics = pd.DataFrame({"topic": range(40), "papers": np.bincount(km.labels_, minlength=40),
                           "top_terms": [" ".join(terms[order[k, :10]]) for k in range(40)]})
    topics.to_csv(os.path.join(ROOT, "results", "disclosures", "lane_c_topics.csv"), index=False)

    def ids(ws):
        return np.array([vocab.setdefault(w, len(vocab)) for w in ws], dtype=np.int32)
    body_ids = [res[d]["types"] for d in meta.doc_id]
    auth_ids = [ids(a) for a in auth_types]
    np.savez_compressed(
        os.path.join(DATA, "lane_c_types.npz"),
        body_ptr=np.cumsum([0] + [len(x) for x in body_ids]), body=np.concatenate(body_ids),
        auth_ptr=np.cumsum([0] + [len(x) for x in auth_ids]), auth=np.concatenate(auth_ids) if auth_ids else np.zeros(0, np.int32),
        body_fw=np.stack([res[d]["fw_profile"] for d in meta.doc_id]), disc_fw=np.stack(dfw),
        vocab=np.array(sorted(vocab, key=vocab.get)), fw=np.array(FW),
    )
    meta["classifier_version"] = CLASSIFIER_VERSION
    meta.to_parquet(os.path.join(DATA, "lane_c_papers.parquet"), index=False)
    summ = {"papers_clean_tier": int(len(keep)), "bodies_kept": int(keep.sum()), "min_tokens": MIN_TOKENS,
            "classifier_version": CLASSIFIER_VERSION, "disclosure_cut_from_body": int(meta.disclosure_cut_from_body.sum()),
            "groups": meta.group.value_counts().to_dict(), "groups2": meta.group2.value_counts().to_dict(), "seed": SEED}
    json.dump(summ, open(os.path.join(ROOT, "results", "disclosures", "lane_c_run.json"), "w"), indent=1)
    print(json.dumps(summ, indent=1))


if __name__ == "__main__":
    main()
