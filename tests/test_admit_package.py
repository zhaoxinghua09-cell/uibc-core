"""Admission of a foreign artifact, with a negative control.

The claim this tool makes is narrow: the bytes you hold are the bytes that were
sealed. So the test that matters is the one where somebody changes a byte after
the seal and the verdict flips — without that, "PASS" would mean "we looked at
it", which is not a claim anyone can check.
"""
import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(_REPO, "tools"))

import admit_package as ap  # noqa: E402


def _keypair(tmp):
    seed = os.path.join(tmp, "e.key")
    subprocess.run([sys.executable, "-m", "uibc_core.cli", "keygen", "--out", seed,
                    "--ed25519"], capture_output=True, check=True)
    return seed, seed + ".pub"


def _wheel(tmp, name="demo-1.0.whl", files=(("pkg/__init__.py", "print(1)\n"),
                                            ("pkg/util.py", "x = 2\n"))):
    path = os.path.join(tmp, name)
    with zipfile.ZipFile(path, "w") as z:
        for member, body in files:
            z.writestr(member, body)
    return path


class TestAdmitPackage(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="admit-")
        self.art = _wheel(self.tmp)
        self.seed, self.pub = _keypair(self.tmp)
        self.out = os.path.join(self.tmp, "pkg")

    def test_the_inventory_covers_every_member(self):
        kind, digest, size, members = ap.inventory(self.art)
        self.assertEqual(kind, "zip/wheel")
        self.assertEqual(len(members), 2)
        self.assertEqual(digest, hashlib.sha256(open(self.art, "rb").read()).hexdigest())
        self.assertEqual(size, os.path.getsize(self.art))
        names = sorted(m["path"] for m in members)
        self.assertEqual(names, ["pkg/__init__.py", "pkg/util.py"])

    def test_a_sealed_artifact_verifies_under_a_pinned_key(self):
        r = ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                     key=self.seed, pinned=self.pub)
        self.assertEqual(r["verdicts"]["open"], "PASS")
        self.assertEqual(r["verdicts"]["pinned"], "PASS")
        self.assertEqual(r["checks"], [], "no non-PASS check should remain")

    def test_a_changed_byte_flips_the_verdict(self):
        ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                     key=self.seed, pinned=self.pub)
        # the evidence copy inside the package is what a verifier hashes
        ev = os.path.join(self.out, "evidence")
        target = None
        for root, _d, files in os.walk(ev):
            for f in files:
                if f.endswith(".whl"):
                    target = os.path.join(root, f)
        self.assertIsNotNone(target, "artifact copy not found under evidence/")
        data = bytearray(open(target, "rb").read())
        data[10] ^= 0xFF
        open(target, "wb").write(bytes(data))
        verdict = ap._verify_dict(sys.executable, self.out, self.pub)
        self.assertEqual(verdict["result"], "FAIL")
        self.assertIn("S4", {c["id"] for c in verdict["checks"]
                             if c["result"] != "PASS"})

    def test_no_rate_is_invented_for_one_artifact(self):
        r = ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                     key=self.seed, pinned=self.pub)
        d = r["disclosure"]
        self.assertEqual(d["numerator"], "n/a")
        self.assertEqual(d["denominator"], "1 artifact")
        self.assertIn("n<30", d["na_policy"])
        self.assertEqual(set(d) & set(ap.DISCLOSURE_FIELDS), set(ap.DISCLOSURE_FIELDS))

    def test_a_second_admission_will_not_overwrite_the_first(self):
        ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                 key=self.seed, pinned=self.pub)
        with self.assertRaises(ap.ArtifactError):
            ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable)

    def test_a_directory_is_admitted_by_walking_it(self):
        d = os.path.join(self.tmp, "skill")
        os.makedirs(os.path.join(d, "sub"))
        open(os.path.join(d, "SKILL.md"), "w").write("# skill\n")
        open(os.path.join(d, "sub", "run.py"), "w").write("print('x')\n")
        r = ap.admit(d, os.path.join(self.tmp, "pkg_dir"), "skill", "alice",
                     sys.executable, key=self.seed, pinned=self.pub)
        self.assertEqual(r["inventory"]["member_count"], 2)
        self.assertEqual([m["path"] for m in r["inventory"]["members"]],
                         ["SKILL.md", "sub/run.py"])
        self.assertEqual(r["verdicts"]["pinned"], "PASS")

    def test_the_gate_decides_allow_and_states_why(self):
        r = ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                     key=self.seed, pinned=self.pub)
        self.assertEqual(r["decision"], "ALLOW")
        self.assertIn("verify PASS", r["reason"])
        self.assertIn("no revocation", r["reason"])

    def test_a_tampered_package_is_denied_not_only_failed(self):
        # verify returning FAIL and the gate returning DENY are different
        # answers: the gate folds revocation and dispute overlays in, and a
        # caller who stops at verify would implement that logic themselves.
        ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                 key=self.seed, pinned=self.pub)
        for root, _d, files in os.walk(os.path.join(self.out, "evidence")):
            for f in files:
                if f.endswith(".whl"):
                    p = os.path.join(root, f)
                    data = bytearray(open(p, "rb").read())
                    data[4] ^= 0xFF
                    open(p, "wb").write(bytes(data))
        gate = ap._gate_dict(sys.executable, self.out, self.pub)
        self.assertEqual(gate["decision"], "DENY")
        self.assertEqual(gate["verify_result"], "FAIL")

    def test_skipping_the_gate_is_possible_but_weaker(self):
        r = ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                     key=self.seed, pinned=self.pub, run_gate=False)
        self.assertIsNone(r["decision"])

    def test_the_record_names_what_it_did_not_look_at(self):
        r = ap.admit(self.art, self.out, "demo-1.0", "alice", sys.executable,
                     key=self.seed, pinned=self.pub)
        text = ap.render(r)
        self.assertIn("no malware scan", text)
        self.assertIn("no execution", text)
        self.assertIn("It does not mean the artifact is good", text)


if __name__ == "__main__":
    unittest.main()
