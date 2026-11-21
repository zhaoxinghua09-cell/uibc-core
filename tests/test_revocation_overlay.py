"""The overlay must move the decision, and must never fail open.

Four runs are asserted by tools/demo_revocation.py: ALLOW without overlay,
DENY with a valid owner revocation, HOLD when the revocation cannot be
verified (no key), HOLD when it was signed by a different key.

HOLD matters more than DENY: the common shortcut is to treat "revocation I
cannot check" as "no revocation" and return ALLOW. That is the bug this pins.

There is also a limitation asserted rather than described: revocation
signatures are HMAC-only, so an Ed25519-sealed package cannot have its
revocation verified at all - the gate HOLDs. A future change that starts
returning ALLOW there would be a regression, not an improvement.
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(HERE, "tools", "demo_revocation.py")


class RevocationOverlay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="revdemo_")
        proc = subprocess.run([sys.executable, DEMO, "--work", cls.tmp,
                               "--python", sys.executable, "--json"],
                              capture_output=True, text=True, timeout=300)
        cls.proc = proc
        try:
            cls.result = json.loads(proc.stdout)
        except ValueError:
            cls.result = None

    def test_all_eight_runs_behave_as_documented(self):
        self.assertIsNotNone(self.result, self.proc.stdout + self.proc.stderr)
        got = {r["label"]: r["decision"] for r in self.result["runs"]}
        self.assertEqual(got["no overlay"], "ALLOW")
        self.assertEqual(got["valid owner revocation"], "DENY")
        self.assertEqual(got["same revocation, no key"], "HOLD")
        self.assertEqual(got["revocation signed by another key"], "HOLD")
        self.assertEqual(got["ed25519 package, no overlay"], "ALLOW")
        self.assertEqual(got["ed25519 revocation, pinned pubkey"], "DENY")
        self.assertEqual(got["ed25519 revocation signed by another key"], "HOLD")
        self.assertEqual(got["ed25519 revocation, no pubkey"], "HOLD")
        self.assertEqual(self.proc.returncode, 0)

    def test_the_bytes_never_move(self):
        # If a package changed to make the DENY happen, the demo would be
        # proving the wrong thing: overlay, not bytes.
        self.assertEqual(self.result["tree_hash_before"],
                         self.result["tree_hash_after"])
        self.assertTrue(self.result["package_unchanged"])
        self.assertEqual(self.result["ed25519_tree_before"],
                         self.result["ed25519_tree_after"])
        self.assertTrue(self.result["ed25519_package_unchanged"])

    def test_an_unverifiable_revocation_is_never_allow(self):
        for r in self.result["runs"]:
            if r["keys"]["revocation"]["status"] == "UNVERIFIABLE":
                self.assertEqual(r["decision"], "HOLD", r)
        # Four different unverifiable causes, four different reasons: no HMAC
        # key, a bad HMAC signature, no public key, a foreign key_id. Asserting
        # one phrase across all of them would be a test that only looked right.
        reasons = [r["reason"] for r in self.result["runs"]
                   if r["keys"]["revocation"]["status"] == "UNVERIFIABLE"]
        self.assertEqual(len(reasons), 4)
        self.assertTrue(any("no --key" in r for r in reasons))
        self.assertTrue(any("invalid for supplied key" in r for r in reasons))
        self.assertTrue(any("no --pubkey" in r for r in reasons))
        self.assertTrue(any("key_id does not match" in r for r in reasons))


    def test_a_deny_says_which_overlay_caused_it(self):
        denies = [r for r in self.result["runs"] if r["decision"] == "DENY"]
        self.assertEqual(len(denies), 2)   # one per signature algorithm
        for d in denies:
            self.assertIn("revoked", d["reason"])
            self.assertEqual(d["exit"], 2)


class Ed25519Revocation(unittest.TestCase):
    """The asymmetric path, tested directly rather than through the demo."""

    def test_a_revocation_signed_by_the_owner_denies_a_clean_package(self):
        sys.path.insert(0, os.path.join(HERE, "tools"))
        import admit_package as ap
        tmp = tempfile.mkdtemp(prefix="rev_ed_ok_")
        seed = os.path.join(tmp, "owner.key")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "keygen", "--out", seed,
                        "--ed25519"], check=True, capture_output=True)
        pub = seed + ".pub"
        art = os.path.join(tmp, "a.zip")
        import zipfile
        with zipfile.ZipFile(art, "w") as z:
            z.writestr("a.txt", "x\n")
        pkg = os.path.join(tmp, "pkg")
        ap.admit(art, pkg, "ed-ok", "alice", sys.executable, key=seed, pinned=pub)

        rev = os.path.join(tmp, "rev.json")
        proc = subprocess.run([sys.executable, "-m", "uibc_core.cli", "revoke", pkg,
                               "--key", seed, "--out", rev],
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

        # verify still PASSes: the bytes are untouched, only the decision moves.
        v = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify", pkg,
                            "--pubkey", pub], capture_output=True, text=True)
        self.assertEqual(json.loads(v.stdout)["result"], "PASS")

        g = subprocess.run([sys.executable, "-m", "uibc_core.cli", "gate", pkg,
                            "--pubkey", pub, "--revocation", rev],
                           capture_output=True, text=True)
        rep = json.loads(g.stdout)
        self.assertEqual(rep["decision"], "DENY")
        self.assertEqual(rep["revocation"]["status"], "REVOKED")
        self.assertEqual(g.returncode, 2)

    def test_ed25519_revocation_without_pubkey_holds(self):
        # Same files as above, but no pinned key: nothing to verify against.
        tmp = tempfile.mkdtemp(prefix="rev_ed_nokey_")
        sys.path.insert(0, os.path.join(HERE, "tools"))
        import admit_package as ap
        seed = os.path.join(tmp, "o.key")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "keygen", "--out", seed,
                        "--ed25519"], check=True, capture_output=True)
        art = os.path.join(tmp, "a.zip")
        import zipfile
        with zipfile.ZipFile(art, "w") as z:
            z.writestr("a.txt", "x\n")
        pkg = os.path.join(tmp, "pkg")
        ap.admit(art, pkg, "ed-nokey", "alice", sys.executable, key=seed,
                 pinned=seed + ".pub")
        rev = os.path.join(tmp, "rev.json")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "revoke", pkg,
                        "--key", seed, "--out", rev], check=True, capture_output=True)
        g = subprocess.run([sys.executable, "-m", "uibc_core.cli", "gate", pkg,
                            "--revocation", rev], capture_output=True, text=True)
        rep = json.loads(g.stdout)
        self.assertEqual(rep["decision"], "HOLD")
        self.assertIn("no --pubkey", rep["reason"])


class Ed25519Limitation(unittest.TestCase):
    """A revocation whose signature nothing can check must HOLD, not guess."""

    def test_ed25519_package_with_revocation_holds(self):
        sys.path.insert(0, os.path.join(HERE, "tools"))
        import admit_package as ap
        tmp = tempfile.mkdtemp(prefix="rev_ed_")
        seed = os.path.join(tmp, "owner.key")
        subprocess.run([sys.executable, "-m", "uibc_core.cli", "keygen", "--out", seed,
                        "--ed25519"], check=True, capture_output=True)
        pub = seed + ".pub"
        art = os.path.join(tmp, "a.zip")
        import zipfile
        with zipfile.ZipFile(art, "w") as z:
            z.writestr("a.txt", "x\n")
        pkg = os.path.join(tmp, "pkg")
        ap.admit(art, pkg, "ed-1.0", "alice", sys.executable, key=seed, pinned=pub)

        # A revocation whose target_root matches, but signed with an HMAC key
        # the Ed25519 package has no way to check.
        import hashlib
        import base64
        import hmac
        import time
        with open(os.path.join(pkg, "manifest.json"), encoding="utf-8") as f:
            root = json.load(f)["evidence_root"]
        key = hashlib.sha256(b"someone else").digest()
        body = {"revocation_id": "r-ed", "target_root": root,
                "reason_code": "OWNER_REQUEST", "key_id": "ed-owner",
                "revoked_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
        body["signature"] = base64.b64encode(
            hmac.new(key, json.dumps(body, sort_keys=True,
                                     separators=(",", ":")).encode("utf-8"),
                     hashlib.sha256).digest()).decode()
        rev = os.path.join(tmp, "revocation.json")
        with open(rev, "w", encoding="utf-8") as f:
            json.dump(body, f)

        proc = subprocess.run([sys.executable, "-m", "uibc_core.cli", "gate", pkg,
                               "--pubkey", pub, "--revocation", rev],
                              capture_output=True, text=True)
        rep = json.loads(proc.stdout)
        self.assertEqual(rep["decision"], "HOLD", rep)
        self.assertEqual(rep["revocation"]["status"], "UNVERIFIABLE")
        self.assertNotEqual(proc.returncode, 0)
