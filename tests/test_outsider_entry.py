"""The outsider's entry point has to be a real file, reachable by a real URL.

Measured 2026-20-11: `docs/AUDIT-KIT.md` told a reader who had cloned nothing that the
archive "is self-contained" without saying where to get it, and the newest release carries
`uibc-conformance-0.4.0.zip` — a different corpus under a different version. These tests
hold the document, the URL and the pin together so they cannot drift apart silently.
"""
import os
import shutil
import sys
import tempfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def _declared_version():
    import re
    text = open(os.path.join(REPO, "pyproject.toml"), encoding="utf-8").read()
    return re.search(r'version *= *"([^"]+)"', text).group(1)


_VER = _declared_version()

sys.path.insert(0, os.path.join(REPO, "tools"))

import check_outsider_entry as entry  # noqa: E402


def clone_repo(tmp_path):
    """A copy of just the files the checker reads, so tests can corrupt them."""
    for rel in ("README.md", os.path.join("docs", "AUDIT-KIT.md"),
                os.path.join("anchors", "pins", "uibc-conformance-%s.sha256" % _VER),
                "conformance"):
        src = os.path.join(REPO, rel)
        dst = os.path.join(str(tmp_path), rel)
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        if os.path.isdir(src):
            shutil.copytree(src, dst)
        else:
            shutil.copy2(src, dst)
    return str(tmp_path)


def run_checker(repo, monkeypatch, *args):
    monkeypatch.setattr(entry, "REPO", repo)
    return entry.main(list(args))


def test_the_real_repository_passes(monkeypatch):
    assert run_checker(REPO, monkeypatch) == 0


def test_the_documented_url_is_the_pinned_archive(tmp_path, monkeypatch):
    repo = clone_repo(tmp_path)
    monkeypatch.setattr(entry, "REPO", repo)
    pin = entry.read_pin(_VER)
    assert pin["path"].endswith("uibc-conformance-%s.zip" % _VER)
    assert entry.RAW_URL.endswith(pin["path"].split("/")[-1])
    assert "/zhaoxinghua09-cell/uibc-core/" in entry.RAW_URL


def test_a_tampered_archive_is_refused(tmp_path, monkeypatch):
    repo = clone_repo(tmp_path)
    archive = os.path.join(repo, "conformance", ("uibc-conformance-%s.zip" % _VER))
    with open(archive, "ab") as fh:
        fh.write(b"\x00")
    assert run_checker(repo, monkeypatch) == 1


def test_a_pin_naming_a_different_archive_is_refused(tmp_path, monkeypatch):
    repo = clone_repo(tmp_path)
    pin = os.path.join(repo, "anchors", "pins", "uibc-conformance-%s.sha256" % _VER)
    # the pin is "<sha256>  <path>"; flipping one hex digit must be refused
    import re
    text = open(pin, encoding="utf-8").read()
    digest = re.search(r"([0-9a-f]{64})", text)
    d = digest.group(1)
    text = text.replace(d, ("0" if d[0] != "0" else "1") + d[1:], 1)
    open(pin, "w", encoding="utf-8", newline="\n").write(text)
    assert run_checker(repo, monkeypatch) == 1


def test_documents_that_omit_the_url_are_refused(tmp_path, monkeypatch):
    repo = clone_repo(tmp_path)
    for rel in ("README.md", os.path.join("docs", "AUDIT-KIT.md")):
        path = os.path.join(repo, rel)
        text = open(path, encoding="utf-8").read().replace(entry.RAW_URL, "the usual place")
        open(path, "w", encoding="utf-8", newline="\n").write(text)
    assert run_checker(repo, monkeypatch) == 1


def test_a_document_pointing_at_another_versions_asset_is_refused(tmp_path, monkeypatch):
    repo = clone_repo(tmp_path)
    readme = os.path.join(repo, "README.md")
    text = open(readme, encoding="utf-8").read()
    text += ("\nOr: https://github.com/zhaoxinghua09-cell/uibc-core/releases/download/"
             "v0.4.0/uibc-conformance-0.4.0.zip\n")
    open(readme, "w", encoding="utf-8", newline="\n").write(text)
    assert run_checker(repo, monkeypatch) == 1


def test_the_release_asset_must_be_named(tmp_path, monkeypatch):
    repo = clone_repo(tmp_path)
    for rel in ("README.md", os.path.join("docs", "AUDIT-KIT.md")):
        path = os.path.join(repo, rel)
        text = open(path, encoding="utf-8").read().replace(entry.RELEASE_URL, "the release page")
        open(path, "w", encoding="utf-8", newline="\n").write(text)
    assert run_checker(repo, monkeypatch) == 1


def test_a_missing_pin_exits_three_not_one(tmp_path, monkeypatch):
    repo = clone_repo(tmp_path)
    os.unlink(os.path.join(repo, "anchors", "pins", "uibc-conformance-%s.sha256" % _VER))
    assert run_checker(repo, monkeypatch) == 3


def test_an_unreachable_network_is_unmeasured_not_a_failure(monkeypatch):
    """A dropped connection must not be reported as a broken path."""
    calls = {"n": 0}

    def failing_probe(pin, attempts=3):
        calls["n"] += 1
        print("unmeasured - simulated")
        return None, None

    monkeypatch.setattr(entry, "probe", failing_probe)
    assert entry.main(["--probe"]) == 3
    assert calls["n"] == 1


def test_a_probe_that_serves_other_bytes_is_a_failure(monkeypatch):
    def wrong_probe(pin, attempts=3):
        return [("the URL served 1 bytes, the pin says %s" % os.path.basename(entry.PIN)) if False else "the URL served 1 bytes"], 1

    monkeypatch.setattr(entry, "probe", wrong_probe)
    assert entry.main(["--probe"]) == 1


@pytest.mark.skipif(shutil.which("curl") is None, reason="no curl to exercise the reader's path")
def test_the_probe_prefers_curl(monkeypatch):
    """The documents tell readers to use curl, so the probe does too."""
    seen = {}

    def fake_run(cmd, **kwargs):
        seen["cmd"] = cmd

        class P:
            returncode = 1
            stderr = "simulated failure"
            stdout = ""

        return P()

    import subprocess
    monkeypatch.setattr(subprocess, "run", fake_run)
    reasons, served = entry.probe(entry.read_pin(_VER), attempts=1)
    assert reasons is None and served is None
    assert os.path.basename(seen["cmd"][0]).lower() in ("curl", "curl.exe")
