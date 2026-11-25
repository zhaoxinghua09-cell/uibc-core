# -*- coding: utf-8 -*-
"""The vector pack must stay green, and must stay honestly labelled.

`vectors/bid-resolution-v1.json` is hand-authored from the clause text - not
Caict's output - so two things need guarding: that it still runs 22/22 against
this tree, and that nothing quietly relabels it as authoritative.
"""

import json
import pathlib
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
PACK = json.loads((REPO / "vectors" / "bid-resolution-v1.json").read_text(encoding="utf-8"))


def test_all_vectors_pass_against_this_tree():
    import os

    env = dict(os.environ, PYTHONUTF8="1")
    proc = subprocess.run([sys.executable, str(REPO / "tools" / "check_bid_vectors.py"), "--subject", str(REPO)],
                          capture_output=True, text=True, timeout=180, env=env)
    assert proc.returncode == 0, (proc.stdout or "")[-800:] + (proc.stderr or "")[-400:]
    tail = (proc.stdout or "").strip().splitlines()[-1]
    assert "%d/%d passed" % (len(PACK["cases"]), len(PACK["cases"])) in tail


def test_provenance_says_self_authored():
    prov = PACK["provenance"]
    assert "self-authored" in prov["status"]
    assert "NOT published" in prov["status"] or "不是官方" in PACK["about"]


def test_every_case_cites_a_clause_and_explains_itself():
    assert len(PACK["cases"]) == 22
    for case in PACK["cases"]:
        assert case["clause"].startswith("§") or case["clause"].startswith("附录")
        assert len(case["note"]) > 5, case["id"]
        assert case["kind"] in {"envelope", "document", "signature", "trusted", "field"}


def test_ids_are_unique():
    ids = [c["id"] for c in PACK["cases"]]
    assert len(ids) == len(set(ids))
