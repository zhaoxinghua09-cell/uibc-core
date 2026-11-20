"""The reproduction gate's network guard, controlled rather than assumed."""

import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "reproduce_gate.py")


def test_self_test_passes():
    r = subprocess.run([sys.executable, TOOL, "--self-test"], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "SELF-TEST PASS" in r.stdout


def test_the_receipt_does_not_fail_on_a_machine_with_internet():
    # The bug this test exists for: the gate used to treat "network reachable"
    # as a failed reproduction, so it would greet almost every outsider with
    # REPRODUCTION FAILED while every number matched. Reachability is a property
    # of their machine; attempts are a property of the run.
    src = open(TOOL, encoding="utf-8").read()
    assert 'hard.append(("environment", "network", "network reachable during run"))' not in src
    assert "outbound attempt(s)" in src


def test_the_failure_list_is_built_after_every_step_runs():
    # A previous version appended the convention-axis failure before resetting
    # `hard = []`, silently discarding it. Guard against the reset moving again.
    src = open(TOOL, encoding="utf-8").read()
    reset = src.index("hard = []")
    convention = src.index('hard.append(("convention", "axis"')
    assert convention > reset, "convention failure is appended before the list is reset"
