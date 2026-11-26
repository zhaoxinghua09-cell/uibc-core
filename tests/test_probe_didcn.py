"""The platform probe has to be able to say "the letter is now wrong".

A tool that only ever prints OK is not a check. These three tests pin the
directions that matter:

  1. the recorded observations, as committed, pass offline
  2. a record whose "invalid input" rows no longer show 200+success:true
     fails, and the failure names the reason rather than a count
  3. the generated page must carry the count it quotes, the timestamp, and the
     `facts: current` marker -- otherwise a stale page would be quoted silently
"""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools"))

import probe_didcn_platform as probe  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECORD = os.path.join(REPO, "docs", "didcn-probe.json")
PAGE = os.path.join(REPO, "docs", "DIDCN-PROBE.md")


def _rec():
    return json.load(open(RECORD, encoding="utf-8"))


def test_the_recorded_probe_is_consistent():
    problems, verdict = probe.check(_rec())
    assert problems == [], problems
    assert verdict["accepted_as_success"] >= 1
    assert verdict["vc_skipped"] == verdict["accepted_as_success"]


def test_a_record_that_stopped_holding_is_rejected():
    rec = _rec()
    for row in rec["rows"]:
        if row["case"] != "empty string":
            row["success"] = False
            row["code"] = 400
    problems, verdict = probe.check(rec)
    assert verdict["accepted_as_success"] == 0
    assert any("no longer true" in p for p in problems), problems


def test_the_page_quotes_what_the_record_measured():
    rec = _rec()
    verdict = probe.verdict(rec)
    text = open(PAGE, encoding="utf-8").read()
    assert rec["probed_at"] in text
    assert "facts: current" in text
    assert "%d of %d" % (verdict["accepted_as_success"], verdict["invalid_cases"]) in text
    assert "vcVerificationStatus" in text or "vcVerificationStatus" in text.replace("`", "")


def test_one_code_one_agent_is_actually_pressed():
    """GB/Z 185.2 6 d). A check that never resolves anything proves nothing."""
    uni = os.path.join(REPO, "docs", "didcn-uniqueness.json")
    rec = json.load(open(uni, encoding="utf-8"))
    problems, u = probe.check_uniqueness(rec)
    assert problems == [], problems
    assert len(u["repeat"]) >= 1, "no code was resolved twice"
    assert u["holds"] is True

    rec["duplicates"] = ["did:cn:dupe:x"]
    problems, _ = probe.check_uniqueness(rec)
    assert any("appear twice" in p for p in problems), problems
