"""Tests for the read-only registry HTTP server (stdlib only)."""

import json
import os
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "registry_server"))
from server import REGISTRY_NAMES, load_registry, make_handler  # noqa: E402


class RegistryServerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="regsrv-")
        # one registry has data, others empty
        with open(os.path.join(self.tmp, "revocations.jsonl"), "w",
                  encoding="utf-8") as f:
            f.write(json.dumps({"revocation_id": "r-1", "key_id": "abc",
                                "reason": "key compromise"}) + "\n")
            f.write(json.dumps({"revocation_id": "r-2", "key_id": "def",
                                "reason": "superseded"}) + "\n")
        self.srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.tmp))
        self.port = self.srv.server_address[1]
        threading.Thread(target=self.srv.serve_forever, daemon=True).start()

    def tearDown(self):
        self.srv.shutdown()

    def _get(self, path):
        with urllib.request.urlopen(
                "http://127.0.0.1:%d%s" % (self.port, path), timeout=5) as r:
            return r.status, json.loads(r.read().decode("utf-8"))

    # 1. service info
    def test_01_info(self):
        st, body = self._get("/")
        self.assertEqual(st, 200)
        self.assertTrue(body["read_only"])
        self.assertEqual(sorted(body["registries"]), sorted(REGISTRY_NAMES))

    # 2. health
    def test_02_health(self):
        st, body = self._get("/health")
        self.assertEqual((st, body), (200, {"status": "ok"}))

    # 3. non-empty registry returns parsed entries in order
    def test_03_entries_in_order(self):
        st, body = self._get("/registry/revocations")
        self.assertEqual(st, 200)
        self.assertEqual([e["revocation_id"] for e in body["entries"]],
                         ["r-1", "r-2"])

    # 4. empty/missing registry file -> empty list, not error
    def test_04_empty_registry_is_empty_list(self):
        st, body = self._get("/registry/certificates")
        self.assertEqual((st, body["entries"]), (200, []))

    # 5. unknown registry -> 404
    def test_05_unknown_registry_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._get("/registry/nope")
        self.assertEqual(cm.exception.code, 404)

    # 6. unknown route -> 404
    def test_06_unknown_route_404(self):
        with self.assertRaises(urllib.error.HTTPError) as cm:
            self._get("/whatever")
        self.assertEqual(cm.exception.code, 404)

    # 7. POST is explicitly refused (read-only by design)
    def test_07_post_refused_405(self):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/registry/disputes" % self.port, data=b"{}",
            method="POST")
        with self.assertRaises(urllib.error.HTTPError) as cm:
            urllib.request.urlopen(req, timeout=5)
        self.assertEqual(cm.exception.code, 405)

    # 8. malformed JSONL line -> server surfaces the error honestly (500-family)
    def test_08_malformed_line_not_silently_hidden(self):
        bad = os.path.join(self.tmp, "disputes.jsonl")
        with open(bad, "w", encoding="utf-8") as f:
            f.write("{not json}\n")
        try:
            with self.assertRaises(urllib.error.HTTPError):
                self._get("/registry/disputes")
        finally:
            os.remove(bad)

    # 9. load_registry unit: unknown name raises
    def test_09_load_registry_unknown_name(self):
        with self.assertRaises(ValueError):
            load_registry(self.tmp, "bogus")


if __name__ == "__main__":
    unittest.main()
