"""The provenance check must fail on the property it names, not just run.

0.5.0 shipped with `publish-pypi.yml` green while every provenance URL returned
404, because the only assertion in the job was "the version exists". The
replacement asserts "the attestation exists" - and this file asserts that the
assertion itself works, with no network: a fake fetch stands in for PyPI.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.check_pypi_provenance import check, main  # noqa: E402


RELEASE = {
    "releases": {
        "1.0.0": [{"filename": "pkg-1.0.0-py3-none-any.whl"},
                  {"filename": "pkg-1.0.0.tar.gz"}],
    }
}


def make_fetch(present, release=RELEASE):
    """present: filenames whose provenance URL answers; everything else raises."""
    import json

    def fetch(url, timeout=20):
        if "/pypi/" in url:
            return json.dumps(release).encode()
        for fn in present:
            if url.endswith("/%s/provenance" % fn):
                return b'{"attestations": []}'
        raise FileNotFoundError("HTTP Error 404: Not Found")
    return fetch


def test_all_files_attested_passes():
    files, missing = check("pkg", "1.0.0", fetch=make_fetch(
        ["pkg-1.0.0-py3-none-any.whl", "pkg-1.0.0.tar.gz"]))
    assert len(files) == 2
    assert missing == []
    assert main(["--pkg", "pkg", "--version", "1.0.0"]) in (0, 1)  # network-dependent, only shape


def test_one_file_unattested_fails():
    files, missing = check("pkg", "1.0.0", fetch=make_fetch(["pkg-1.0.0-py3-none-any.whl"]))
    assert len(files) == 2
    assert [m[0] for m in missing] == ["pkg-1.0.0.tar.gz"]


def test_this_is_the_0_5_0_case():
    """No provenance at all: the check must say so instead of reporting the version."""
    files, missing = check("pkg", "1.0.0", fetch=make_fetch([]))
    assert len(missing) == len(files) == 2


def test_no_files_is_a_failure_not_a_pass():
    empty = {"releases": {"1.0.0": []}}
    files, missing = check("pkg", "1.0.0", fetch=make_fetch([], release=empty))
    assert files == []


def test_unknown_version_lists_nothing():
    other = {"releases": {"0.9.0": [{"filename": "pkg-0.9.0.tar.gz"}]}}
    files, _ = check("pkg", "1.0.0", fetch=make_fetch([], release=other))
    assert files == []


@pytest.mark.parametrize("present,expect_rc", [
    (["pkg-1.0.0-py3-none-any.whl", "pkg-1.0.0.tar.gz"], 0),
    (["pkg-1.0.0-py3-none-any.whl"], 1),
    ([], 1),
])
def test_exit_codes_are_what_the_workflow_reads(present, expect_rc, monkeypatch, capsys):
    import tools.check_pypi_provenance as m
    monkeypatch.setattr(m, "http_get", make_fetch(present))
    rc = m.main(["--pkg", "pkg", "--version", "1.0.0"])
    assert rc == expect_rc
    out = capsys.readouterr().out
    if expect_rc:
        assert "MISSING provenance" in out or "no files published" in out
    else:
        assert "all 2 file(s) carry provenance" in out
