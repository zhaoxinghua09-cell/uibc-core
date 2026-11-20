"""The decision receipt has to survive three different kinds of tampering.

1. A byte changed in the sealed artifact      -> package_root and decision move.
2. A field edited in the receipt              -> receipt_sha256 moves, and only that.
3. A receipt that describes another package   -> package_root moves while the
   receipt stays self-consistent, which is the case a naive "hash the receipt"
   check would miss.

Each test asserts *which* fields are red, not just that something failed. A
checker that reports "MISMATCH" without naming the field is a checker nobody
can act on.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))

import admit_package as ap  # noqa: E402
import verify_decision as vd  # noqa: E402


def _make_artifact(root):
    """A tiny zip standing in for a wheel: real bytes, real members."""
    import zipfile
    path = os.path.join(root, "demo-1.0.whl")
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("demo/__init__.py", "print('hi')\n")
        z.writestr("demo/core.py", "def f():\n    return 1\n")
    return path


class ReceiptTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="receipt_")
        cls.art = _make_artifact(cls.tmp)
        cls.seed = os.path.join(cls.tmp, "owner.key")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "keygen",
                        "--out", cls.seed, "--ed25519"], check=True,
                       capture_output=True)
        cls.pub = cls.seed + ".pub"
        cls.out = os.path.join(cls.tmp, "pkg")
        cls.result = ap.admit(cls.art, cls.out, "demo-1.0", "alice",
                              sys.executable, key=cls.seed, pinned=cls.pub)
        cls.receipt_path = cls.out + ".decision.json"
        ap.write_receipt(cls.receipt_path, cls.result["receipt"])

    def _rows(self, pkg=None, receipt_path=None):
        r = vd.load_receipt(receipt_path or self.receipt_path)
        rows, ok = vd.compare(pkg or self.out, r, sys.executable, self.pub)
        return {name: good for name, _w, _g, good in rows}, ok

    def test_a_fresh_receipt_matches_its_own_package(self):
        fields, ok = self._rows()
        self.assertTrue(ok, fields)
        self.assertNotIn(False, fields.values())

    def test_the_receipt_carries_the_decision_not_just_the_verdict(self):
        r = vd.load_receipt(self.receipt_path)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertEqual(r["verify_result"], "PASS")
        self.assertIn("no revocation", r["reason"])
        self.assertEqual(len(r["receipt_sha256"]), 64)
        # The disclosure row travels with the decision: a reader does not have
        # to fetch a second document to learn that no rate was claimed.
        self.assertEqual(r["disclosure"]["denominator"], "1 artifact")
        self.assertEqual(r["disclosure"]["numerator"], "n/a")

    def test_a_byte_in_the_artifact_moves_the_package_root(self):
        pkg2 = os.path.join(self.tmp, "pkg_byte")
        ap.admit(self.art, pkg2, "demo-1.0", "alice", sys.executable,
                 key=self.seed, pinned=self.pub)
        whl = None
        for root, _d, files in os.walk(os.path.join(pkg2, "evidence")):
            for f in files:
                if f.endswith(".whl"):
                    whl = os.path.join(root, f)
        data = bytearray(open(whl, "rb").read())
        data[4] ^= 0xFF
        open(whl, "wb").write(bytes(data))
        fields, ok = self._rows(pkg=pkg2)
        self.assertFalse(ok)
        self.assertFalse(fields["package_root"])
        self.assertFalse(fields["decision"])
        self.assertFalse(fields["verify_result"])

    def test_editing_one_field_breaks_the_receipt_hash_and_nothing_else(self):
        path = os.path.join(self.tmp, "edited.json")
        with open(self.receipt_path, encoding="utf-8") as f:
            r = json.load(f)
        r["reason"] = r["reason"] + " (edited)"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2, sort_keys=True)
        fields, ok = self._rows(receipt_path=path)
        self.assertFalse(ok)
        self.assertFalse(fields["receipt_sha256"])
        self.assertFalse(fields["reason"])
        # Everything about the package still agrees: the tampering is in the
        # receipt, so a report that blamed the package would send the reader
        # to the wrong place.
        self.assertTrue(fields["package_root"])

    def test_a_receipt_for_another_package_is_self_consistent_but_wrong(self):
        # Re-sign the edited receipt so its own hash is valid again: this is
        # what a forger would do, and it is why package_root must be checked
        # against the bytes rather than trusted from the receipt.
        pkg2 = os.path.join(self.tmp, "pkg_other")
        ap.admit(self.art, pkg2, "demo-1.0", "bob", sys.executable,
                 key=self.seed, pinned=self.pub)
        path = os.path.join(self.tmp, "foreign.json")
        with open(self.receipt_path, encoding="utf-8") as f:
            r = json.load(f)
        r["package_root"] = "0" * 64
        body = {k: v for k, v in r.items() if k != "receipt_sha256"}
        import hashlib
        r["receipt_sha256"] = hashlib.sha256(ap.canonical_bytes(body)).hexdigest()
        with open(path, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=2, sort_keys=True)
        fields, ok = self._rows(pkg=pkg2, receipt_path=path)
        self.assertFalse(ok)
        self.assertTrue(fields["receipt_sha256"])   # internally consistent
        self.assertFalse(fields["package_root"])    # but not these bytes

    def test_the_receipt_carries_no_machine_specific_paths(self):
        # A receipt with a local path in it would only verify on the machine
        # that wrote it, which quietly turns "third party can recompute" into
        # "third party on the same disk can recompute". Guard the property.
        raw = open(self.receipt_path, encoding="utf-8").read()
        self.assertNotIn(self.tmp, raw)
        self.assertNotIn(self.out, raw)
        r = vd.load_receipt(self.receipt_path)
        self.assertEqual(r["tool"], "decision_receipt/1.0")
        self.assertEqual(len(r["package_root"]), 64)

    def test_a_package_copied_to_another_path_keeps_the_same_root(self):
        pkg2 = os.path.join(self.tmp, "pkg_copy")
        import shutil
        shutil.copytree(self.out, pkg2)
        fields, ok = self._rows(pkg=pkg2)
        self.assertTrue(ok, fields)

    # --- the stranger's case: artifact + receipt, no package -----------------

    def test_artifact_mode_matches_the_wheel_without_the_package(self):
        r = vd.load_receipt(self.receipt_path)
        rows, ok = vd.compare_artifact(self.art, r)
        self.assertTrue(ok)
        got = {n: g for n, _w, _g, g in rows}
        for f in ("receipt_sha256", "subject.sha256", "subject.bytes",
                  "subject.members", "subject.name"):
            self.assertTrue(got[f], f)
        # And it must not pretend the decision was checked: eight fields need
        # the package, and they have to be reported as NOT CHECKABLE.
        self.assertEqual(sum(1 for v in got.values() if v is None), 8)

    def test_artifact_mode_rejects_a_different_file(self):
        other = os.path.join(self.tmp, "other.txt")
        open(other, "w", encoding="utf-8").write("not the sealed artifact\n")
        rows, ok = vd.compare_artifact(other, vd.load_receipt(self.receipt_path))
        self.assertFalse(ok)
        got = {n: g for n, _w, _g, g in rows}
        self.assertFalse(got["subject.sha256"])
        self.assertFalse(got["subject.bytes"])
        # A file is one member; the receipt describes a two-member wheel.
        self.assertFalse(got["subject.members"])

    def test_artifact_mode_says_how_much_it_could_not_check(self):
        proc = subprocess.run([sys.executable,
                               os.path.join(HERE, "tools", "verify_decision.py"),
                               "--artifact", self.art, "--receipt", self.receipt_path,
                               "--python", sys.executable],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("MATCH on every checkable field", proc.stdout)
        self.assertIn("could not be checked", proc.stdout)
        # A bare "MATCH" here would overstate: the decision fields were not redone.
        self.assertNotIn("**MATCH** — every field recomputed", proc.stdout)

    def test_verify_decision_exits_nonzero_and_names_the_field(self):
        pkg2 = os.path.join(self.tmp, "pkg_cli")
        ap.admit(self.art, pkg2, "demo-1.0", "alice", sys.executable,
                 key=self.seed, pinned=self.pub)
        proc = subprocess.run([sys.executable,
                               os.path.join(HERE, "tools", "verify_decision.py"),
                               "--package", pkg2, "--receipt", self.receipt_path,
                               "--pubkey", self.pub, "--python", sys.executable],
                              capture_output=True, text=True)
        # Same artifact, different package directory: the package roots differ,
        # and the message has to say which field, not just "failed".
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("package_root", proc.stdout)
        self.assertIn("MISMATCH", proc.stdout)


if __name__ == "__main__":
    unittest.main()
