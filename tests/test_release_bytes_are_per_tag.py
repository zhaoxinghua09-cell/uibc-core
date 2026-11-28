"""The digest list must be the same bytes on a re-run of the same tag.

Measured 2026-11-20: the tag push built `CORPUS-DIGESTS.txt` = 9a3ffbbc..., and a
dispatch of the same tag minutes later produced 60f48c32... . The freeze guard refused
the second upload -- correctly -- but the reason was ours: the lab bundle embeds
`built_utc` / `declared_utc`, the digest list hashes the bundle, so a wall-clock stamp
propagates three files down and makes "the page for this tag" a different byte string
each run. A tag is a fixed commit; its release should be a fixed set of bytes.

`lab_manifest._now()` now honours `SOURCE_DATE_EPOCH`, the same convention
`uibc_core.cli` already uses, and the workflow sets it to the tag's commit time.
"""
import io
import json
import os
import subprocess
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_WORKFLOW = os.path.join(REPO, ".github", "workflows", "release-lab-bundle.yml")
_ARCHIVE = os.path.join(REPO, "conformance", "uibc-conformance-0.4.1.zip")
pytestmark = pytest.mark.skipif(
    not os.path.isfile(_WORKFLOW) or not os.path.isfile(_ARCHIVE),
    reason="needs the workflow file and a published archive; an sdist has neither")
sys.path.insert(0, os.path.join(REPO, "tools"))

import lab_manifest  # noqa: E402


def test_now_honours_source_date_epoch(monkeypatch):
    import datetime
    monkeypatch.setenv("SOURCE_DATE_EPOCH", "1795008087")
    assert lab_manifest._now() == datetime.datetime.fromtimestamp(
        1795008087, datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_now_falls_back_to_the_clock(monkeypatch):
    monkeypatch.delenv("SOURCE_DATE_EPOCH", raising=False)
    assert lab_manifest._now().endswith("Z")


def test_the_workflow_pins_the_epoch_to_the_tag(tmp_path):
    text = io.open(os.path.join(REPO, ".github", "workflows",
                                "release-lab-bundle.yml"), encoding="utf-8").read()
    assert "SOURCE_DATE_EPOCH" in text, (
        "without a fixed epoch the same tag produces a different digest list on a re-run")
    assert "git log -1 --format=%ct" in text


def test_a_bundle_stamps_the_tag_not_the_clock(tmp_path):
    """The bundle's own timestamps follow the fixed epoch."""
    out = tmp_path / "one"
    out.mkdir()
    subprocess.check_call([sys.executable, os.path.join(REPO, "tools", "release_lab_bundle.py"),
                           "--version", "0.4.1", "--out", str(out)], cwd=REPO,
                          env=dict(os.environ, SOURCE_DATE_EPOCH="1795008087"),
                          stdout=subprocess.DEVNULL)
    bundle = json.loads((out / "uibc-lab-bundle-0.4.1.json").read_text(encoding="utf-8"))
    assert bundle["built_utc"].startswith("2026-11-18T13:21:27"), bundle["built_utc"]


def test_the_digest_list_is_per_run_and_the_document_says_so(tmp_path):
    """Half of the page is ours to fix; the other half lives inside the archive.

    The receipt is written by `run.py` inside the archive. Archives built before
    `tools/conformance_bundle_run.py` learned `SOURCE_DATE_EPOCH` cannot be changed
    without rewriting published bytes, so their receipt carries the run time and the
    digest list that covers it differs between runs. AUDIT-KIT has to say this rather
    than imply a per-tag byte identity that the corpus cannot deliver.
    """
    audit = io.open(os.path.join(REPO, "docs", "AUDIT-KIT.md"), encoding="utf-8").read()
    assert "per-run, not per-tag" in audit
    assert "the receipt carries the time the archive ran" in audit


def test_the_digest_list_covers_three_files(tmp_path):
    out = tmp_path / "one"
    out.mkdir()
    env = dict(os.environ, SOURCE_DATE_EPOCH="1795008087")
    subprocess.check_call([sys.executable, os.path.join(REPO, "tools", "release_lab_bundle.py"),
                           "--version", "0.4.1", "--out", str(out)],
                          cwd=REPO, env=env, stdout=subprocess.DEVNULL)
    lines = [l for l in (out / "CORPUS-DIGESTS.txt").read_text(encoding="utf-8").splitlines()
             if l.strip() and not l.strip().startswith("#")]
    assert len(lines) == 3, lines
