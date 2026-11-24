"""Hardening tests for did:web resolution (Muse _108 B2).

Three findings, three groups here, each naming what it refuses:

* loopback and private targets are refused by default (assert_public_host);
* a redirect that downgrades https to http is refused (_NoDowngradeRedirect);
* a document over the size cap is refused (enforce_size).

These are the checks themselves, not an end-to-end fetch: they can run without
a network, which is the point -- a hardening rule that only runs when the
network agrees is not a rule.
"""
import unittest

from uibc_core.did import (
    MAX_DOCUMENT_BYTES,
    DIDError,
    _NoDowngradeRedirect,
    assert_public_host,
    enforce_size,
)


class TestLoopbackAndPrivateAreRefused(unittest.TestCase):
    def assertRefused(self, url, because):
        with self.assertRaises(DIDError) as caught:
            assert_public_host(url)
        self.assertIn(because, str(caught.exception).lower())

    def test_ipv4_loopback(self):
        self.assertRefused("https://127.0.0.1/.well-known/did.json", "public address")

    def test_ipv4_loopback_alias(self):
        self.assertRefused("https://127.1.2.3/x", "public address")

    def test_ipv6_loopback(self):
        self.assertRefused("https://[::1]/x", "public address")

    def test_private_ranges(self):
        for host in ("10.0.0.5", "192.168.1.10", "172.16.0.1"):
            with self.subTest(host=host):
                self.assertRefused("https://%s/x" % host, "public address")

    def test_link_local_and_unspecified(self):
        for host in ("169.254.169.254", "0.0.0.0"):
            with self.subTest(host=host):
                self.assertRefused("https://%s/x" % host, "public address")

    def test_localhost_names(self):
        for host in ("localhost", "LOCALHOST", "app.local"):
            with self.subTest(host=host):
                self.assertRefused("https://%s/x" % host, "local host")

    def test_plain_http_is_refused(self):
        self.assertRefused("http://example.com/x", "https")

    def test_public_hosts_pass(self):
        for url in ("https://example.com/x", "https://8.8.8.8/x",
                    "https://sub.example.org/.well-known/did.json"):
            with self.subTest(url=url):
                assert_public_host(url)  # must not raise


class TestRedirectDowngradeIsRefused(unittest.TestCase):
    def test_302_to_plain_http_is_refused(self):
        with self.assertRaises(DIDError) as caught:
            _NoDowngradeRedirect().redirect_request(
                None, None, 302, "Found", {}, "http://example.com/did.json")
        self.assertIn("not https", str(caught.exception).lower())

    def test_302_to_private_https_is_refused(self):
        with self.assertRaises(DIDError) as caught:
            _NoDowngradeRedirect().redirect_request(
                None, None, 302, "Found", {}, "https://10.0.0.5/did.json")
        self.assertIn("public address", str(caught.exception).lower())

    def test_https_to_https_redirect_is_allowed(self):
        # urllib resolves a relative Location before calling this handler, so a
        # hop that stays on https and stays public must go through untouched.
        import urllib.request

        base = urllib.request.Request("https://example.com/.well-known/did.json")
        redirect = _NoDowngradeRedirect().redirect_request(
            base, None, 302, "Found", {}, "https://example.com/other/did.json")
        self.assertIsNotNone(redirect)
        self.assertTrue(redirect.get_full_url().startswith("https://"))


class TestSizeCap(unittest.TestCase):
    def test_declared_length_over_cap_is_refused(self):
        with self.assertRaises(DIDError) as caught:
            enforce_size(str(MAX_DOCUMENT_BYTES + 1), b"{}")
        self.assertIn("over the", str(caught.exception).lower())

    def test_undeclared_but_large_body_is_refused(self):
        with self.assertRaises(DIDError):
            enforce_size(None, b"x" * (MAX_DOCUMENT_BYTES + 1))

    def test_small_document_passes(self):
        enforce_size(str(len(b"{}")), b"{}")
        enforce_size(None, b"{}")

    def test_unparseable_declared_length_falls_back_to_body(self):
        enforce_size("not-a-number", b"{}")


if __name__ == "__main__":
    unittest.main()
