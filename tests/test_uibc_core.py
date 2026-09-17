"""uibc-core full test suite (unit + edge cases). Stdlib unittest only.

Covers: canonical serialization, lifecycle state machine L1-L7, verifier
S1-S6, seal signing (v0.2), report discipline, CLI chain, tamper-evidence
and key-substitution behaviours.
"""

import base64
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
from uibc_core.signing import (ALGORITHM, generate_key, key_id, seal_payload,
                               seal_sign, seal_verify)
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


class TestSigning(unittest.TestCase):
    """v0.2 seal signature primitives (archive SS19/SS10-B5)."""

    def setUp(self):
        self.key = generate_key()
        self.identity = {"agent_id": "a", "owner": "o", "version": "1"}
        self.manifest = {"evidence_root": "x" * 64, "status": "SUBMITTED"}

    def test_keygen_random_and_keyid_stable(self):
        k2 = generate_key()
        self.assertNotEqual(self.key, k2)
        self.assertEqual(key_id(self.key), key_id(self.key))
        self.assertNotEqual(key_id(self.key), key_id(k2))
        self.assertEqual(len(key_id(self.key)), 64)

    def test_roundtrip_and_determinism(self):
        s1 = seal_sign(self.key, self.identity, self.manifest)
        s2 = seal_sign(self.key, self.identity, self.manifest)
        self.assertEqual(s1, s2)
        self.assertTrue(seal_verify(self.key, self.identity, self.manifest, s1))

    def test_payload_tamper_detected(self):
        s = seal_sign(self.key, self.identity, self.manifest)
        bad = dict(self.manifest, evidence_root="f" * 64)
        self.assertFalse(seal_verify(self.key, self.identity, bad, s))

    def test_identity_tamper_detected(self):
        s = seal_sign(self.key, self.identity, self.manifest)
        bad = dict(self.identity, owner="attacker")
        self.assertFalse(seal_verify(self.key, bad, self.manifest, s))

    def test_wrong_key_fails(self):
        s = seal_sign(self.key, self.identity, self.manifest)
        self.assertFalse(seal_verify(generate_key(), self.identity, self.manifest, s))

    def test_malformed_signature_fails(self):
        self.assertFalse(seal_verify(self.key, self.identity, self.manifest, "not-base64!!!"))
        self.assertFalse(seal_verify(self.key, self.identity, self.manifest, ""))
        self.assertFalse(seal_verify(self.key, self.identity, self.manifest, None))
        # valid base64 but garbage bytes
        self.assertFalse(seal_verify(self.key, self.identity, self.manifest,
                                     base64.b64encode(b"\x00" * 32).decode()))

    def test_key_not_in_package_material(self):
        # key_id is a one-way digest of the key: recording it is safe
        self.assertNotIn(self.key, seal_payload(self.identity, self.manifest))


class TestSealVerification(unittest.TestCase):
    """Verifier S6: open vs strict mode, forgery + key substitution."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.owner_key = generate_key()
        self.attacker_key = generate_key()
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

    def _seal_with(self, key):
        identity = json.load(open(os.path.join(self.pkg, "identity.json"), encoding="utf-8"))
        manifest = json.load(open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8"))
        sig_dir = os.path.join(self.pkg, "signatures")
        os.makedirs(sig_dir, exist_ok=True)
        with open(os.path.join(sig_dir, "seal.json"), "w", encoding="utf-8") as f:
            json.dump({"algorithm": ALGORITHM, "key_id": key_id(key),
                       "signature": seal_sign(key, identity, manifest)}, f)

    def _s6(self, report):
        return {c["id"]: c["result"] for c in report["checks"]}.get("S6")

    def _detail(self, report):
        return "; ".join(c["detail"] for c in report["checks"] if c["id"] == "S6")

    def test_unsigned_open_passes_skip(self):
        r = verify(self.pkg)
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(self._s6(r), "SKIP")

    def test_unsigned_strict_fails(self):
        r = verify(self.pkg, key=self.owner_key)
        self.assertEqual(r["result"], "FAIL")
        self.assertEqual(self._s6(r), "FAIL")
        self.assertIn("unsigned", self._detail(r))

    def test_signed_owner_key_passes_strict(self):
        self._seal_with(self.owner_key)
        r = verify(self.pkg, key=self.owner_key)
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(self._s6(r), "PASS")

    def test_signed_no_key_inconclusive(self):
        self._seal_with(self.owner_key)
        r = verify(self.pkg)
        self.assertEqual(r["result"], "PASS")  # open mode: integrity only
        self.assertEqual(self._s6(r), "INCONCLUSIVE")

    def test_manifest_forgery_detected_strict(self):
        """THE v0.2 fix: self-consistent forgery (recomputed root) without
        the owner key FAILs strict verification at S6."""
        self._seal_with(self.owner_key)
        m = json.load(open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8"))
        m["evidence_root"] = evidence_root(["forged"])  # recompute everything
        json.dump(m, open(os.path.join(self.pkg, "manifest.json"), "w", encoding="utf-8"))
        r = verify(self.pkg, key=self.owner_key)
        self.assertEqual(r["result"], "FAIL")
        self.assertEqual(self._s6(r), "FAIL")
        self.assertIn("signature invalid", self._detail(r))

    def test_key_substitution_detected_with_owner_key(self):
        """Known boundary: attacker re-signs with their own key. Owner-key
        strict verification catches it (key_id mismatch)."""
        self._seal_with(self.attacker_key)
        r = verify(self.pkg, key=self.owner_key)
        self.assertEqual(r["result"], "FAIL")
        self.assertIn("key mismatch", self._detail(r))

    def test_key_substitution_undetected_with_attacker_key(self):
        """Honest recording of the known boundary: verifying with the
        ATTACKER's own key passes - hence out-of-band key pinning matters."""
        self._seal_with(self.attacker_key)
        r = verify(self.pkg, key=self.attacker_key)
        self.assertEqual(r["result"], "PASS")


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


class TestCLISigning(unittest.TestCase):
    """v0.2 CLI: keygen / submit --key / verify --key end-to-end."""

    def test_keygen_submit_verify_strict(self):
        tmp = tempfile.mkdtemp()
        try:
            pkg = os.path.join(tmp, "s.uibc")
            keyf = os.path.join(tmp, "owner.key")
            py = sys.executable
            root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            env = dict(os.environ, PYTHONPATH=root, PYTHONIOENCODING="utf-8")

            def run(*a):
                return subprocess.run([py, "-m", "uibc_core.cli", *a],
                                      capture_output=True, text=True, env=env)

            ef = os.path.join(tmp, "log.txt")
            with open(ef, "w", encoding="utf-8") as f:
                f.write("data\n")
            self.assertEqual(run("keygen", "--out", keyf).returncode, 0)
            # refuse to overwrite an existing key
            self.assertNotEqual(run("keygen", "--out", keyf).returncode, 0)
            self.assertEqual(run("init", pkg).returncode, 0)
            self.assertEqual(run("register", pkg, "--agent-id", "a", "--owner", "o").returncode, 0)
            self.assertEqual(run("evidence", pkg, "--type", "ACTION", "--file", ef).returncode, 0)
            self.assertEqual(run("submit", pkg, "--key", keyf).returncode, 0)
            self.assertTrue(os.path.isfile(os.path.join(pkg, "signatures", "seal.json")))
            # strict verify passes; tamper then fails; no key = inconclusive
            self.assertEqual(run("verify", pkg, "--key", keyf).returncode, 0)
            with open(os.path.join(pkg, "evidence", "files", "log.txt"), "w", encoding="utf-8") as f:
                f.write("evil\n")
            self.assertEqual(run("verify", pkg, "--key", keyf).returncode, 1)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
