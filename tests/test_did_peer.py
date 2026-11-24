"""Tests for uibc_core.did_peer: offline resolution of did:peer.

What is being pinned here, and why these cases: a did:peer document must be
reproducible from the identifier alone. So every assertion below is "given this
string, does the document come out right", with the vectors taken from the
Peer DID Method Specification rather than invented here -- an implementation
that only agrees with its own test data proves nothing.
"""

import base64
import json
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core import did
from uibc_core import did_peer
from uibc_core.identity_adapter import check

# Spec example: did:peer:0z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH is
# equivalent to did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH.
_V0 = "did:peer:0z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH"

_V2_NO_SERVICE = ("did:peer:2.Ez6LSbysY2xFMRpGMhb7tFTLMpeuPRaqaWM1yECx2AtzE3KCc"
                  ".Vz6MkqRYqQiSgvZQdnBytw86Qbs2ZWUkGv22od935YF4s8M7V")


def _v2_with_service():
    service = {"t": "dm", "s": "https://example.com/endpoint",
               "r": ["did:example:somemediator#somekey"], "a": ["didcomm/v2"]}
    blob = base64.urlsafe_b64encode(
        json.dumps(service, separators=(",", ":")).encode()).decode().rstrip("=")
    return _V2_NO_SERVICE + ".S" + blob


class Numalgo0Tests(unittest.TestCase):
    def test_resolves_offline_to_single_key(self):
        doc = did.resolve(_V0)
        self.assertEqual(doc["id"], _V0)
        self.assertEqual(len(doc["verificationMethod"]), 1)
        self.assertEqual(doc["verificationMethod"][0]["publicKeyMultibase"][:2], "z6")

    def test_key_material_matches_equivalent_did_key(self):
        """Spec says numalgo 0 is functionally equivalent to did:key for the same key."""
        peer_doc = did.resolve(_V0)
        key_doc = did.resolve("did:key:" + _V0.split(":peer:0", 1)[1])
        self.assertEqual(peer_doc["verificationMethod"][0]["publicKeyMultibase"],
                         key_doc["verificationMethod"][0]["publicKeyMultibase"])

    def test_all_signing_relationships_point_at_the_one_key(self):
        doc = did.resolve(_V0)
        key_id = doc["verificationMethod"][0]["id"]
        for rel in ("authentication", "assertionMethod",
                    "capabilityInvocation", "capabilityDelegation"):
            self.assertEqual(doc[rel], [key_id])

    def test_no_key_agreement_is_claimed(self):
        """We cannot derive X25519 from an Ed25519 public key, so we do not pretend to."""
        self.assertNotIn("keyAgreement", did.resolve(_V0))

    def test_state_is_verified(self):
        self.assertEqual(check(_V0).state, "VERIFIED")

    def test_x25519_material_is_refused_for_numalgo_0(self):
        """An encryption key is not an inception signing key; refuse rather than mislabel."""
        with self.assertRaises(did.DIDError):
            did.resolve("did:peer:0z6LSbysY2xFMRpGMhb7tFTLMpeuPRaqaWM1yECx2AtzE3KCc")

    def test_wrong_multibase_prefix_is_invalid(self):
        self.assertEqual(check("did:peer:0uAAAA").state, "INVALID")


class Numalgo2Tests(unittest.TestCase):
    def test_keys_are_numbered_in_order(self):
        doc = did.resolve(_V2_NO_SERVICE)
        self.assertEqual([m["id"].rsplit("#", 1)[1] for m in doc["verificationMethod"]],
                         ["key-1", "key-2"])

    def test_purpose_codes_map_to_relationships(self):
        doc = did.resolve(_V2_NO_SERVICE)
        self.assertEqual(doc["keyAgreement"],
                         [_V2_NO_SERVICE + "#key-1"])
        self.assertEqual(doc["authentication"],
                         [_V2_NO_SERVICE + "#key-2"])

    def test_multikey_type_and_controller(self):
        doc = did.resolve(_V2_NO_SERVICE)
        for m in doc["verificationMethod"]:
            self.assertEqual(m["type"], "Multikey")
            self.assertEqual(m["controller"], _V2_NO_SERVICE)

    def test_service_element_is_decoded_and_unabbreviated(self):
        doc = did.resolve(_v2_with_service())
        service = doc["service"][0]
        self.assertEqual(service["id"], "#service")
        self.assertEqual(service["type"], "DIDCommMessaging")
        self.assertEqual(service["serviceEndpoint"], "https://example.com/endpoint")
        self.assertEqual(service["routingKeys"], ["did:example:somemediator#somekey"])

    def test_service_without_id_gets_incrementing_ids(self):
        blob1 = base64.urlsafe_b64encode(b'{"t":"dm","s":"https://a.example"}').decode().rstrip("=")
        blob2 = base64.urlsafe_b64encode(b'{"t":"dm","s":"https://b.example"}').decode().rstrip("=")
        did_str = _V2_NO_SERVICE + ".S" + blob1 + ".S" + blob2
        doc = did.resolve(did_str)
        self.assertEqual([s["id"] for s in doc["service"]], ["#service", "#service-1"])

    def test_encryption_element_must_be_x25519(self):
        bad = "did:peer:2.Ez6MkqRYqQiSgvZQdnBytw86Qbs2ZWUkGv22od935YF4s8M7V"
        with self.assertRaises(did.DIDError):
            did.resolve(bad)

    def test_missing_key_elements_is_refused(self):
        blob = base64.urlsafe_b64encode(b'{"t":"dm","s":"https://x.example"}').decode().rstrip("=")
        with self.assertRaises(did.DIDError):
            did.resolve("did:peer:2.S" + blob)

    def test_unknown_purpose_code_is_refused(self):
        with self.assertRaises(did.DIDError):
            did.resolve("did:peer:2.Zz6MkqRYqQiSgvZQdnBytw86Qbs2ZWUkGv22od935YF4s8M7V")

    def test_empty_element_is_refused(self):
        with self.assertRaises(did.DIDError):
            did.resolve(_V2_NO_SERVICE + ".")

    def test_state_is_verified(self):
        self.assertEqual(check(_V2_NO_SERVICE).state, "VERIFIED")


class NotSelfResolvingTests(unittest.TestCase):
    def test_numalgo_1_is_unresolved_not_invalid(self):
        record = check("did:peer:1z6MkqRYqQiSgvZQdnBytw86Qbs2ZWUkGv22od935YF4s8M7V")
        self.assertEqual(record.state, "UNRESOLVED")
        self.assertIn("genesis document", record.notes)

    def test_numalgo_3_is_unresolved_not_invalid(self):
        record = check("did:peer:3zQmS19jtYDvGtKVrJhQnRFpBQAx3pJ9omx2HpNrcXFuRCz9")
        self.assertEqual(record.state, "UNRESOLVED")

    def test_numalgo_4_is_unresolved_and_says_why(self):
        record = check("did:peer:4zQmS19jtYDvGtKVrJhQnRFpBQAx3pJ9omx2HpNrcXFuRCz9")
        self.assertEqual(record.state, "UNRESOLVED")
        self.assertIn("long form", record.notes)

    def test_undefined_numalgo_is_invalid(self):
        self.assertEqual(check("did:peer:7zQmS19jtYDv").state, "INVALID")

    def test_empty_identifier_is_invalid(self):
        self.assertEqual(check("did:peer:").state, "INVALID")


class MatrixTests(unittest.TestCase):
    def test_matrix_names_every_numalgo_the_spec_defines(self):
        self.assertEqual(sorted(did_peer.matrix()["peer"]), ["0", "1", "2", "3", "4"])

    def test_peer_is_in_supported_methods(self):
        self.assertIn("peer", did.SUPPORTED_METHODS)


if __name__ == "__main__":
    unittest.main()
