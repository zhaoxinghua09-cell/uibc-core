"""Two snapshots, one answer -- and the digest is what carries it.

The earlier head's receipt deliberately ships no per-file list, so the only thing
tying it to the snapshot we do ship is the manifest digest. That means the digest
has to be recomputed here from 39daf704's 171 entries and compared to the value
recorded for 22764551: if either side drifts, the "they did not change it in
between" sentence loses its evidence and this test has to fail.
"""

import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "compare_corpus_snapshots.py")
OLD = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects",
                   "corpus-sweep-22764551.json")
NEW = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects",
                   "corpus-sweep-39daf704.json")
CMP = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects",
                   "corpus-snapshots-22764551-39daf704.json")
DOC = os.path.join(ROOT, "docs", "COMPETITOR-CORPUS-SWEEP.md")


def _load(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _digest(entries):
    sys.path.insert(0, os.path.join(ROOT, "tools"))
    from compare_corpus_snapshots import manifest_digest
    return manifest_digest(entries)


def test_the_tool_passes_its_own_selftest():
    out = subprocess.run([sys.executable, TOOL, "--selftest"],
                         capture_output=True, text=True, check=True)
    assert "selftest:" in out.stdout


def test_the_old_snapshot_digest_is_the_new_snapshot_list():
    """The bridge: one digest, recomputed from the 171 lines we do ship."""
    old = _load(OLD)
    new = _load(NEW)
    assert old["manifest_digest"] == _digest(new["manifest"]["files"])
    assert old["manifest"]["count"] == 171 == len(new["manifest"]["files"])


def test_the_two_heads_swept_to_the_same_numbers():
    old = _load(OLD)
    new = _load(NEW)
    assert old["head"] == "22764551" and new["head"] == "39daf704"
    for key in ("vectors", "n_replayable", "consistent", "inconsistent", "none"):
        assert old["totals"][key] == new["totals"][key], key
    assert new["totals"]["n_replayable"] == 69
    assert new["totals"]["inconsistent"] == 0


def test_the_comparison_receipt_says_identical_and_names_both_heads():
    c = _load(CMP)
    assert c["verdict"] == "IDENTICAL"
    assert c["changed"] == []
    # Digest-only comparison: it can say "same" but cannot name added or removed
    # files, so those keys must be absent rather than invented as empty lists.
    assert "added" not in c and "removed" not in c
    assert c["method"] == "digest only"
    assert (c["a"], c["b"]) == ("22764551", "39daf704")
    assert c["a_digest"] == c["b_digest"]
    assert len(c["a_digest"]) == 64


def test_the_doc_states_both_heads_and_the_shared_digest():
    with open(DOC, encoding="utf-8") as f:
        doc = f.read()
    for needle in ("22764551", "39daf704", "7169d876",
                   "corpus-snapshots-22764551-39daf704.json", "IDENTICAL"):
        assert needle in doc, needle
