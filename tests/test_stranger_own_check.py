"""The self-audit has to be able to say no, and has to name what said no."""

import os
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

import stranger_own_check as audit  # noqa: E402


def test_every_check_runs_a_tool_in_this_tree():
    for name, argv in audit.CHECKS:
        assert argv[0].startswith("tools/"), name
        assert os.path.exists(os.path.join(REPO, *argv[0].split("/"))), name


def test_all_pass_is_self_consistent():
    report = audit.run_checks("x", lambda argv, cwd: (0, "ok"))
    assert report["verdict"] == "SELF-CONSISTENT"
    assert report["failed"] == 0
    assert len(report["checks"]) == len(audit.CHECKS)


def test_one_failure_changes_the_verdict_and_names_itself():
    def runner(argv, cwd):
        if "build_reach_ladder" in " ".join(argv):
            return 1, "stale: not a fresh build"
        return 0, "ok"

    report = audit.run_checks("x", runner)
    assert report["verdict"] == "NOT SELF-CONSISTENT"
    failed = [c for c in report["checks"] if c["status"] == "FAIL"]
    assert [c["check"] for c in failed] == ["reach-ladder-picture"]
    assert "stale" in failed[0]["last_line"]


def test_the_receipts_this_audit_depends_on_exist():
    """A missing receipt is a skip for this suite, not a silent pass."""
    receipts = [
        os.path.join(REPO, "docs", "upstream-package", "measurements",
                     "own-corpus-replay.json"),
        os.path.join(REPO, "docs", "upstream-package", "competitor-defects",
                     "corpus-sweep-39daf704.json"),
    ]
    present = [p for p in receipts if os.path.exists(p)]
    if not present:
        pytest.skip("an sdist carries no docs/ receipts")
    assert len(present) == len(receipts)
