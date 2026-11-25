"""The 307 in #71, turned into something that can fail.

`FG-TIDA/use-cases` moved; the old path 307s to a numeric repository id on the
same host. A client that lets the redirect machine drop its `Authorization` sends
the write anonymously and is told `401 Requires authentication` -- a message that
sends you looking at permissions for two days.

Two properties are pinned here:
  * same host: the credential survives the hop, and so do the method and body;
  * different host: the call raises instead of forwarding the token.
"""

import http.server
import json
import os
import sys
import threading
import unittest
import urllib.parse

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import gh_api  # noqa: E402

SECRET = "b" + "0" * 39


class _Handler(http.server.BaseHTTPRequestHandler):
    seen = []

    def log_message(self, *args):
        pass

    def _redirect(self, code, target):
        self.send_response(code)
        self.send_header("Location", target)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_POST(self):
        _Handler.seen.append({"path": self.path, "method": "POST",
                              "auth": self.headers.get("Authorization")})
        length = int(self.headers.get("Content-Length") or 0)
        self.rfile.read(length)
        self.do_GET()

    def do_GET(self):
        path = urllib.parse.urlsplit(self.path).path
        if path == "/old":
            return self._redirect(307, "/new")
        if path == "/old-post":
            return self._redirect(307, "/new")
        if path == "/cross":
            port = self.server.other_port
            return self._redirect(307, "http://localhost:%d/new" % port)
        if path == "/new":
            if self.headers.get("Authorization") != "Bearer " + SECRET:
                self.send_response(401)
                self.send_header("Content-Length", "2")
                self.end_headers()
                self.wfile.write(b"{}")
                return
            body = json.dumps({"ok": True, "path": self.path}).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.send_header("Content-Length", "2")
        self.end_headers()
        self.wfile.write(b"{}")


class RedirectKeepsCredentialTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
        cls.port = cls.server.server_address[1]
        cls.server.other_port = cls.port
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base = "http://127.0.0.1:%d" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def setUp(self):
        _Handler.seen.clear()

    def test_same_host_307_keeps_the_credential_and_the_method(self):
        status, body = gh_api.request(self.base + "/old-post", token=SECRET, method="POST",
                                      payload={"x": 1})
        self.assertEqual(status, 200, body)
        self.assertTrue(body.get("ok"))
        self.assertEqual(_Handler.seen[-1]["method"], "POST", "the method was downgraded")
        self.assertEqual(_Handler.seen[-1]["auth"], "Bearer " + SECRET,
                         "the credential was dropped on the redirect")

    def test_a_cross_host_redirect_is_refused_not_followed(self):
        with self.assertRaises(gh_api.CrossHostRedirect):
            gh_api.request(self.base + "/cross", token=SECRET)
        self.assertFalse([s for s in _Handler.seen if s["path"].startswith("/new")
                          and s["auth"] == "Bearer " + SECRET],
                         "the token was forwarded to another host")

    def test_a_plain_401_is_returned_not_swallowed(self):
        status, body = gh_api.request(self.base + "/new", token=None)
        self.assertEqual(status, 401)
        self.assertEqual(body, {})


if __name__ == "__main__":
    unittest.main()
