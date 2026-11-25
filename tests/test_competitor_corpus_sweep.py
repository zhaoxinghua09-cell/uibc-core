"""The corpus sweep's numbers are pinned, and its honesty tests with it.

The sweep in `tools/sweep_competitor_corpus.py` decides two things per vector:
whether the file can be replayed without the upstream code, and whether its own
numbers agree with the verdict it publishes. Both numbers are claims about
somebody else's corpus, so both are pinned here: if either moves, a human has to
re-run the sweep and say so in the doc, rather than the page quietly following
whatever the last build produced.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects",
                       "corpus-sweep-39daf704.json")
DOC = os.path.join(ROOT, "docs", "COMPETITOR-CORPUS-SWEEP.md")
VENDORED = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects", "v0.38.0")


def _receipt():
    with open(RECEIPT, encoding="utf-8") as f:
        return json.load(f)


def test_the_tool_still_passes_its_own_selftest():
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "sweep_competitor_corpus.py"),
                          "--selftest"], capture_output=True, text=True, check=True)
    assert "selftest: 13/13" in out.stdout


def test_the_totals_are_the_totals():
    r = _receipt()
    t = r["totals"]
    assert t["vectors"] == 171
    assert t["n_replayable"] == 60
    assert t["consistent"] == 60
    assert t["inconsistent"] == 0
    assert t["none"] == 111
    # The two halves have to add up, and so do the published expectations.
    assert t["n_replayable"] + t["none"] == t["vectors"]
    assert t["n_accept_published"] + t["n_reject_published"] == t["vectors"]


def test_each_category_adds_to_its_own_total_and_to_the_whole():
    r = _receipt()
    seen = 0
    for kind, c in r["categories"].items():
        n = c["counts"]
        assert n["replayable"] + (n["vectors"] - n["replayable"]) == n["vectors"]
        assert n["consistent"] + n["inconsistent"] + (n["vectors"] - n["replayable"]) == n["vectors"]
        seen += n["vectors"]
    assert seen == r["totals"]["vectors"]


def test_the_manifest_digests_every_file_once():
    m = _receipt()["manifest"]
    paths = [f["path"] for f in m["files"]]
    assert m["count"] == 171 == len(paths)
    assert len(set(paths)) == len(paths)
    assert all(f["sha256"] and len(f["sha256"]) == 64 for f in m["files"])


def test_the_vendored_three_are_the_same_bytes_as_in_the_swept_corpus():
    """The three files we ship and the 171 we only digest must not drift apart."""
    import hashlib

    files = {f["sha256"]: f for f in _receipt()["manifest"]["files"]}
    for name in ("INC-N-size-zero.json", "CON-N-old-size-zero.json", "TOK-N-tree-size-zero.json"):
        path = os.path.join(VENDORED, name)
        with open(path, "rb") as fh:
            digest = hashlib.sha256(fh.read()).hexdigest()
        assert digest in files, name
        assert files[digest]["bytes"] == os.path.getsize(path), name


def test_the_sweep_is_not_a_uniform_pass():
    """A sweep that only ever says "consistent" would be worthless. The receipt
    has to show the 111 it could not replay, per category, with a reason."""
    r = _receipt()
    for kind in ("token", "chain", "canonical"):
        c = r["categories"][kind]
        assert c["counts"]["replayable"] == 0
        assert c["why_not_numeric"], kind
    assert r["categories"]["token"]["counts"]["vectors"] == 87


def test_the_doc_carries_the_same_numbers():
    with open(DOC, encoding="utf-8") as f:
        doc = f.read()
    for needle in ("171", "60（35%）", "111", "0 条出现", "39daf704"):
        assert needle in doc, needle
