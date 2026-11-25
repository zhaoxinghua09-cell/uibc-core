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


def test_the_audit_covers_the_receipt_and_its_second_implementation():
    """A gate nobody runs is a gate nobody has. The audit must include both."""
    names = [name for name, _ in audit.CHECKS]
    assert "outsider-receipt" in names
    assert "tree-digest-second-impl" in names
    assert len(names) == len(set(names)) == 10


def test_a_missing_runtime_is_a_skip_not_a_pass():
    """Exit 77 means "not exercised": counted as skipped, never as passed."""
    def runner(argv, cwd):
        if "tree_digest_second_impl" in " ".join(argv):
            return 77, "SKIP: no node binary"
        return 0, "ok"

    report = audit.run_checks("x", runner)
    assert [c["status"] for c in report["checks"] if c["check"] == "tree-digest-second-impl"] == ["SKIP"]
    assert report["skipped"] == 1
    assert report["passed"] == len(audit.CHECKS) - 1
    assert report["verdict"] == "SELF-CONSISTENT"


def test_a_skip_cannot_mask_a_failure():
    def runner(argv, cwd):
        if "tree_digest_second_impl" in " ".join(argv):
            return 77, "SKIP: no node binary"
        if "build_reach_ladder" in " ".join(argv):
            return 1, "stale: not a fresh build"
        return 0, "ok"

    report = audit.run_checks("x", runner)
    assert report["verdict"] == "NOT SELF-CONSISTENT"
    assert report["failed"] == 1
    assert report["skipped"] == 1


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
