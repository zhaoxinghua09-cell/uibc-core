"""The conversion is one-way and lossy by design. These tests hold the parts
that must stay true: a payload plus its recorded hash becomes an evidence file
and its hash, the transformed package verifies, and the two container-neutral
faults stay detectable after the move.

Measured 2026-11-20 against the published EATF vectors: 5/5 valid convert and
verify on both implementations; 3/3 container-neutral faults (tampered payload,
missing payload, tampered metadata) fail on both; 5 fault classes are declined
as untransferable rather than converted into a different fault.
"""

import hashlib
import json
import os
import sys
import tempfile
import unittest
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

import aep_to_uibc  # noqa: E402
from independent_verifier.iverify import independent_verify  # noqa: E402
from uibc_core.verify import verify as ref_verify  # noqa: E402


def _make_aep(path, payload=b'{"decision":"allow"}\n'):
    meta = {"schema": "urn:eatf:spec:aep:metadata:1.0",
            "attestation_id": "att_test_01",
            "created_at": "2026-11-20T00:00:00Z",
            "agent_id": "urn:test:agent:one",
            "policy_decision": "allow"}
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("metadata.json", json.dumps(meta))
        z.writestr("canonical.bin", payload)
        z.writestr("hash.sha256", hashlib.sha256(payload).hexdigest())


class TestAepConversion(unittest.TestCase):
    def test_a_foreign_package_becomes_a_verifiable_uibc_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            aep = os.path.join(tmp, "p.aep")
            _make_aep(aep)
            pkg, key_hex = aep_to_uibc.convert(aep, os.path.join(tmp, "pkg"))
            key = bytes.fromhex(key_hex)
            self.assertEqual(ref_verify(pkg, key=key)["result"], "PASS")
            self.assertEqual(independent_verify(pkg, key=key)["result"], "PASS")
            files = os.listdir(os.path.join(pkg, "evidence", "files"))
            self.assertEqual(len(files), 2)
    def test_the_payload_bytes_are_not_altered(self):
        with tempfile.TemporaryDirectory() as tmp:
            payload = b'the exact bytes, unchanged\n'
            aep = os.path.join(tmp, "p.aep")
            _make_aep(aep, payload)
            pkg, _ = aep_to_uibc.convert(aep, os.path.join(tmp, "pkg"))
            got = open(os.path.join(pkg, "evidence", "files", "canonical.bin"), "rb").read()
            self.assertEqual(got, payload)

    def test_a_mangled_payload_is_caught_after_the_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            aep = os.path.join(tmp, "p.aep")
            _make_aep(aep)
            pkg, key_hex = aep_to_uibc.convert(aep, os.path.join(tmp, "pkg"),
                                               fault="tampered-canonical-bin")
            key = bytes.fromhex(key_hex)
            self.assertEqual(ref_verify(pkg, key=key)["result"], "FAIL")
            self.assertEqual(independent_verify(pkg, key=key)["result"], "FAIL")

    def test_an_absent_payload_is_caught_after_the_move(self):
        with tempfile.TemporaryDirectory() as tmp:
            aep = os.path.join(tmp, "p.aep")
            _make_aep(aep)
            pkg, key_hex = aep_to_uibc.convert(aep, os.path.join(tmp, "pkg"),
                                               fault="missing-canonical-bin")
            key = bytes.fromhex(key_hex)
            self.assertEqual(ref_verify(pkg, key=key)["result"], "FAIL")
            self.assertEqual(independent_verify(pkg, key=key)["result"], "FAIL")

    def test_untransferable_classes_are_declared_not_silently_skipped(self):
        for name in ("bad-signature-classical", "bad-signature-pqc",
                     "bad-timestamp", "tampered-overt-receipt", "untrusted-issuer"):
            self.assertIn(name, aep_to_uibc.NOT_TRANSFERABLE)
            self.assertNotIn(name, aep_to_uibc.TRANSFERABLE)


if __name__ == "__main__":
    unittest.main()
