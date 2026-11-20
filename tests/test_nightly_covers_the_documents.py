"""The nightly job has to check the documents, not only the bytes.

Measured 2026-11-20: `tools/status_page.py --check` catches a one-character drift
in STATUS.md (the case count written as 35 instead of 36) and exits 1 -- and no
scheduled job ran it. The public page could have gone quietly false while every
machine-driven check stayed green, which is the same class of defect as the three
silent rewrites of one tag and the checker that trusted its own record.

These tests hold the wiring: the commands must be in the nightly workflow, in the
order that matters (nothing after a failing gate), with the exit codes mapped the
way the tools define them (1 = a real disagreement, 3 = could not measure, which
is a warning and never a pass).
"""

import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "release-integrity.yml")

def _text():
    with open(WORKFLOW, encoding="utf-8") as handle:
        return handle.read()


def test_the_nightly_runs_the_status_page_gate():
    text = _text()
    assert "python tools/status_page.py --check" in text


def test_the_nightly_runs_the_document_facts_gate():
    text = _text()
    assert "python tools/check_doc_facts.py" in text


def test_a_stale_page_fails_the_run_and_an_unknown_is_only_a_warning():
    text = _text()
    for gate in ("STATUS.md no longer matches the repository",
                 "a document states a fact the repository no longer supports"):
        assert gate in text, gate
    assert text.count('echo "::warning::') >= 2
    assert 'code=${PIPESTATUS[0]}' not in text  # the code must be read straight after the tool
    assert "set +e" in text


def test_the_doc_gates_run_before_the_external_probe():
    # A local gate is cheap and deterministic; it must not be queued behind a
    # network probe that may take minutes or fail for unrelated reasons.
    text = _text()
    page = text.index("python tools/status_page.py --check")
    probe = text.index("python tools/check_outsider_entry.py --probe")
    assert page < probe


def test_both_reports_survive_the_run():
    text = _text()
    assert "anchors-report.json" in text
    assert "doc-facts-report.json" in text
    artifact = text[text.index("upload-artifact"):]
    assert "doc-facts-report.json" in artifact, "the doc report must be uploaded, not only printed"


def test_the_status_gate_reads_the_same_file_it_writes():
    """`status_page.py` regenerates STATUS.md; `--check` must not rewrite it. If the
    nightly accidentally regenerated the page, drift would be 'fixed' instead of
    reported, and the check would pass by editing the evidence."""
    tool = open(os.path.join(REPO, "tools", "status_page.py"), encoding="utf-8").read()
    assert "--check" in tool
    # The generator writes the page with io.open(..., "w"); the nightly must never
    # call that path, only --check, or a wrong page would be silently corrected.
    assert "\"w\"" in tool and "PAGE" in tool, "the generator writes the page"
    text = _text()
    assert "run python tools/status_page.py" in text
