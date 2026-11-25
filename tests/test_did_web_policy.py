"""The did:web host and size policy must not depend on which transport carried the bytes.

This file exists because of a real cross-platform inconsistency (issue #434):
three s02b cases passed on Linux and failed on Windows. The cause was not the
platform -- it was that `assert_public_host`, the no-downgrade redirect handler
and the size cap all lived inside `_fetch_json`. Any caller that injected its
own fetcher (a test, the bench's local-server cases, an adapter) resolved
`did:web:127.0.0.1` happily, because the checks simply were not on that path.

So: the policy is asserted here at the resolution contract, with the transport
substituted. If someone later moves a check back into the transport helper,
these tests fail on every platform, which is the point.
"""

import json
import os
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core import did


def _fetcher(document):
    def fetch(url, timeout):
        return document
    return fetch


class HostPolicyTests(unittest.TestCase):
    def test_loopback_refused_even_with_injected_fetcher(self):
        doc = {"id": "did:web:127.0.0.1"}
        with self.assertRaises(did.DIDError) as ctx:
            did.resolve("did:web:127.0.0.1", fetcher=_fetcher(doc))
        self.assertIn("not a public address", str(ctx.exception))

    def test_private_range_refused_even_with_injected_fetcher(self):
        doc = {"id": "did:web:192.168.1.10"}
        with self.assertRaises(did.DIDError):
            did.resolve("did:web:192.168.1.10", fetcher=_fetcher(doc))

    def test_localhost_name_refused_even_with_injected_fetcher(self):
        doc = {"id": "did:web:localhost"}
        with self.assertRaises(did.DIDError):
            did.resolve("did:web:localhost", fetcher=_fetcher(doc))

    def test_public_host_still_resolves(self):
        doc = {"id": "did:web:example.com", "verificationMethod": []}
        self.assertEqual(did.resolve("did:web:example.com", fetcher=_fetcher(doc))["id"],
                         "did:web:example.com")


class SizePolicyTests(unittest.TestCase):
    def test_oversized_document_from_a_fetcher_is_refused(self):
        """A 20 MB document must not be accepted just because a fetcher produced it."""
        big = {"id": "did:web:example.com",
               "verificationMethod": [],
               "service": [{"id": "#s", "type": "X", "serviceEndpoint": "y" * 2200000}]}
        payload = json.dumps(big)
        self.assertGreater(len(payload.encode("utf-8")), did.MAX_DOCUMENT_BYTES)
        with self.assertRaises(did.DIDError) as ctx:
            did.resolve("did:web:example.com", fetcher=_fetcher(big))
        self.assertIn("cap", str(ctx.exception))

    def test_document_just_under_the_cap_is_accepted(self):
        big = {"id": "did:web:example.com", "verificationMethod": [],
               "service": [{"id": "#s", "type": "X", "serviceEndpoint": "y" * 1500000}]
               }
        payload = json.dumps(big)
        self.assertLess(len(payload.encode("utf-8")), did.MAX_DOCUMENT_BYTES)
        self.assertEqual(did.resolve("did:web:example.com", fetcher=_fetcher(big))["id"],
                         "did:web:example.com")


if __name__ == "__main__":
    unittest.main()
