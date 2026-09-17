"""uibc-core full test suite (unit + edge cases). Stdlib unittest only.

Covers: canonical serialization, lifecycle state machine L1-L7, verifier
S1-S5, report discipline, CLI chain, tamper-evidence behaviours.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.canonical import canonicalize, evidence_root, hash_file, hash_obj
from uibc_core.lifecycle import validate_lifecycle
from uibc_core.verify import verify
from uibc_core import cli as ucli
from uibc_core import SPEC_VERSION, __version__


def ev(etype, eid, prev=None):
    return {"event_id": eid, "event_type": etype, "agent_id": "a",
            "timestamp": "2026-01-01T00:00:00Z", "actor": "o",
            "payload_hash": None, "previous_event": prev, "signature": None}


class TestCanonical(unittest.TestCase):
    def test_key_order_independence(self):
        self.assertEqual(hash_obj({"a": 1, "b": 2}), hash_obj({"b": 2, "a": 1}))

    def test_whitespace_independence(self):
        raw1 = json.loads('{"a": 1, "b": "x"}')
        raw2 = json.loads('{"a":1,"b":"x"}')
        self.assertEqual(hash_obj(raw1), hash_obj(raw2))

    def test_unicode_stable(self):
        h1 = hash_obj({"note": "有籍·有证·有门禁"})
        h2 = hash_obj(json.loads(json.dumps({"note": "有籍·有证·有门禁"}, ensure_ascii=True)))
        self.assertEqual(h1, h2)

    def test_different_content_different_hash(self):
        self.assertNotEqual(hash_obj({"a": 1}), hash_obj({"a": 2}))

    def test_root_sorted_and_order_free(self):
        r1 = evidence_root(["aa", "bb", "cc"])
        r2 = evidence_root(["cc", "aa", "bb"])
        self.assertEqual(r1, r2)

    def test_crlf_vs_lf_changes_hash(self):
        with tempfile.TemporaryDirectory() as d:
            p1, p2 = os.path.join(d, "a.txt"), os.path.join(d, "b.txt")
            with open(p1, "wb") as f:
                f.write(b"line1\nline2\n")
            with open(p2, "wb") as f:
                f.write(b"line1\r\nline2\r\n")
            self.assertNotEqual(hash_file(p1), hash_file(p2))

    def test_known_limitation_float_forms(self):
        # PROVISIONAL (pre-RFC8785): 1 vs 1.0 serialize differently - documented.
        self.assertNotEqual(hash_obj({"a": 1}), hash_obj({"a": 1.0}))


class TestLifecycle(unittest.TestCase):
    def _chain(self, *types):
        events, prev = [], None
        for i, t in enumerate(types):
            eid = f"e{i}"
            events.append(ev(t, eid, prev))
            prev = eid
        return events

    def test_valid_full_chain(self):
        chain = self._chain("REGISTER", "ACTIVATE", "UPDATE", "SUSPEND",
                            "RESUME", "MIGRATE", "TRANSFER", "DELEGATE", "RETIRE")
        self.assertEqual(validate_lifecycle(chain), [])

    def test_L1_first_must_register(self):
        errs = validate_lifecycle(self._chain("ACTIVATE"))
        self.assertTrue(any("L1" in e for e in errs))

    def test_L2_duplicate_register(self):
        errs = validate_lifecycle(self._chain("REGISTER", "REGISTER"))
        self.assertTrue(any("L2" in e for e in errs))

    def test_L3_unknown_type(self):
        errs = validate_lifecycle(self._chain("REGISTER", "TELEPORT"))
        self.assertTrue(any("L3" in e for e in errs))

    def test_L4_broken_chain(self):
        events = self._chain("REGISTER", "ACTIVATE")
        events[1]["previous_event"] = "wrong"
        errs = validate_lifecycle(events)
        self.assertTrue(any("L4" in e for e in errs))

    def test_L5_duplicate_id(self):
        events = self._chain("REGISTER", "ACTIVATE")
        events[1]["event_id"] = events[0]["event_id"]
        errs = validate_lifecycle(events)
        self.assertTrue(any("L5" in e for e in errs))

    def test_L6_resume_without_suspend(self):
        errs = validate_lifecycle(self._chain("REGISTER", "RESUME"))
        self.assertTrue(any("L6" in e for e in errs))

    def test_L6_resume_after_suspend_ok(self):
        self.assertEqual(validate_lifecycle(
            self._chain("REGISTER", "SUSPEND", "RESUME")), [])

    def test_L7_event_after_terminal(self):
        errs = validate_lifecycle(self._chain("REGISTER", "REVOKE", "ACTIVATE"))
        self.assertTrue(any("L7" in e for e in errs))

    def test_empty_events_vacuously_valid(self):
        self.assertEqual(validate_lifecycle([]), [])


class TestVerifier(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pkg = os.path.join(self.tmp, "p.uibc")
        ucli.cmd_init(type("A", (), {"path": self.pkg})())
        ns = type("A", (), {"path": self.pkg, "agent_id": "a1", "owner": "o",
                            "agent_type": "t", "version": "1"})
        ucli.cmd_register(ns)
        src = os.path.join(self.tmp, "e.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("evidence body\n")
        ucli.cmd_evidence(type("A", (), {"path": self.pkg, "type": "ACTION",
                                         "file": src, "media_type": "text/plain",
                                         "note": ""})())
        ucli.cmd_submit(type("A", (), {"path": self.pkg})())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def _checks(self, report):
        return {c["id"]: c["result"] for c in report["checks"]}

    def test_clean_pass_and_discipline(self):
        r = verify(self.pkg)
        self.assertEqual(r["result"], "PASS")
        for field in ("scope", "limitations", "checked", "not_checked", "statement"):
            self.assertIn(field, r)
        self.assertIn("No violation was detected", r["statement"])

    def test_skeleton_no_evidence_fails_S5(self):
        pkg2 = os.path.join(self.tmp, "skeleton.uibc")
        ucli.cmd_init(type("A", (), {"path": pkg2})())
        r = verify(pkg2)
        self.assertEqual(r["result"], "FAIL")
        self.assertEqual(self._checks(r)["S5"], "INCONCLUSIVE")

    def test_missing_files_S1(self):
        pkg2 = os.path.join(self.tmp, "empty.uibc")
        os.makedirs(pkg2)
        r = verify(pkg2)
        self.assertEqual(self._checks(r)["S1"], "FAIL")

    def test_identity_mismatch_S2(self):
        m = json.load(open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8"))
        m["agent_id"] = "someone-else"
        json.dump(m, open(os.path.join(self.pkg, "manifest.json"), "w", encoding="utf-8"))
        self.assertEqual(self._checks(verify(self.pkg))["S2"], "FAIL")

    def test_unknown_evidence_type_S4(self):
        ip = os.path.join(self.pkg, "evidence", "index.json")
        idx = json.load(open(ip, encoding="utf-8"))
        idx["entries"][0]["type"] = "GOSSIP"
        json.dump(idx, open(ip, "w", encoding="utf-8"))
        self.assertEqual(self._checks(verify(self.pkg))["S4"], "FAIL")

    def test_tamper_content_S4_root_inconclusive(self):
        ep = os.path.join(self.pkg, "evidence", "files", "e.txt")
        with open(ep, "w", encoding="utf-8") as f:
            f.write("tampered\n")
        c = self._checks(verify(self.pkg))
        self.assertEqual(c["S4"], "FAIL")
        self.assertEqual(c["S5"], "INCONCLUSIVE")

    def test_unicode_evidence_pass(self):
        pkg2 = os.path.join(self.tmp, "uni.uibc")
        ucli.cmd_init(type("A", (), {"path": pkg2})())
        ucli.cmd_register(type("A", (), {"path": pkg2, "agent_id": "有籍-agent",
                                         "owner": "owner", "agent_type": "t",
                                         "version": "1"})())
        src = os.path.join(self.tmp, "u.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("凡自治之物\n")
        ucli.cmd_evidence(type("A", (), {"path": pkg2, "type": "OUTPUT",
                                         "file": src, "media_type": "text/plain",
                                         "note": "中文"})())
        ucli.cmd_submit(type("A", (), {"path": pkg2})())
        self.assertEqual(verify(pkg2)["result"], "PASS")

    def test_duplicate_filename_autorenamed(self):
        src = os.path.join(self.tmp, "e.txt")
        ucli.cmd_evidence(type("A", (), {"path": self.pkg, "type": "INPUT",
                                         "file": src, "media_type": "text/plain",
                                         "note": ""})())
        # re-seal: a new evidence entry after sealing invalidates the root,
        # so the package must be re-submitted before verify (by design).
        ucli.cmd_submit(type("A", (), {"path": self.pkg})())
        self.assertEqual(verify(self.pkg)["result"], "PASS")

    def test_stale_seal_fails_S5(self):
        src = os.path.join(self.tmp, "f.txt")
        with open(src, "w", encoding="utf-8") as fh:
            fh.write("late evidence\n")
        ucli.cmd_evidence(type("A", (), {"path": self.pkg, "type": "INPUT",
                                         "file": src, "media_type": "text/plain",
                                         "note": ""})())
        # deliberately NOT re-sealing: stale manifest root must FAIL
        c = self._checks(verify(self.pkg))
        self.assertEqual(c["S5"], "FAIL")


class TestCLIChain(unittest.TestCase):
    def test_full_chain_exit_codes(self):
        tmp = tempfile.mkdtemp()
        try:
            pkg = os.path.join(tmp, "c.uibc")
            py = sys.executable
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env = dict(os.environ, PYTHONPATH=root, PYTHONIOENCODING="utf-8")
            def run(*a):
                return subprocess.run([py, "-m", "uibc_core.cli", *a],
                                      capture_output=True, text=True, env=env)
            ef = os.path.join(tmp, "log.txt")
            with open(ef, "w", encoding="utf-8") as f:
                f.write("data\n")
            self.assertEqual(run("init", pkg).returncode, 0)
            self.assertEqual(run("register", pkg, "--agent-id", "a", "--owner", "o").returncode, 0)
            self.assertEqual(run("event", pkg, "--type", "ACTIVATE").returncode, 0)
            self.assertEqual(run("evidence", pkg, "--type", "ACTION", "--file", ef).returncode, 0)
            self.assertEqual(run("submit", pkg).returncode, 0)
            self.assertEqual(run("verify", pkg).returncode, 0)
            self.assertEqual(run("inspect", pkg).returncode, 0)
            # re-init same path must fail
            self.assertNotEqual(run("init", pkg).returncode, 0)
            # unknown event type recorded but verify must FAIL at S3
            pkg2 = os.path.join(tmp, "c2.uibc")
            run("init", pkg2)
            run("register", pkg2, "--agent-id", "a", "--owner", "o")
            run("event", pkg2, "--type", "TELEPORT")
            run("submit", pkg2)
            self.assertEqual(run("verify", pkg2).returncode, 1)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
