"""Tests for uibc_core.did: did:key offline resolution, did:web, and the
DID -> seal-verification path.

The point of these tests is the property that matters externally: a third
party who has only the DID (no key handed to them out of band) can check our
seal. Everything else here is plumbing around that.
"""

import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core import did
from uibc_core import signing


def _sample_payload(seed):
    identity = {"schema": "uibc-1.1", "agent_id": "did-test-agent",
                "agent_type": "software-agent", "owner": "tester",
                "created_at": "2026-01-01T00:00:00Z",
                "status": "REGISTERED", "version": "0.1.0"}
    manifest = {"schema": "uibc-1.1", "agent_id": "did-test-agent",
                "agent_version": "0.1.0", "created_at": "2026-01-01T00:00:00Z",
                "evidence_count": 0,
                "evidence_root": "0" * 64}
    sig_b64, pub_b64 = signing.ed_seal_sign(seed, identity, manifest)
    return identity, manifest, sig_b64, pub_b64


class TestParse(unittest.TestCase):
    def test_parse_splits_method_and_id(self):
        self.assertEqual(did.parse("did:key:zABC"), ("key", "zABC"))
        self.assertEqual(did.parse("did:web:example.com"),
                         ("web", "example.com"))

    def test_parse_rejects_non_did(self):
        for bad in ("", "key:zABC", "did:", "did:KEY:zABC", 123, None):
            with self.assertRaises(did.DIDError):
                did.parse(bad)

    def test_unsupported_methods_are_refused_not_guessed(self):
        # Since 2026-11-24 the CAICT-family methods have published specifications
        # and are handled in did_cn.py. What must still be refused is either a
        # method this build knows nothing about, or an identifier that breaks the
        # published ABNF. Neither may be answered with a guess.
        for value in ("did:wba:example.com:agent:abc",   # spec exists, not wired here yet
                      "did:lgd:abc"):                    # no such method at all
            with self.assertRaises(did.UnsupportedMethod):
                did.resolve(value)
        from uibc_core import did_cn
        for value in ("did:cn:agent:sfKvhQocnYJJME4zGDdRqvWtes21Mi9c",
                      "did:ioa:agent:abc"):
            with self.assertRaises(did_cn.IdentifierError):
                did.resolve(value)


class TestDidKey(unittest.TestCase):
    def setUp(self):
        self.seed = bytes.fromhex("11" * 32)
        self.pub = signing.ed_public_key(self.seed)

    def test_did_key_round_trip(self):
        value = did.did_key_from_ed25519(self.pub)
        self.assertTrue(value.startswith("did:key:z"))
        document = did.resolve(value)
        self.assertEqual(document["id"], value)
        key, kid = did.document_ed25519_key(document)
        self.assertEqual(key, self.pub)
        self.assertTrue(kid.startswith(value + "#"))

    def test_did_key_resolves_without_network(self):
        value = did.did_key_from_ed25519(self.pub)
        calls = []

        def fetcher(url, timeout):  # pragma: no cover - must never run
            calls.append(url)
            raise AssertionError("did:key must not fetch %s" % url)

        document = did.resolve(value, fetcher=fetcher)
        self.assertEqual(calls, [], "did:key resolution must stay offline")
        self.assertEqual(document["id"], value)

    def test_seal_from_another_party_verifies_against_the_did(self):
        identity, manifest, sig_b64, _ = _sample_payload(self.seed)
        value = did.did_key_from_ed25519(self.pub)
        ok, kid = did.verify_seal_with_did(value, identity, manifest, sig_b64)
        self.assertTrue(ok, "third party must be able to verify with only the DID")
        self.assertIn("#", kid)

    def test_tampered_manifest_fails(self):
        identity, manifest, sig_b64, _ = _sample_payload(self.seed)
        value = did.did_key_from_ed25519(self.pub)
        manifest = dict(manifest, evidence_root="f" * 64)
        ok, _ = did.verify_seal_with_did(value, identity, manifest, sig_b64)
        self.assertFalse(ok)

    def test_wrong_key_fails(self):
        identity, manifest, sig_b64, _ = _sample_payload(bytes.fromhex("22" * 32))
        value = did.did_key_from_ed25519(self.pub)
        ok, _ = did.verify_seal_with_did(value, identity, manifest, sig_b64)
        self.assertFalse(ok)


class TestDidWeb(unittest.TestCase):
    def test_url_rules(self):
        self.assertEqual(did.did_web_url("did:web:example.com"),
                         "https://example.com/.well-known/did.json")
        self.assertEqual(did.did_web_url("did:web:example.com:user:alice"),
                         "https://example.com/user/alice/did.json")
        self.assertEqual(did.did_web_url("did:web:example.com%3A8443"),
                         "https://example.com:8443/.well-known/did.json")

    def test_resolve_via_injected_fetcher_and_verify_seal(self):
        seed = bytes.fromhex("33" * 32)
        pub = signing.ed_public_key(seed)
        value = "did:web:medxpert.cn"
        document = {
            "@context": ["https://www.w3.org/ns/did/v1"],
            "id": value,
            "verificationMethod": [{
                "id": value + "#uibc-1",
                "type": "Ed25519VerificationKey2020",
                "controller": value,
                "publicKeyMultibase": "z" + did._b58encode(
                    did._ED25519_MULTICODEC + pub),
            }],
            "assertionMethod": [value + "#uibc-1"],
        }
        seen = {}

        def fetcher(url, timeout):
            seen["url"] = url
            return document

        identity, manifest, sig_b64, _ = _sample_payload(seed)
        ok, kid = did.verify_seal_with_did(value, identity, manifest, sig_b64,
                                           fetcher=fetcher)
        self.assertEqual(seen["url"], "https://medxpert.cn/.well-known/did.json")
        self.assertEqual(kid, value + "#uibc-1")
        self.assertTrue(ok)

    def test_document_id_must_match(self):
        document = {"id": "did:web:other.example", "verificationMethod": []}
        with self.assertRaises(did.DIDError):
            did.resolve("did:web:example.com", fetcher=lambda url, timeout: document)

    def test_jwk_form_is_accepted(self):
        seed = bytes.fromhex("44" * 32)
        pub = signing.ed_public_key(seed)
        document = {
            "id": "did:web:example.com",
            "verificationMethod": [{
                "id": "did:web:example.com#k",
                "type": "JsonWebKey2020",
                "publicKeyJwk": {
                    "kty": "OKP", "crv": "Ed25519",
                    "x": base64.urlsafe_b64encode(pub).decode().rstrip("="),
                },
            }],
        }
        key, kid = did.document_ed25519_key(document)
        self.assertEqual(key, pub)
        self.assertEqual(kid, "did:web:example.com#k")

    def test_document_without_ed25519_key_is_refused(self):
        document = {"id": "did:web:example.com",
                    "verificationMethod": [{"id": "#x", "type": "Unknown"}]}
        with self.assertRaises(did.DIDError):
            did.document_ed25519_key(document)


class TestCliBinding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uibc-did-")
        self.pkg = os.path.join(self.tmp, "pkg")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _cli(self, *args):
        return subprocess.run([sys.executable, "-m", "uibc_core.cli"] + list(args),
                              cwd=_REPO, capture_output=True, text=True)

    def test_register_records_supported_did(self):
        value = did.did_key_from_ed25519(signing.ed_public_key(bytes.fromhex("55" * 32)))
        result = self._cli("init", self.pkg)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = self._cli("register", self.pkg, "--agent-id", "a1",
                           "--owner", "tester", "--did", value)
        self.assertEqual(result.returncode, 0, result.stderr)
        with open(os.path.join(self.pkg, "identity.json"), encoding="utf-8") as f:
            identity = json.load(f)
        self.assertEqual(identity["did"], value)

    def test_register_refuses_unresolvable_did(self):
        self._cli("init", self.pkg)
        result = self._cli("register", self.pkg, "--agent-id", "a1",
                           "--owner", "tester",
                           "--did", "did:ioa:agent:abc")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("no public resolution rule", result.stderr)


if __name__ == "__main__":
    unittest.main()
