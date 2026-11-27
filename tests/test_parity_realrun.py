"""A real run must never move the table, and the record must be self-checking.

Four contracts:

1. every recorded run is at the exact commit the table pins;
2. the counts add up, and the exit code agrees with the failure count - so a
   record cannot quietly turn a red suite into a green one;
3. no record claims to affect the score, and the summary says zero scores moved;
4. the page is generated from the record and states that a green suite is not
   evidence for any of the five dimensions.
"""

import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@pytest.fixture(scope="module")
def rr():
    spec = importlib.util.spec_from_file_location("parity_realrun", os.path.join(ROOT, "tools", "parity_realrun.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def rec(rr):
    return json.load(open(rr.RECORD, encoding="utf-8"))


@pytest.fixture(scope="module")
def snap(rr):
    return json.load(open(rr.SNAPSHOT, encoding="utf-8"))


def test_runs_are_at_the_pinned_commits(rec, snap):
    pinned = {r["repo"]: r["sha"] for r in snap["repos"] if "error" not in r}
    for r in rec["records"]:
        assert pinned[r["repo"]] == r["sha"]


def test_counts_and_exit_code_agree(rec):
    for r in rec["records"]:
        assert r["passed"] + r["failed"] + r["skipped"] == r["tests"]
        assert (r["exit_code"] == 0) == (r["failed"] == 0)


def test_no_run_affects_the_score(rec):
    for r in rec["records"]:
        assert r["affects_score"] is False
    assert rec["score_impact"]["changed_scores"] == 0


def test_page_states_the_run_is_not_evidence(rr, rec):
    page = open(rr.PAGE, encoding="utf-8").read()
    assert "不是加分项" in page
    for r in rec["records"]:
        assert "`%s`" % r["repo"] in page
    assert rr.check() == 0


def test_check_refuses_a_record_that_moves_the_score(rr, rec, capsys, tmp_path, monkeypatch):
    # Same trap as test_refs_check: rewriting the tracked record and putting it
    # back leaves CRLF in the working copy on Windows. Use a copy.
    bad = json.loads(json.dumps(rec))
    bad["records"][0]["affects_score"] = True
    copy = tmp_path / "competitor-realrun.json"
    with open(copy, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(bad))
    monkeypatch.setattr(rr, "RECORD", str(copy))
    assert rr.check() == 1
    assert "claims to affect the score" in capsys.readouterr().out
