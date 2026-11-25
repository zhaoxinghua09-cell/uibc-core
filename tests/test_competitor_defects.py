import hashlib
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from tools import check_competitor_vectors as ccv  # noqa: E402

PKG = os.path.join(ROOT, "docs", "upstream-package", "competitor-defects")
UPSTREAM = os.path.join(PKG, "v0.38.0")
COUNTER = os.path.join(PKG, "v0.38.0-counter")


def test_the_rfc_constant_is_the_one_we_think():
    assert ccv.EMPTY_ROOT == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert ccv.EMPTY_ROOT == hashlib.sha256(b"").hexdigest()


def test_vendored_bytes_match_the_recorded_hashes():
    manifest = json.load(open(os.path.join(PKG, "SHA256SUMS.json"), encoding="utf-8"))
    assert manifest["upstream"]["commit"] == "22764551"
    missing = []
    for key, rec in manifest["files"].items():
        path = os.path.join(PKG, *key.split("/"))
        if not os.path.isfile(path):
            missing.append(key)
            continue
        with open(path, "rb") as f:
            body = f.read()
        assert hashlib.sha256(body).hexdigest() == rec["sha256"], "%s drifted" % key
        assert len(body) == rec["bytes"], "%s size drifted" % key
    assert not missing, missing


def test_all_three_upstream_vectors_contradict_their_own_size():
    report = ccv.run(UPSTREAM)
    assert len(report) == 3
    for v in report:
        assert v["agrees"] is False, v["file"]
        assert "root-contradicts-size-zero" in v["forced_code"], v


def test_none_of_the_three_rejections_is_forced_by_arithmetic_alone():
    """The published code cannot be what the numbers force: every file adds the constant."""
    report = ccv.run(UPSTREAM)
    for v in report:
        assert set(v["forced_code"]) - set(v["declared_code"]), v


def test_the_counter_vectors_agree_with_their_published_code():
    report = ccv.run(COUNTER)
    assert len(report) == 3
    for v in report:
        assert v["agrees"] is True, (v["file"], v["forced_code"], v["declared_code"])


def test_the_counter_vectors_reject_for_a_structural_rule():
    """A well-formed empty-tree vector must reject because of a rule, not because of a number."""
    report = ccv.run(COUNTER)
    codes = {v["id"]: v["forced_code"] for v in report}
    assert codes["INC-N-size-zero-counter"] == ["not-included"]
    assert codes["CON-N-size-zero-counter"] == ["schema"]
    assert codes["TOK-N-tree-size-zero-counter"] == ["schema"]


def test_self_test_passes():
    assert ccv.selftest() == 0


def test_the_history_rows_are_tied_to_the_vendored_bytes():
    """A history row that cannot be tied to bytes is a claim, not a record."""
    hist = json.load(open(os.path.join(PKG, "HISTORY.json"), encoding="utf-8"))
    manifest = json.load(open(os.path.join(PKG, "SHA256SUMS.json"), encoding="utf-8"))
    assert hist["empty_tree_root"] == ccv.EMPTY_ROOT
    assert hist["ids"] == ["INC-N-size-zero", "CON-N-old-size-zero", "TOK-N-tree-size-zero"]
    rows = hist["rows"]
    assert len(rows) >= 2
    vendored = [r for r in rows if r["evidence"].startswith("vendored")]
    assert vendored, "at least one row must be tied to vendored bytes"
    for r in vendored:
        assert r["agrees"] == 0 and r["of"] == 3, r
    upstream_keys = [k for k in manifest["files"] if k.startswith("v0.38.0/")]
    assert len(upstream_keys) == 3, upstream_keys


def test_the_documented_table_matches_the_history_file():
    hist = json.load(open(os.path.join(PKG, "HISTORY.json"), encoding="utf-8"))
    page = open(os.path.join(ROOT, "docs", "COMPETITOR-DEFECTS.md"), encoding="utf-8").read()
    for row in hist["rows"]:
        ref = row["upstream_ref"]
        wanted = "v0.38.0" if "v0.38.0" in ref else "v0.37.1"
        assert wanted in page, wanted
        assert row["rejudged"] in page, row["rejudged"]
        assert "%d of %d" % (row["agrees"], row["of"]) in page, row


def test_ci_runs_the_judge():
    """The step exists and calls the tool, so the page cannot outlive the fact."""
    ci_path = os.path.join(ROOT, ".github", "workflows", "ci.yml")
    if not os.path.isfile(ci_path):
        # The sdist does not carry .github/; the workflow is checked in the repository.
        pytest.skip("this archive carries no .github/workflows; the CI step is checked "
                    "where the workflow lives, in the repository")
    ci = open(ci_path, encoding="utf-8").read()
    assert "tools/check_competitor_vectors.py --self-test" in ci
    assert "competitor-defects/v0.38.0-counter" in ci


def test_json_mode_prints_json_and_nothing_else():
    """CI pipes it into json.load; a trailing prose line broke that once."""
    import subprocess

    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_competitor_vectors.py"),
                          "--dir", UPSTREAM, "--json"], capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    assert len(data["dirs"][0]["vectors"]) == 3


def test_the_two_dirs_are_told_apart_the_way_ci_tells_them_apart():
    """CI selects upstream as "ends with /v0.38.0". A plain "v0.38.0/" substring
    test matched nothing, because --dir is echoed without a trailing slash, and
    the step asserted over an empty list. Same selection, checked here."""
    import subprocess

    def is_upstream(d):
        d = d.replace(os.sep, "/").rstrip("/")
        return d.endswith("/v0.38.0") or d == "v0.38.0"

    assert is_upstream(UPSTREAM) and not is_upstream(COUNTER)
    assert not is_upstream("v0.38.0-counter")
    out = subprocess.run([sys.executable, os.path.join(ROOT, "tools", "check_competitor_vectors.py"),
                          "--dir", UPSTREAM, "--dir", COUNTER, "--json"],
                         capture_output=True, text=True, check=True)
    data = json.loads(out.stdout)
    up = [v for dd in data["dirs"] for v in dd["vectors"] if is_upstream(dd["dir"])]
    ct = [v for dd in data["dirs"] for v in dd["vectors"] if "counter" in dd["dir"]]
    assert len(up) == 3 and not any(v["agrees"] for v in up)
    assert len(ct) == 3 and all(v["agrees"] for v in ct)



