"""An endpoint without a limiter is a way to make someone else's CPU bill your
problem. These assertions are about the bucket actually filling, and about the
bucket not being emptyable by a header the caller controls.
"""
import io
import os
import sys
import threading
import time
import unittest
import urllib.error
import urllib.request
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

import serve_verify  # noqa: E402

CLEAN = os.path.join(_REPO, "fixtures", "clean.uibc")


def package_zip():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _d, files in os.walk(CLEAN):
            for name in files:
                full = os.path.join(root, name)
                z.write(full, os.path.relpath(full, CLEAN))
    return buf.getvalue()


def post(port, blob, headers=None):
    req = urllib.request.Request("http://127.0.0.1:%d/verify" % port,
                                 data=blob, method="POST",
                                 headers=headers or {"Content-Type": "application/zip"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, dict(r.headers)
    except urllib.error.HTTPError as exc:
        return exc.code, dict(exc.headers)


class TestBucket(unittest.TestCase):
    def test_bucket_empties_then_refills(self):
        lim = serve_verify.RateLimiter(per_minute=60, burst=3)
        allowed = [lim.take("a")[0] for _ in range(4)]
        self.assertEqual(allowed, [True, True, True, False])
        time.sleep(0.05)   # 60/min is one per second; not enough to refill
        self.assertFalse(lim.take("a")[0])

    def test_zero_rate_disables_the_limit(self):
        lim = serve_verify.RateLimiter(per_minute=0, burst=3)
        self.assertTrue(all(lim.take("a")[0] for _ in range(50)))

    def test_forwarded_header_is_ignored_by_default(self):
        lim = serve_verify.RateLimiter(per_minute=60, burst=2)
        self.assertFalse(lim.trust_forwarded)

    def test_caller_map_does_not_grow_without_bound(self):
        lim = serve_verify.RateLimiter(per_minute=60, burst=2, max_callers=16)
        for i in range(200):
            lim.take("k%d" % i)
        self.assertLessEqual(len(lim._state), 16 + 1)


class TestLiveServer(unittest.TestCase):
    def _serve(self, rate, burst, ready_timeout=2.0):
        """Bind an ephemeral port and wait until it actually answers.

        The four live tests used to hard-code ports 8795-8798 and sleep 0.2 s.
        Both halves of that are a flake waiting to happen: a fixed port on
        Windows can still be in TIME_WAIT from an earlier run, and a 0.2 s sleep
        is a guess about how fast a loaded machine starts a thread. On
        2026-11-21 a full-suite run produced ConnectionResetError (WinError
        10054) on a live test; it passed 4/4 standalone, which is what an
        environment-dependent flake looks like.

        Now: port 0, and readiness is *observed* by polling /health instead of
        slept for. A test that waits for a symptom is steadier than one that
        waits for a duration.
        """
        httpd = serve_verify.serve("127.0.0.1", 0, rate, burst)
        port = httpd.server_address[1]
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        deadline = time.time() + ready_timeout
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(
                        "http://127.0.0.1:%d/health" % port, timeout=1) as r:
                    if r.status == 200:
                        return httpd, port
            except Exception:  # noqa: BLE001 - not ready yet is not a failure
                time.sleep(0.02)
        httpd.shutdown(); httpd.server_close()
        raise AssertionError("server did not become ready within %.1fs" % ready_timeout)

    def test_eleventh_call_in_a_burst_is_refused(self):
        httpd, port = self._serve(60, 10)
        try:
            blob = package_zip()
            codes = [post(port, blob)[0] for _ in range(12)]
            self.assertEqual(codes[:10], [200] * 10,
                             "burst 10 means exactly ten calls from a full bucket")
            self.assertEqual(codes[10], 429, "the eleventh call must be refused")
        finally:
            httpd.shutdown(); httpd.server_close()

    def test_refusal_carries_retry_after(self):
        httpd, port = self._serve(60, 1)
        try:
            blob = package_zip()
            post(port, blob)
            code, headers = post(port, blob)
            self.assertEqual(code, 429)
            self.assertIn("Retry-After", headers)
        finally:
            httpd.shutdown(); httpd.server_close()

    def test_a_spoofed_forwarded_for_does_not_buy_a_new_bucket(self):
        """The header is caller-controlled. If it worked, the limiter would not."""
        httpd, port = self._serve(60, 2)
        try:
            blob = package_zip()
            post(port, blob)
            post(port, blob)
            code, _ = post(port, blob, {"Content-Type": "application/zip",
                                        "X-Forwarded-For": "203.0.113.9"})
            self.assertEqual(code, 429)
        finally:
            httpd.shutdown(); httpd.server_close()

    def test_health_advertises_the_limit(self):
        httpd, port = self._serve(60, 5)
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/health" % port, timeout=10) as r:
                import json as _json
                doc = _json.loads(r.read())
            self.assertEqual(doc["limits"]["requests_per_minute"], 60)
            self.assertEqual(doc["limits"]["burst"], 5)
        finally:
            httpd.shutdown(); httpd.server_close()


if __name__ == "__main__":
    unittest.main()
