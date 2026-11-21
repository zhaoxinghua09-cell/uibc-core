#!/usr/bin/env python3
"""Tests for the Nostr anchoring backend.

The Schnorr implementation is checked against the official BIP-340 test
vectors (committed as tests/data/bip340-vectors.csv), and against two
independent implementations where they happen to be installed:

  - libsecp256k1 via `coincurve` (the same library Bitcoin Core uses),
  - `pynostr` for NIP-01 event construction.

Those cross-checks are skipped when the libraries are absent, so the suite
still runs on a bare interpreter. The vectors are not skipped: a crypto
implementation that cannot reproduce the official vectors is wrong, and
"skip" is not an acceptable answer to that.
"""

import csv
import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
VECTORS = os.path.join(ROOT, "tests", "data", "bip340-vectors.csv")


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


nostr = _load(os.path.join(ROOT, "tools", "nostr_anchor.py"), "nostr_anchor")

try:
    from coincurve import PrivateKey as CCPrivateKey, PublicKeyXOnly as CCOOnly
except Exception:  # noqa: BLE001
    CCPrivateKey = None

try:
    from pynostr.event import Event as PyEvent
    from pynostr.key import PrivateKey as PyPrivateKey
except Exception:  # noqa: BLE001
    PyEvent = None

SECKEEY = "0" * 63 + "3"
MESSAGE = "11" * 32


class Bip340Vectors(unittest.TestCase):
    def test_all_official_vectors(self):
        with open(VECTORS, encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        self.assertEqual(len(rows), 19)
        for row in rows:
            with self.subTest(index=row["index"]):
                pubkey = bytes.fromhex(row["public key"])
                message = bytes.fromhex(row["message"])
                signature = bytes.fromhex(row["signature"])
                expected = row["verification result"].strip().upper() == "TRUE"
                self.assertEqual(nostr.schnorr_verify(pubkey, message, signature),
                                 expected, "verification verdict")
                if row["secret key"].strip():
                    aux = (bytes.fromhex(row["aux_rand"])
                           if row["aux_rand"].strip() else b"\x00" * 32)
                    produced = nostr.schnorr_sign(bytes.fromhex(row["secret key"]),
                                                  message, aux)
                    self.assertEqual(produced, signature, "reproduced signature")

    def test_signing_is_deterministic_for_a_fixed_aux(self):
        sk = bytes.fromhex(SECKEEY)
        msg = bytes.fromhex(MESSAGE)
        self.assertEqual(nostr.schnorr_sign(sk, msg, b"\x00" * 32),
                         nostr.schnorr_sign(sk, msg, b"\x00" * 32))

    def test_malformed_inputs_are_rejected_not_raised(self):
        sk = bytes.fromhex(SECKEEY)
        msg = bytes.fromhex(MESSAGE)
        good = nostr.schnorr_sign(sk, msg, b"\x00" * 32)
        self.assertFalse(nostr.schnorr_verify(b"\x00" * 31, msg, good))
        self.assertFalse(nostr.schnorr_verify(nostr.pubkey_of(sk), msg, good[:63]))
        flipped = bytearray(good)
        flipped[0] ^= 1
        self.assertFalse(nostr.schnorr_verify(nostr.pubkey_of(sk), msg, bytes(flipped)))

    @unittest.skipIf(CCPrivateKey is None, "coincurve not installed")
    def test_cross_check_against_libsecp256k1(self):
        sk = bytes.fromhex(SECKEEY)
        msg = bytes.fromhex(MESSAGE)
        aux = bytes(32)
        ours = nostr.schnorr_sign(sk, msg, aux)
        theirs = CCPrivateKey(sk).sign_schnorr(msg, aux_randomness=aux)
        self.assertEqual(ours, theirs, "same bytes with the same aux")
        self.assertTrue(CCOOnly(nostr.pubkey_of(sk)).verify(ours, msg))
        other_aux = CCPrivateKey(sk).sign_schnorr(msg, aux_randomness=bytes(range(1, 33)))
        self.assertTrue(nostr.schnorr_verify(nostr.pubkey_of(sk), msg, other_aux))


class Events(unittest.TestCase):
    def test_event_id_follows_the_definition(self):
        event = nostr.build_event(bytes.fromhex(SECKEEY), "hello", kind=1,
                                  tags=[], created_at=1794000000)
        serialized = json.dumps([0, event["pubkey"], event["created_at"], 1,
                                 [], "hello"], separators=(",", ":"),
                                ensure_ascii=False)
        import hashlib
        self.assertEqual(event["id"], hashlib.sha256(serialized.encode()).hexdigest())

    def test_roundtrip_and_self_verification(self):
        event = nostr.build_event(bytes.fromhex(SECKEEY), '{"root":"abc"}',
                                  kind=1, tags=[["t", "uibc-anchor"]],
                                  created_at=1794000000)
        self.assertTrue(nostr.verify_event(event))

    def test_tampering_breaks_both_id_and_signature(self):
        event = nostr.build_event(bytes.fromhex(SECKEEY), '{"root":"abc"}',
                                  created_at=1794000000)
        tampered = dict(event)
        tampered["content"] = '{"root":"abd"}'
        self.assertFalse(nostr.verify_event(tampered))
        # Even with a consistent id, a swapped signature must fail.
        forged = dict(event)
        forged["id"] = nostr.event_id(event["pubkey"], event["created_at"],
                                      event["kind"], event["tags"], '{"root":"abd"}')
        self.assertFalse(nostr.verify_event(forged))

    @unittest.skipIf(PyEvent is None, "pynostr not installed")
    def test_cross_check_against_pynostr(self):
        ours = nostr.build_event(bytes.fromhex(SECKEEY), '{"root":"abc"}',
                                 kind=1, tags=[["t", "uibc-anchor"]],
                                 created_at=1794000000)
        self.assertTrue(PyEvent.from_dict(dict(ours)).verify())
        key = PyPrivateKey.from_hex(SECKEEY)
        theirs = PyEvent(content='{"root":"abc"}', pubkey=key.public_key.hex(),
                         created_at=ours["created_at"], kind=1,
                         tags=[["t", "uibc-anchor"]])
        theirs.sign(SECKEEY)
        self.assertEqual(theirs.id, ours["id"], "independent NIP-01 id")
        self.assertTrue(nostr.verify_event(theirs.to_dict()))


class Anchoring(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.pkg = os.path.join(self.tmp, "pkg.uibc")
        shutil.copytree(os.path.join(ROOT, "fixtures", "clean.uibc"), self.pkg)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_anchor_event_commits_to_the_manifest_root(self):
        event = nostr.anchor_event(self.pkg, bytes.fromhex(SECKEEY),
                                   created_at=1794000000)
        with open(os.path.join(self.pkg, "manifest.json"), encoding="utf-8") as stream:
            root = json.load(stream)["evidence_root"]
        payload = json.loads(event["content"])
        self.assertEqual(payload["root"], root.lower())
        self.assertEqual(payload["scheme"], "uibc-core/evidence-root")
        self.assertTrue(nostr.verify_event(event))

    def test_package_without_root_is_rejected(self):
        broken = os.path.join(self.tmp, "broken.uibc")
        os.makedirs(broken)
        with open(os.path.join(broken, "manifest.json"), "w", encoding="utf-8") as stream:
            json.dump({"schema": "x"}, stream)
        with self.assertRaises(ValueError):
            nostr.anchor_event(broken, bytes.fromhex(SECKEEY))


if __name__ == "__main__":
    unittest.main()
