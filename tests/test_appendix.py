"""Synthetic checks for the Lane A region scanner (scripts/appendix_scan.py)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from appendix_scan import REF, analyse, checklist_end, checklist_start, find_sections, leading_refres  # noqa: E402

PROSE = "This sentence is ordinary prose about the method and its results in detail.\n"


def test_lettered_sections_and_order():
    post = ("A\nPROOFS\n" + PROSE * 5 + "A model is trained here.\n" + PROSE
            + "B ADDITIONAL EXPERIMENTS\n" + PROSE * 5 + "D\nHyperparameters\n" + PROSE * 3)
    secs = find_sections(post)
    assert [(s[0], s[1]) for s in secs] == [("A", "PROOFS"), ("B", "ADDITIONAL EXPERIMENTS"), ("D", "Hyperparameters")]


def test_table_of_contents_skipped():
    toc = "A Related Work 14\nB Proofs 15\nC Experiments 17\n"
    body = "A\nRELATED WORK\n" + PROSE * 5 + "B\nPROOFS\n" + PROSE * 5 + "C\nEXPERIMENTS\n" + PROSE * 5
    secs = find_sections(toc + body)
    assert [s[1] for s in secs] == ["RELATED WORK", "PROOFS", "EXPERIMENTS"]
    assert secs[0][2] >= len(toc)


def test_checklist_between_references_and_appendix():
    ck = "".join(f"Answer: [Yes]\nJustification: point {i}.\n" for i in range(5))
    post = ck + "A\nPROOFS\n" + PROSE * 10
    s = checklist_start(post)
    e = checklist_end(post, s)
    assert s == 0 and post[e:].startswith("A\nPROOFS")


def test_leading_bibliography_residue():
    bib = ("Jane Doe and John Roe. A paper title. In Proceedings of the Conference on Things, 2019.\n"
           "Ann Poe. Another title. arXiv preprint arXiv:1234.5678, 2020.\n")
    post = bib + "A\nPROOFS\n" + PROSE * 3
    assert leading_refres(post) == len(bib) - 1


def test_regions_and_pages():
    body = PROSE * 40 + "\f" + PROSE * 40 + "\f" + PROSE * 2
    text = body + REF + "\f" + REF + "\f" + "A\nPROOFS\n" + PROSE * 20 + "\f" + PROSE * 20
    r, secs = analyse(("iclr", 2020, "x", text))
    assert r["n_ref_markers"] == 2 and r["pages"] == 6
    assert r["body_pages"] == 2.0  # 2 full pages; the third page has < 300 prose chars before the marker
    assert r["post_pages"] == 2.0
    assert r["body_chars"] == len(body)
    assert secs[0]["title"] == "PROOFS"
