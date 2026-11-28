"""A verifier that cannot start is an environment fact, not a corpus verdict.

Measured 2026-11-20 against the shipped 0.4.1 archive: `--verify "definitely-not-a-binary {pkg}"`
raised FileNotFoundError inside `subprocess.run`, the runner died with a traceback and exit 1, and
wrote no receipt — while the page promised exit 3 for a verifier that is not installed. The template
now catches the OSError so the existing preflight turns it into exit 3 with a reason.
"""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE = os.path.join(REPO, "tools", "conformance_bundle_run.py")


def load_template():
    spec = importlib.util.spec_from_file_location("conformance_bundle_run", TEMPLATE)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def runner():
    return load_template()


def test_a_missing_binary_is_reported_not_raised(runner):
    got = runner.call_verifier("definitely-not-a-binary {pkg}", "some/case/dir")
    assert got["unparsed"] is True
    assert got["verifier_unstartable"] is True
    assert got["returncode"] is None
    assert "could not be started" in got["stderr"]


def test_an_unstartable_verifier_never_looks_like_a_verdict(runner):
    got = runner.call_verifier("definitely-not-a-binary {pkg}", "some/case/dir")
    # It must not be recorded as "FAIL with empty checks and parsed output", which is
    # what a 0/36 receipt would read as.
    assert got["checks"] == []
    assert got["unparsed"] is True


def test_the_preflight_names_the_unstartable_case():
    text = open(TEMPLATE, encoding="utf-8").read()
    assert "except OSError" in text
    assert "verifier could not be started" in text
    assert "could not be started at all" in text


def test_the_page_records_what_0_4_1_actually_does():
    page = open(os.path.join(REPO, "docs", "AUDIT-KIT.md"), encoding="utf-8").read()
    assert "exits 1 with a traceback" in page
    assert "predates it" in page


def test_the_shipped_archive_is_not_silently_rebuilt():
    """The fix must not be backported into the pinned bytes; 0.4.1 stays what it was."""
    pin = open(os.path.join(REPO, "anchors", "pins", "uibc-conformance-0.4.1.sha256"),
               encoding="utf-8").read()
    assert "711fa82c9f183066cfae6441a4fe3fc27fcc516b25f2a976cad5e0dd61b5135f" in pin
