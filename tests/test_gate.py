"""Gate decision-layer tests (task G2). Stdlib unittest only.

Decision contract (docs/governance.md section 7):
  ALLOW            exit 0   verify PASS, no overlays
  ALLOW_DISPUTED   exit 0   verify PASS + valid dispute (flagged, human decides)
  DENY             exit 2   verify FAIL or valid revocation
  HOLD             exit 3   anything unverifiable (unverified revocation, bad overlay)
"""

import json
import os
import shutil
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import cli as ucli
from uibc_core.gate import gate
from uibc_core.signing import generate_key, key_id


def _canonical_sig_payload(body: dict) -> bytes:
    core = {k: v for k, v in body.items() if k != "signature"}
    return json.dumps(core, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _make_pkg(tmp, name="g.uibc", sign_key=None, n_evidence=2):
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "gate-agent", "owner": "gate-owner",
        "agent_type": "software-agent", "version": "1"})())
    src = os.path.join(tmp, "ev.txt")
    with open(src, "w", encoding="utf-8") as f:
        f.write("gate evidence\n")
    for i in range(n_evidence):
        ucli.cmd_evidence(type("A", (), {
            "path": pkg, "type": "ACTION", "file": src,
            "media_type": "text/plain", "note": f"n{i}"})())
    kf = None
    if sign_key is not None:
        kf = os.path.join(tmp, name + ".key")
        with open(kf, "w", encoding="ascii") as f:
            f.write(sign_key.hex())
        ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    else:
        ucli.cmd_submit(type("A", (), {"path": pkg, "key": None})())
    return pkg, kf


def _read_manifest_root(pkg):
    with open(os.path.join(pkg, "manifest.json"), "r", encoding="utf-8") as f:
        return json.load(f)["evidence_root"]


def _write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False)
    return path


class GateTests(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # 1. clean signed package, strict key -> ALLOW
    def test_01_clean_signed_strict_allows(self):
        key = generate_key()
        pkg, _ = _make_pkg(self.tmp, sign_key=key)
        r = gate(pkg, key=key)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["verify_result"], "PASS")

    # 2. clean unsigned package, open mode -> ALLOW
    def test_02_clean_unsigned_open_allows(self):
        pkg, _ = _make_pkg(self.tmp)
        r = gate(pkg)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["exit_code"], 0)

    # 3. tampered evidence -> DENY exit 2
    def test_03_tampered_denies(self):
        pkg, _ = _make_pkg(self.tmp)
        target = os.path.join(pkg, "evidence", "files", "ev.txt")
        with open(target, "a", encoding="utf-8") as f:
            f.write("TAMPERED\n")
        r = gate(pkg)
        self.assertEqual(r["decision"], "DENY")
        self.assertEqual(r["exit_code"], 2)

    # 4. unsigned package + strict key -> DENY (S6)
    def test_04_unsigned_strict_denies(self):
        key = generate_key()
        pkg, _ = _make_pkg(self.tmp)
        r = gate(pkg, key=key)
        self.assertEqual(r["decision"], "DENY")
        self.assertEqual(r["exit_code"], 2)
        ids = {c["id"]: c["result"] for c in r["verify_report"]["checks"]}
        self.assertEqual(ids["S6"], "FAIL")

    # 5. valid signed revocation -> DENY REVOKED (R2)
    def test_05_valid_revocation_denies(self):
        key = generate_key()
        pkg, _ = _make_pkg(self.tmp, sign_key=key)
        import base64, hashlib, hmac
        root = _read_manifest_root(pkg)
        body = {
            "revocation_id": "r-test-1",
            "target_root": root,
            "reason_code": "KEY_COMPROMISED",
            "key_id": key_id(key),
            "algorithm": "HMAC-SHA256",
            "revoked_at": "2026-09-18T00:00:00Z",
        }
        sig = base64.b64encode(
            hmac.new(key, _canonical_sig_payload(body), hashlib.sha256).digest()
        ).decode("ascii")
        rp = _write_json(os.path.join(self.tmp, "rev.json"), dict(body, signature=sig))
        r = gate(pkg, key=key, revocation_path=rp)
        self.assertEqual(r["decision"], "DENY")
        self.assertEqual(r["revocation"]["status"], "REVOKED")
        self.assertEqual(r["exit_code"], 2)

    # 6. revocation without key -> HOLD (never silently trusted)
    def test_06_unverified_revocation_holds(self):
        pkg, _ = _make_pkg(self.tmp)
        root = _read_manifest_root(pkg)
        rp = _write_json(os.path.join(self.tmp, "rev.json"), {
            "revocation_id": "r-test-2", "target_root": root,
            "reason_code": "OWNER_REQUEST", "key_id": "f" * 64,
            "signature": "AAAA", "revoked_at": "2026-09-18T00:00:00Z"})
        r = gate(pkg, revocation_path=rp)
        self.assertEqual(r["decision"], "HOLD")
        self.assertEqual(r["exit_code"], 3)
        self.assertEqual(r["revocation"]["status"], "UNVERIFIABLE")

    # 7. valid dispute -> ALLOW_DISPUTED exit 0 (flagged, never auto-denied)
    def test_07_dispute_flags_not_blocks(self):
        pkg, _ = _make_pkg(self.tmp)
        root = _read_manifest_root(pkg)
        dp = _write_json(os.path.join(self.tmp, "disp.json"), {
            "dispute_id": "d-test-1", "target_root": root,
            "reason_code": "EVIDENCE_DISPUTED", "disputer": "third-party-1",
            "created_at": "2026-09-18T00:00:00Z", "evidence": []})
        r = gate(pkg, dispute_path=dp)
        self.assertEqual(r["decision"], "ALLOW_DISPUTED")
        self.assertEqual(r["exit_code"], 0)
        self.assertEqual(r["dispute"]["status"], "DISPUTED")

    # 8. dispute targeting another package -> HOLD (bad input, human decides)
    def test_08_mismatched_dispute_holds(self):
        pkg, _ = _make_pkg(self.tmp)
        dp = _write_json(os.path.join(self.tmp, "disp.json"), {
            "dispute_id": "d-test-2", "target_root": "0" * 64,
            "reason_code": "EVIDENCE_DISPUTED", "disputer": "x",
            "created_at": "2026-09-18T00:00:00Z", "evidence": []})
        r = gate(pkg, dispute_path=dp)
        self.assertEqual(r["decision"], "HOLD")
        self.assertEqual(r["dispute"]["status"], "MISMATCH")

    # 9. revocation for a DIFFERENT package does not block this one (MISMATCH -> HOLD)
    def test_09_mismatched_revocation_holds_not_denies(self):
        pkg, _ = _make_pkg(self.tmp)
        rp = _write_json(os.path.join(self.tmp, "rev.json"), {
            "revocation_id": "r-test-3", "target_root": "1" * 64,
            "reason_code": "OWNER_REQUEST", "key_id": "e" * 64,
            "signature": "BBBB", "revoked_at": "2026-09-18T00:00:00Z"})
        r = gate(pkg, revocation_path=rp)
        self.assertEqual(r["decision"], "HOLD")
        self.assertNotEqual(r["decision"], "DENY")

    # 10. exit-code contract is total (every decision maps to a defined code)
    def test_10_exit_code_contract(self):
        mapping = {"ALLOW": 0, "ALLOW_DISPUTED": 0, "DENY": 2, "HOLD": 3}
        self.assertEqual(set(mapping.values()), {0, 2, 3})
        pkg, _ = _make_pkg(self.tmp)
        r = gate(pkg)
        self.assertEqual(r["exit_code"], mapping[r["decision"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
