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
