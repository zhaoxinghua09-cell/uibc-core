"""Our own corpus has to be measured by the ruler we point at everyone else.

`docs/COMPETITOR-CORPUS-SWEEP.md` says 69 of 171 upstream vectors can be replayed
without their code. A ratio like that is worthless next to nothing: if the same
measurement is never turned on our own 63 vectors, the reader has to take our word
for the comparison. These tests pin the three things that make the comparison
honest:

  * the tool folds with the same functions the competitor sweep imports, not
    with a second implementation written to agree with us;
  * all 63 of ours replay and none contradict - or the numbers in the doc are
    wrong and the suite says so;
  * the stored receipt is the one the corpus rebuilds, so a later edit to a
    vector cannot quietly leave the published ratio behind.
"""

import json
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "measure_own_corpus.py")
SWEEP = os.path.join(ROOT, "tools", "sweep_competitor_corpus.py")
RECEIPT = os.path.join(ROOT, "docs", "upstream-package", "measurements",
                       "own-corpus-replay.json")
DOC = os.path.join(ROOT, "docs", "COMPETITOR-CORPUS-SWEEP.md")


def _read(path):
    """An sdist carries tools and tests but not .github or docs; skip, not fail."""
    if not os.path.isfile(path):
        pytest.skip("%s is not in this distribution" % os.path.relpath(path, ROOT))
    with open(path, encoding="utf-8") as f:
        return f.read()


def _run(*args):
    return subprocess.run([sys.executable, TOOL] + list(args), cwd=ROOT,
                          capture_output=True, text=True)


def test_the_tool_passes_its_own_selftest():
    out = _run("--selftest")
    assert out.returncode == 0
    assert "selftest: 14/14" in out.stdout


def test_it_folds_with_the_same_code_the_competitor_sweep_uses():
    # Not "a verifier that agrees with ours": the same functions, imported.
    src = _read(TOOL)
    assert "from tools.verify_rekor_inclusion import" in src, \
        "the own-corpus measure must import the shared fold, not redefine one"
    for name in ("_decomp_incl_proof", "fold", "root_from_consistency_proof"):
        assert name in src
        assert name in _read(SWEEP), \
            "%s is not the one the competitor sweep uses" % name


def test_all_63_of_ours_replay_and_none_contradict():
    if not os.path.isdir(os.path.join(ROOT, "docs", "upstream-package", "scitt-rfc9162", "v1")):
        pytest.skip("the vector package is not in this distribution")
    out = _run("--json")
    assert out.returncode == 0, out.stderr
    r = json.loads(out.stdout)
    t = r["totals"]
    assert t["vectors"] == 63
    assert t["n_replayable"] == 63
    assert t["consistent"] == 63
    assert t["inconsistent"] == 0
    assert t["none"] == 0
    assert r["categories"]["inclusion"]["counts"]["vectors"] == 50
    assert r["categories"]["consistency"]["counts"]["vectors"] == 13


def test_every_root_the_files_state_agrees_with_the_fold():
    if not os.path.isdir(os.path.join(ROOT, "docs", "upstream-package", "scitt-rfc9162", "v1")):
        pytest.skip("the vector package is not in this distribution")
    r = json.loads(_run("--json").stdout)
    t = r["totals"]
    # 57 of 63 state a reconstructed root; the six that do not are the ones where
    # no fold is defined (size 0, an impossible size order, a proof that cannot
    # walk). Those are counted as absent, not as passes.
    assert t["own_reconstruction_stated"] == 57
    assert t["own_reconstruction_agrees"] == 57
    assert t["leaf_digest_stated"] == 50
    assert t["leaf_digest_rebuilt"] == 50


def test_the_stored_receipt_is_the_one_the_corpus_rebuilds():
    _read(RECEIPT)
    out = _run("--check")
    assert out.returncode == 0, out.stdout + out.stderr
    assert "receipt matches the corpus" in out.stdout


def test_the_doc_states_both_ratios_and_names_the_tool():
    doc = _read(DOC)
    assert "tools/measure_own_corpus.py" in doc
    assert "63" in doc and "69" in doc and "171" in doc
    assert "100%" in doc or "63 of 63" in doc

