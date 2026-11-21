#!/usr/bin/env python3
"""P1-4: independent verifier public-key pinning (S6/V6).

A key-substituted re-seal verifies against the attacker's own new key, so in
open mode it passes V6. Pinning the owner's public key out-of-band must make
that mismatch fail V6. These tests pin against the mutation-benchmark base
package; if the mutants are not on disk they are skipped, not failed.
"""
import base64
import importlib.util
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)


def _load():
    spec = importlib.util.spec_from_file_location(
        "iverify_pin", os.path.join(ROOT, "independent_verifier", "iverify.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


iv = _load()
MB = os.path.join(ROOT, "tools", "out", "_mb")
BASE = os.path.join(MB, "base")
M17 = os.path.join(MB, "m_M17")


def _pubhex(pkg):
    seal = json.load(open(os.path.join(pkg, "signatures", "seal.json"), encoding="utf-8"))
    return base64.b64decode(seal["public_key"]).hex()


@unittest.skipUnless(os.path.isdir(BASE) and os.path.isdir(M17),
                     "mutation benchmark packages not on disk")
class PubkeyPinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner = bytes.fromhex(_pubhex(BASE))
        cls.attacker = bytes.fromhex(_pubhex(M17))

    def test_base_with_owner_pin_passes_v6(self):
        out = iv.independent_verify(BASE, pubkey=self.owner)
        self.assertEqual(out["checks"]["V6"], "PASS")

    def test_base_with_wrong_pin_fails_v6(self):
        out = iv.independent_verify(BASE, pubkey=self.attacker)
        self.assertEqual(out["checks"]["V6"], "FAIL")

    def test_keyswap_caught_by_owner_pin(self):
        # M17 re-sealed with the attacker key; pinning the owner key fails V6.
        out = iv.independent_verify(M17, pubkey=self.owner)
        self.assertEqual(out["checks"]["V6"], "FAIL")

    def test_keyswap_open_mode_passes_v6_known_boundary(self):
        # Documented open-mode boundary: without a pin the substituted seal
        # verifies against itself. This must stay a known gap, not silently
        # become a pass claim.
        out = iv.independent_verify(M17)
        self.assertEqual(out["checks"]["V6"], "PASS")

    def test_pin_length_rejected_by_caller_not_crash(self):
        # A malformed pin must not crash the verifier; V6 fails closed.
        out = iv.independent_verify(BASE, pubkey=b"short")
        self.assertEqual(out["checks"]["V6"], "FAIL")


if __name__ == "__main__":
    unittest.main()
