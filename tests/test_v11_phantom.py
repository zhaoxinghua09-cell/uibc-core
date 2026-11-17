"""Phantom-entry ledger: the gate must record what it refused.

These tests pin the property that makes the ledger worth having at all: if
someone edits, deletes, reorders or truncates a decision after the fact, the
recomputation notices. They also pin the honest limit - an empty and a deleted
log are indistinguishable, so the verifier answers INCONCLUSIVE, not PASS.
"""
import json
import os
import tempfile
import unittest

from uibc_core.phantom import (GENESIS, PhantomLog, request_digest,
                               verify_phantom_log)


def _append(log, n=1, decision="DENY"):
    for i in range(n):
        log.append(decision=decision, reason="policy: refund > 100",
                   rule_id="GR-001", request_digest=request_digest({"i": i}),
                   executed=False, at="2026-11-17T00:00:0%dZ" % i,
                   subject="shim-agent")


class TestPhantomLog(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="phantom-")
        self.path = os.path.join(self.tmp, "phantom.jsonl")

    def test_append_and_verify(self):
        log = PhantomLog(self.path)
        self.assertEqual(log.head, GENESIS)
        _append(log, 3)
        r = verify_phantom_log(self.path)
        self.assertEqual(r["result"], "PASS", r["problems"])
        self.assertEqual(r["entries"], 3)
        self.assertEqual(r["phantom_entries"], 3)
        self.assertEqual(len(r["head"]), 64)   # bare sha256 hex, as hash_obj returns

    def test_edited_entry_is_detected(self):
        log = PhantomLog(self.path)
        _append(log, 3)
        lines = open(self.path, encoding="utf-8").read().splitlines()
        bad = json.loads(lines[1])
        bad["reason"] = "policy: allowed"          # rewrite the history
        lines[1] = json.dumps(bad, ensure_ascii=False, sort_keys=True)
        open(self.path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        r = verify_phantom_log(self.path)
        self.assertEqual(r["result"], "FAIL")
        self.assertTrue(any("content edited" in p for p in r["problems"]), r["problems"])

    def test_deleted_entry_is_detected(self):
        log = PhantomLog(self.path)
        _append(log, 3)
        lines = open(self.path, encoding="utf-8").read().splitlines()
        del lines[1]
        open(self.path, "w", encoding="utf-8", newline="\n").write("\n".join(lines) + "\n")
        r = verify_phantom_log(self.path)
        self.assertEqual(r["result"], "FAIL")
        self.assertTrue(any("sequence gap" in p for p in r["problems"]), r["problems"])

    def test_absent_log_is_inconclusive_not_pass(self):
        r = verify_phantom_log(os.path.join(self.tmp, "never-written.jsonl"))
        self.assertEqual(r["result"], "INCONCLUSIVE")
        self.assertEqual(r["entries"], 0)

    def test_executed_and_phantom_are_distinguished(self):
        log = PhantomLog(self.path)
        log.append(decision="ALLOW", reason="PASS + anchored", rule_id="GR-000",
                   request_digest=request_digest({"ok": 1}), executed=True,
                   at="2026-11-17T00:00:01Z")
        _append(log, 1, decision="DENY")
        r = verify_phantom_log(self.path)
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(r["entries"], 2)
        self.assertEqual(r["phantom_entries"], 1)

    def test_unknown_decision_is_refused(self):
        log = PhantomLog(self.path)
        with self.assertRaises(ValueError):
            log.append(decision="MAYBE", reason="", rule_id="", request_digest="",
                       executed=False, at="")


if __name__ == "__main__":
    unittest.main()
