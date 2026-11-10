"""Seal v0.3 tests: Ed25519 public seals + three-valued verdict semantics.

Origin: an external review (2026-11) showed that a fully self-consistent
forgery verified PASS in open mode, because an INCONCLUSIVE S6 rode under
a two-valued top-level PASS. v0.3 answers in two moves:

  1. Verdicts are three-valued - FAIL > INCONCLUSIVE > PASS - so an
     unresolvable check caps the result instead of hiding under it.
  2. Ed25519 seals are publicly verifiable: provenance no longer needs
     the owner's secret, so an honest package can earn a real PASS from
     any stranger, and forgeries are left holding INCONCLUSIVE at best.

The pure-Python Ed25519 is locked to the RFC 8032 section 7.1 vectors.
"""

import base64
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

import uibc_core.cli as ucli  # noqa: E402
from uibc_core import ed25519  # noqa: E402
from uibc_core.canonical import evidence_root, hash_file  # noqa: E402
from uibc_core.signing import ed_generate_seed, ed_public_key, ed_seal_sign  # noqa: E402
from uibc_core.verify import verify  # noqa: E402

# RFC 8032 section 7.1, verbatim.
RFC_VECTORS = [
    ("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60",
     "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
     "",
     "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e06522490155"
     "5fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b"),
    ("4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb",
     "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
     "72",
     "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da"
     "085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00"),
    ("c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7",
     "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
     "af82",
     "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac"
     "18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a"),
]


class TestEd25519RFC8032(unittest.TestCase):
    def test_vectors(self):
        for seed_h, pub_h, msg_h, sig_h in RFC_VECTORS:
            seed, pub = bytes.fromhex(seed_h), bytes.fromhex(pub_h)
            msg, sig = bytes.fromhex(msg_h), bytes.fromhex(sig_h)
            self.assertEqual(ed25519.publickey(seed), pub)
            self.assertEqual(ed25519.sign(seed, msg), sig)  # deterministic
            self.assertTrue(ed25519.verify(pub, msg, sig))
            self.assertFalse(ed25519.verify(pub, msg + b"\x00", sig))
            bad = bytearray(sig)
            bad[10] ^= 1
            self.assertFalse(ed25519.verify(pub, msg, bytes(bad)))


def _a(**kw):
    return type("A", (), kw)()


class SealV03Case(unittest.TestCase):
    """End-to-end verdict semantics over CLI-built packages."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="seal-v03-")
        self.pkg = os.path.join(self.tmp, "p.uibc")
        ucli.cmd_init(_a(path=self.pkg))
        ucli.cmd_register(_a(path=self.pkg, agent_id="v03-agent", owner="owner",
                             agent_type="software-agent", version="1"))
        self.src = os.path.join(self.tmp, "ev.txt")
        with open(self.src, "w", encoding="utf-8") as f:
            f.write("evidence body v1\n")
        ucli.cmd_evidence(_a(path=self.pkg, type="ACTION", file=self.src,
                             media_type="text/plain", note=""))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    # -- helpers -------------------------------------------------------------
    def _submit(self, key_file=None):
        ucli.cmd_submit(_a(path=self.pkg, key=key_file))

    def _key_file(self, name, content):
        p = os.path.join(self.tmp, name)
        with open(p, "w", encoding="ascii") as f:
            f.write(content)
        return p

    def _ed_key(self, name="owner.edkey", seed=None):
        seed = seed or ed_generate_seed()
        return self._key_file(name, "ed25519:" + seed.hex()), seed

    def _forge_self_consistent(self):
        """Attacker rewrite: change the evidence, then recompute the index
        hash and the evidence root so the package is internally consistent
        again (everything Shi's review described)."""
        ev_dir = os.path.join(self.pkg, "evidence", "files")
        target = os.path.join(ev_dir, os.listdir(ev_dir)[0])
        with open(target, "a", encoding="utf-8") as f:
            f.write("forged line\n")
        idx_path = os.path.join(self.pkg, "evidence", "index.json")
        idx = json.load(open(idx_path, encoding="utf-8"))
        for e in idx["entries"]:
            e["content_hash"] = hash_file(os.path.join(self.pkg, "evidence", e["path"]))
        json.dump(idx, open(idx_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        man_path = os.path.join(self.pkg, "manifest.json")
        man = json.load(open(man_path, encoding="utf-8"))
        man["evidence_root"] = evidence_root([e["content_hash"] for e in idx["entries"]])
        json.dump(man, open(man_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        return man

    def _checks(self, report):
        return {c["id"]: c["result"] for c in report["checks"]}

    # -- the reviewer's three cases ------------------------------------------
    def test_a_forgery_unsigned_is_inconclusive_not_pass(self):
        self._submit()  # unsigned
        self._forge_self_consistent()
        r = verify(self.pkg)
        self.assertEqual(self._checks(r)["S4"], "PASS")   # consistency holds
        self.assertEqual(self._checks(r)["S5"], "PASS")
        self.assertEqual(r["result"], "INCONCLUSIVE")     # provenance does not
        self.assertEqual(r["assurance"], "unattested")

    def test_b_hmac_seal_open_is_inconclusive_strict_passes(self):
        from uibc_core.signing import generate_key
        kf = self._key_file("owner.key", generate_key().hex())
        self._submit(kf)
        r_open = verify(self.pkg)
        self.assertEqual(r_open["result"], "INCONCLUSIVE")
        key = bytes.fromhex(open(kf).read().strip())
        r_strict = verify(self.pkg, key=key)
        self.assertEqual(r_strict["result"], "PASS")
        self.assertEqual(r_strict["assurance"], "owner-key")

    def test_c_ed25519_seal_passes_for_any_stranger(self):
        kf, _seed = self._ed_key()
        self._submit(kf)
        r = verify(self.pkg)  # no key, no pin: a stranger's verdict
        self.assertEqual(r["result"], "PASS")
        self.assertEqual(self._checks(r)["S6"], "PASS")
        self.assertEqual(r["assurance"], "public-key")

    # -- Ed25519 attack surface ------------------------------------------------
    def test_d_ed25519_tampered_evidence_fails(self):
        kf, _ = self._ed_key()
        self._submit(kf)
        ev_dir = os.path.join(self.pkg, "evidence", "files")
        with open(os.path.join(ev_dir, os.listdir(ev_dir)[0]), "a",
                  encoding="utf-8") as f:
            f.write("tampered\n")
        self.assertEqual(verify(self.pkg)["result"], "FAIL")

    def test_e_keyswap_caught_by_pinning_only(self):
        owner_kf, owner_seed = self._ed_key()
        self._submit(owner_kf)
        man = self._forge_self_consistent()
        attacker_seed = ed_generate_seed()
        identity = json.load(open(os.path.join(self.pkg, "identity.json"),
                                  encoding="utf-8"))
        sig, pub_b64 = ed_seal_sign(attacker_seed, identity, man)
        from uibc_core.signing import ed_key_id
        seal = {"algorithm": "Ed25519", "key_id": ed_key_id(ed_public_key(attacker_seed)),
                "public_key": pub_b64, "signed": "identity+manifest",
                "signature": sig, "created_at": "2026-11-10T00:00:00Z"}
        json.dump(seal, open(os.path.join(self.pkg, "signatures", "seal.json"),
                             "w", encoding="utf-8"), ensure_ascii=False, indent=2)
        # Unpinned: the attacker's seal is valid against its own key - the
        # documented boundary, stated rather than hidden.
        self.assertEqual(verify(self.pkg)["result"], "PASS")
        # Pinned to the owner: substitution fails S6.
        r = verify(self.pkg, pubkey=ed_public_key(owner_seed))
        self.assertEqual(r["result"], "FAIL")
        self.assertEqual(self._checks(r)["S6"], "FAIL")

    def test_f_hmac_key_against_ed25519_seal_fails(self):
        kf, _ = self._ed_key()
        self._submit(kf)
        from uibc_core.signing import generate_key
        r = verify(self.pkg, key=generate_key())
        self.assertEqual(self._checks(r)["S6"], "FAIL")
        self.assertEqual(r["result"], "FAIL")

    def test_g_evidence_order_does_not_change_the_root(self):
        src2 = os.path.join(self.tmp, "ev2.txt")
        with open(src2, "w", encoding="utf-8") as f:
            f.write("second evidence\n")
        ucli.cmd_evidence(_a(path=self.pkg, type="OUTPUT", file=src2,
                             media_type="text/plain", note=""))
        kf, _ = self._ed_key()
        self._submit(kf)
        idx_path = os.path.join(self.pkg, "evidence", "index.json")
        idx = json.load(open(idx_path, encoding="utf-8"))
        idx["entries"] = list(reversed(idx["entries"]))
        json.dump(idx, open(idx_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=2)
        r = verify(self.pkg)
        # By design (docs/verdict-and-seal-semantics.md): the root binds the
        # SET of content hashes, not their order in the index file.
        self.assertEqual(self._checks(r)["S4"], "PASS")
        self.assertEqual(self._checks(r)["S5"], "PASS")
        self.assertEqual(r["result"], "PASS")

    def test_h_independent_verifier_agrees(self):
        from independent_verifier.iverify import independent_verify
        kf, _ = self._ed_key()
        self._submit(kf)
        self.assertEqual(independent_verify(self.pkg, None)["result"], "PASS")
        self._forge_self_consistent()
        os.remove(os.path.join(self.pkg, "signatures", "seal.json"))
        self.assertEqual(independent_verify(self.pkg, None)["result"],
                         verify(self.pkg)["result"])


if __name__ == "__main__":
    unittest.main()
