"""The parity table has to be checkable, or it is a poster.

Five contracts:

1. the frozen snapshot validates on a clean tree;
2. every audited repository is pinned by a commit and a tarball digest, so the
   audit can be repeated;
3. a score that does not follow from the raw counters is caught, and the
   repository is named;
4. a table that disagrees with the snapshot is caught;
5. this repository's gate still covers the three layers the table claims.
"""

import importlib.util
import json
import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location(
        "competitor_gate_parity", os.path.join(ROOT, "tools", "competitor_gate_parity.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def parity():
    return _load()


@pytest.fixture()
def snap(parity):
    return json.load(open(parity.SNAPSHOT, encoding="utf-8"))


def test_clean_tree_passes(parity):
    assert parity.check(json.load(open(parity.SNAPSHOT, encoding="utf-8"))) == 0


def test_every_audit_is_pinned(snap):
    repos = [r for r in snap["repos"] if "error" not in r]
    assert len(repos) >= 8
    for row in repos:
        assert len(row["sha"]) == 40, row["repo"]
        assert len(row["tarball_sha256"]) == 64, row["repo"]
        assert row["tarball_bytes"] > 0, row["repo"]


def test_score_that_contradicts_its_own_counters_is_caught(parity, snap, capsys):
    target = next(r for r in snap["repos"] if "error" not in r and sum(r["dims"].values()) == 0)
    target["dims"]["D2"] = 2  # no bit-level evidence was found in this repository
    assert parity.check(snap) == 1
    out = capsys.readouterr().out
    assert target["repo"] in out
    assert "scores do not follow" in out


def test_table_that_drifts_from_the_snapshot_is_caught(parity, snap, capsys):
    row = next(r for r in snap["repos"] if "error" not in r)
    row["code_files"] += 17
    assert parity.check(snap) == 1
    assert "does not match the snapshot" in capsys.readouterr().out


def test_gate_still_covers_the_three_layers(parity):
    doc = open(parity.DOC, encoding="utf-8").read()
    for dim, _ in parity.DIMS:
        assert f"| {dim} |" in doc
    assert "10/10" in doc
