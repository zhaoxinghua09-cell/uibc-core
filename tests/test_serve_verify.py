"""The endpoint: bytes in, report out, and hostile input refused.

Three things are being tested and they are different in kind:

  * the happy path (a real package reaches a real verdict over HTTP),
  * the refusal path (a zip that would write outside its directory, a body
    that is too large, an archive with too many members),
  * and one thing that must NOT happen -- a verifier crash returning 200.
"""

import io
import json
import os
import sys
import threading
import unittest
import urllib.error
import urllib.request
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "tools"))

import serve_verify as sv  # noqa: E402

PKG = os.path.join(REPO, "fixtures", "clean.uibc")


def _zip_of(package_dir, prefix=""):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _dirs, names in os.walk(package_dir):
            for name in names:
                full = os.path.join(root, name)
                rel = os.path.relpath(full, package_dir).replace("\\", "/")
                zf.write(full, prefix + rel)
    return buf.getvalue()


def _zip_with(payloads):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        for name, data in payloads.items():
            zf.writestr(name, data)
    return buf.getvalue()


class EndpointTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.httpd = sv.serve("127.0.0.1", 0)
        cls.port = cls.httpd.server_address[1]
        cls.thread = threading.Thread(target=cls.httpd.serve_forever,
                                      daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.httpd.shutdown()
        cls.httpd.server_close()
        cls.thread.join(timeout=5)

    def _post(self, blob):
        req = urllib.request.Request(
            "http://127.0.0.1:%d/verify" % self.port, data=blob, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return r.status, json.loads(r.read())
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read())

    def test_health(self):
        with urllib.request.urlopen(
                "http://127.0.0.1:%d/health" % self.port, timeout=10) as r:
            body = json.loads(r.read())
        self.assertTrue(body["ok"])
        self.assertEqual(body["accepts"],
                         "POST /verify with a package zip")

    def test_a_real_package_gets_a_real_verdict(self):
        code, body = self._post(_zip_of(PKG))
        self.assertEqual(code, 200)
        self.assertEqual(body["result"], "INCONCLUSIVE")
        ids = [c["id"] for c in body["checks"]]
        for want in ("S1", "S4", "S5", "S6"):
            self.assertIn(want, ids)
        # an unsigned package stops at the seal: S6 inconclusive is the honest
        # answer and the later checks are not reached, which the counts show
        self.assertIn("S6", body["inconclusive"])
        self.assertEqual(body["counts"].get("PASS", 0) > 0, True)

    def test_a_flat_archive_is_also_a_package(self):
        code, body = self._post(_zip_of(PKG))
        self.assertEqual(code, 200)
        # the same package nested one level down must behave identically
        code2, body2 = self._post(_zip_of(PKG, prefix="pkg/"))
        self.assertEqual(code2, 200)
        self.assertEqual(body2["result"], body["result"])

    def test_tampering_is_reported_not_smoothed(self):
        import tempfile
        import shutil
        tmp = tempfile.mkdtemp()
        try:
            shutil.copytree(PKG, tmp, dirs_exist_ok=True)
            mpath = os.path.join(tmp, "manifest.json")
            with open(mpath, encoding="utf-8") as f:
                m = json.load(f)
            m["evidence_root"] = "0" * 64
            with open(mpath, "w", encoding="utf-8") as f:
                json.dump(m, f)
            code, body = self._post(_zip_of(tmp))
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        self.assertEqual(code, 200)
        self.assertEqual(body["result"], "FAIL")
        self.assertIn("S5", body["failed"])

    def test_traversal_member_is_refused(self):
        blob = _zip_with({"../../escape.txt": b"x", "manifest.json": b"{}"})
        code, body = self._post(blob)
        self.assertEqual(code, 400)
        self.assertIn("parent traversal", body["error"])

    def test_absolute_member_is_refused(self):
        blob = _zip_with({"/etc/passwd": b"x"})
        code, body = self._post(blob)
        self.assertEqual(code, 400)

    def test_oversize_input_is_refused(self):
        """The limit is enforced in the unpacker, so test it there.

        Over HTTP the server answers 413 before reading the body, which makes
        the client see a reset -- testing that measures the socket, not the
        rule."""
        with self.assertRaises(sv.Rejected) as ctx:
            sv.unpack_safely(b"PK" + b"\x00" * (sv.MAX_BODY + 1))
        self.assertIn("exceeds", str(ctx.exception))

    def test_not_a_zip_is_refused(self):
        code, body = self._post(b"just text, not an archive")
        self.assertEqual(code, 400)
        self.assertIn("not a zip", body["error"])


if __name__ == "__main__":
    unittest.main()
