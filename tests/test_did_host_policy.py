"""Network guards for `did:web`.

Each test here corresponds to a defect measured on 2026-11-23 in the harness
(`harness/s02b_did_hostile_clean.py`), where a resolver could be made to fetch
from the verifier's own machine, follow a redirect to plaintext, or read an
unbounded response. The tests are offline: they either refuse before any socket
is opened, or they use a fake response object.
"""

import socket
import unittest
from unittest import mock

from uibc_core import did


REQ = "https://example.com/.well-known/did.json"


class PublicHostTests(unittest.TestCase):
    def test_ip_literals_are_refused(self):
        # w3c-ccg did:web: the method-specific identifier MUST NOT contain an IP.
        for host in ("127.0.0.1", "169.254.169.254", "10.0.0.1", "192.168.1.1",
                     "::1", "[::1]", "8.8.8.8"):
            with self.subTest(host=host), self.assertRaises(did.HostPolicyError):
                did.assert_public_host(host, resolve_dns=False)

    def test_local_names_are_refused(self):
        for host in ("localhost", "LOCALHOST", "metadata.google.internal",
                     "instance-data", "printer.local", "svc.internal",
                     "localhost."):
            with self.subTest(host=host), self.assertRaises(did.HostPolicyError):
                did.assert_public_host(host, resolve_dns=False)

    def test_non_hostnames_are_refused(self):
        for host in ("", " ", "user@example.com", "example.com/path", "a b"):
            with self.subTest(host=host), self.assertRaises(did.HostPolicyError):
                did.assert_public_host(host, resolve_dns=False)

    def test_a_public_name_is_accepted(self):
        did.assert_public_host("example.com", resolve_dns=False)
        did.assert_public_host("Example.COM.", resolve_dns=False)

    def test_a_name_that_resolves_into_a_private_range_is_refused(self):
        # The resolution is the second chance: `evil.example` is a perfectly
        # public name that points at 127.0.0.1.
        infos = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 443))]
        with mock.patch.object(did.socket, "getaddrinfo", return_value=infos):
            with self.assertRaises(did.HostPolicyError):
                did.assert_public_host("evil.example")

    def test_a_name_that_resolves_publicly_is_accepted(self):
        infos = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443))]
        with mock.patch.object(did.socket, "getaddrinfo", return_value=infos):
            did.assert_public_host("example.com")

    def test_an_unresolvable_name_is_a_policy_error_not_a_crash(self):
        with mock.patch.object(did.socket, "getaddrinfo",
                               side_effect=socket.gaierror("no such host")):
            with self.assertRaises(did.HostPolicyError):
                did.assert_public_host("nope.invalid")


class RedirectTests(unittest.TestCase):
    def test_a_redirect_to_plain_http_is_refused(self):
        handler = did._NoDowngradeRedirect()
        with self.assertRaises(did.HostPolicyError):
            handler.redirect_request(None, None, 302, "Found", {}, "http://example.com/d.json")

    def test_a_redirect_to_a_private_host_is_refused(self):
        handler = did._NoDowngradeRedirect()
        with self.assertRaises(did.HostPolicyError):
            handler.redirect_request(None, None, 302, "Found", {}, "https://127.0.0.1/d.json")


class _FakeResponse:
    def __init__(self, chunks, url=REQ):
        self._chunks = list(chunks)
        self._url = url

    def read(self, _n=-1):
        return self._chunks.pop(0) if self._chunks else b""

    def geturl(self):
        return self._url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class ReadCapTests(unittest.TestCase):
    def test_a_document_over_the_cap_is_abandoned(self):
        with self.assertRaises(did.DocumentTooLarge):
            did._read_capped(_FakeResponse([b"x" * 65536] * 9), 512 * 1024)

    def test_a_document_under_the_cap_is_returned_whole(self):
        self.assertEqual(did._read_capped(_FakeResponse([b"{}"]), 512 * 1024), b"{}")

    def test_plaintext_url_never_reaches_a_socket(self):
        with self.assertRaises(did.DIDError):
            did._fetch_json("http://example.com/d.json", 5)

    def test_a_hostile_did_web_is_refused_before_any_request(self):
        # The exact identifier from the harness, which used to fetch from the
        # verifier's own machine on port 8443.
        for value in ("did:web:127.0.0.1%3A8443", "did:web:169.254.169.254",
                      "did:web:localhost", "did:web:metadata.google.internal"):
            with self.subTest(did=value), self.assertRaises(did.HostPolicyError):
                did.resolve(value, timeout=1)


if __name__ == "__main__":
    unittest.main()
