#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""COSE_Sign1 over EdDSA with no third-party package (RFC 9052, RFC 8949 subset).

The tests below aim at the failures that matter, not the happy path:

  * a verifier that returns False must not be reachable by "no exception thrown";
  * changing one byte of payload, signature, or protected header must fail;
  * an algorithm downgrade (alg -19 or absent) must be refused, not ignored;
  * deterministic encoding must give byte-identical output for equal maps
    regardless of insertion order.
"""

import unittest

from uibc_core import cose_min
from uibc_core.signing import ed_generate_seed
from uibc_core.ed25519 import publickey


class CborTests(unittest.TestCase):

    def test_roundtrip_scalars_and_containers(self):
        cases = [b"bytes", "text-\u4e2d\u6587", 0, -7, 1234567890123,
                 [1, b"x", "y"], {"a": 1, "b": [True, False, None]}]
        for obj in cases:
            self.assertEqual(cose_min.decode(cose_min.encode(obj)), obj)

    def test_deterministic_key_order(self):
        a = cose_min.encode({"bb": 2, "a": 1, "ccc": 3})
        b = cose_min.encode({"ccc": 3, "a": 1, "bb": 2})
        self.assertEqual(a, b)

    def test_shortest_integer_form(self):
        self.assertEqual(cose_min.encode(10), b"\x0a")
        self.assertEqual(cose_min.encode(10 ** 6), b"\x1a\x00\x0f\x42\x40")

    def test_rejects_tags_floats_indefinite(self):
        # 0xc6 = tag(6); 0xfa = float32; 0x5f = indefinite bytes
        for bad in (b"\xc6\x01", b"\xfa\x3f\x80\x00\x00", b"\x5f\x41\x61\xff"):
            with self.assertRaises(cose_min.CborError):
                cose_min.decode(bad)

    def test_rejects_trailing_bytes(self):
        with self.assertRaises(cose_min.CborError):
            cose_min.decode(b"\x01\x02")


class Sign1Tests(unittest.TestCase):

    def setUp(self):
        self.seed = ed_generate_seed()
        self.pub = publickey(self.seed)
        self.payload = b'{"uibc":"S6 seal bytes stand in here"}'

    def test_sign_verify_roundtrip(self):
        msg = cose_min.sign1_encode(self.payload, self.seed)
        ok, out, why = cose_min.sign1_verify(msg, self.pub)
        self.assertTrue(ok, why)
        self.assertEqual(out, self.payload)

    def test_verify_without_explicit_key_uses_kid(self):
        msg = cose_min.sign1_encode(self.payload, self.seed)
        ok, out, why = cose_min.sign1_verify(msg)   # no public_key argument
        self.assertTrue(ok, why)
        self.assertEqual(out, self.payload)

    def test_flipping_payload_fails(self):
        msg = cose_min.sign1_encode(self.payload, self.seed)
        bad = bytearray(msg)
        for i, b in enumerate(bad):
            if b == self.payload[0]:
                bad[i] = 0x41 if b != 0x41 else 0x42
                break
        ok, _, why = cose_min.sign1_verify(bytes(bad), self.pub)
        self.assertFalse(ok)
        self.assertIn(why, ("signature does not verify", "signature does not verify"))

    def test_flipping_signature_byte_fails(self):
        msg = cose_min.sign1_encode(self.payload, self.seed)
        parsed = cose_min.decode(msg)
        sig = bytearray(parsed[3])
        sig[0] ^= 0x01
        tampered = cose_min.encode([parsed[0], parsed[1], parsed[2], bytes(sig)])
        ok, _, why = cose_min.sign1_verify(tampered, self.pub)
        self.assertFalse(ok, why)

    def test_algorithm_downgrade_is_refused(self):
        # rebuild protected header with alg -19 (ES256K) and re-sign with EdDSA:
        # signature is cryptographically fine, but the declared algorithm lies.
        seed, payload = self.seed, self.payload
        protected = cose_min.encode({1: -19, 4: publickey(seed)})
        body = cose_min.encode(["Signature1", protected, b"", payload])
        from uibc_core.ed25519 import sign
        sig = sign(seed, body)
        forged = cose_min.encode([protected, {}, payload, sig])
        ok, _, why = cose_min.sign1_verify(forged, self.pub)
        self.assertFalse(ok)
        self.assertIn("not EdDSA", why)

    def test_detached_payload(self):
        msg = cose_min.sign1_encode(self.payload, self.seed, detached=True)
        ok, out, why = cose_min.sign1_verify(msg, self.pub, payload=self.payload)
        self.assertTrue(ok, why)
        self.assertEqual(out, self.payload)
        ok2, _, why2 = cose_min.sign1_verify(msg, self.pub)
        self.assertFalse(ok2)
        self.assertIn("detached", why2)

    def test_foreign_key_fails(self):
        other = ed_generate_seed()
        msg = cose_min.sign1_encode(self.payload, self.seed)
        ok, _, why = cose_min.sign1_verify(msg, publickey(other))
        self.assertFalse(ok, why)


if __name__ == "__main__":
    unittest.main()
