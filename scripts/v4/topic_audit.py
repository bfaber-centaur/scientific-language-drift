"""V4: print random ICLR titles matched by each topic tag (title + keywords + abstract), for eyeballing.

Writes results/v4/iclr/topic_audit.txt. Usage: python3 scripts/v4/topic_audit.py --src ~/ext/paperlists
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from topics import TOPICS, tag  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=os.path.expanduser("~/ext/paperlists"))
    a = ap.parse_args()
    rnd = random.Random(20261022)
    lines = []
    for y in (2019, 2026):
        recs = [r for r in json.load(open(os.path.join(a.src, f"iclr{y}.json"))) if r.get("track", "main") == "main"]
        tags = [tag((r.get("title") or "") + " . " + (r.get("keywords") or "").replace(";", " , ") + " . "
                    + (r.get("abstract") or "")) for r in recs]
        for k in TOPICS:
            hit = [r["title"] for r, t in zip(recs, tags) if t["t_" + k]]
            lines.append(f"== {y} {k}: {len(hit)} of {len(recs)}")
            lines += ["   " + x for x in rnd.sample(hit, min(6, len(hit)))]
    out = os.path.join(HERE, "..", "..", "results", "v4", "iclr", "topic_audit.txt")
    open(out, "w").write("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
