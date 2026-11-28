"""A stale page reads exactly like a fresh one, so the bytes get watched.

`docs/COMPETITOR-CORPUS-SWEEP.md` says 69 of 171 about specific bytes. The receipt
names those bytes; this tool is what notices when they change. Three things have to
hold for the scheduled job to mean anything:

  * drift is named per file, and a removed or added vector counts as drift too;
  * an unchanged corpus exits 0 and prints NO DRIFT (a check that is red every
    night is a check nobody reads);
  * the workflow runs the same command a person runs, so the two cannot disagree.
"""

import json
import os
import re
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(ROOT, "tools", "watch_upstream_corpus.py")
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "upstream-corpus-watch.yml")
DOC = os.path.join(ROOT, "docs", "COMPETITOR-CORPUS-SWEEP.md")
REGISTER = os.path.join(ROOT, "docs", "claims-register.md")


def _read(path):
    """An sdist carries tools and tests but not .github or docs; skip, not fail.

    The point of the skip is that a wheel-only consumer is not asked to prove
    something the sdist never shipped - and CI still runs this with everything
    present, which is where the assertion counts.
    """
    if not os.path.isfile(path):
        pytest.skip("%s is not in this distribution" % os.path.relpath(path, ROOT))
    with open(path, encoding="utf-8") as f:
        return f.read()


def test_the_tool_passes_its_own_selftest():
    out = subprocess.run([sys.executable, TOOL, "--selftest"],
                         capture_output=True, text=True, check=True)
    assert "selftest: identical, changed, removed and added all behave" in out.stdout


def test_it_compares_and_does_not_rewrite():
    """The tool must not mutate the receipt it is watching: that is a human act."""
    with open(TOOL, encoding="utf-8") as f:
        src = f.read()
    # It opens the receipt for reading only, and never for writing.
    assert 'open(RECEIPT, encoding="utf-8")' in src
    assert 'RECEIPT, "w"' not in src and "RECEIPT,\n" not in src
    # It reuses the receipt we committed rather than keeping its own copy.
    assert "corpus-sweep-39daf704.json" in src


def test_the_workflow_runs_the_same_command_and_on_a_schedule():
    wf = _read(WORKFLOW)
    assert "schedule:" in wf and "cron:" in wf
    assert "python tools/watch_upstream_corpus.py" in wf
    assert "workflow_dispatch:" in wf
    # Pinned actions, like every other workflow here.
    assert re.search(r"actions/checkout@[0-9a-f]{40} # v7\.0\.1", wf)
    assert re.search(r"actions/setup-python@[0-9a-f]{40} # v7\.1\.0", wf)


def test_the_receipt_it_watches_is_the_one_the_sweep_uses():
    path = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects",
                        "corpus-sweep-39daf704.json")
    receipt = json.loads(_read(path))
    assert receipt["head"] == "39daf704"
    assert receipt["manifest"]["count"] == 171
    assert receipt["totals"]["n_replayable"] == 69


def test_the_doc_and_the_register_both_say_where_drift_shows_up():
    doc = _read(DOC)
    assert "tools/watch_upstream_corpus.py" in doc
    assert "upstream-corpus-watch.yml" in doc
    assert "NO DRIFT" in doc
    reg = _read(REGISTER)
    assert "watch_upstream_corpus.py" in reg
    assert "NO DRIFT" in reg

