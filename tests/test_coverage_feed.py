"""Tests for the coverage distribution channel (HTTP pull).

The point of these tests is the fail-closed direction: a feed that cannot be
read must never turn into ALLOW. The positive case exists only to prove the
channel actually carries a statement the gate accepts.
"""

import base64
import json
import os
import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import test_gate as tg                                    # noqa: E402  (package builder lives there)
from uibc_core import ed25519 as ed                       # noqa: E402
from uibc_core.coverage_feed import ChannelError, fetch, poll  # noqa: E402
from uibc_core.gate import gate                           # noqa: E402
from uibc_core.signing import ed_key_id, ed_public_key    # noqa: E402


class _Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def _serve(directory):
    httpd = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        lambda *a, **kw: _Handler(*a, directory=directory, **kw))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


def _iso_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _statement(target_root, seed, seq=1, issued=None):
    body = {
        "coverage_id": f"ch-{seq}",
        "target_root": target_root,
        "issued_at": issued or _iso_now(),
        "sequence": seq,
        "no_revocation": True,
        "key_id": ed_key_id(ed_public_key(seed)),
        "algorithm": "Ed25519",
    }
    sig = base64.b64encode(ed.sign(seed, tg._canonical_sig_payload(body))).decode("ascii")
    return dict(body, signature=sig)


class FetchTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="covfeed_")
        with open(os.path.join(self.tmp, "coverage.json"), "w", encoding="utf-8") as fh:
            json.dump({"sequence": 1}, fh)
        self.httpd = _serve(self.tmp)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_fetch_returns_object(self):
        self.assertEqual(fetch(self.base + "/coverage.json"), {"sequence": 1})

    def test_fetch_404_is_channel_error(self):
        with self.assertRaises(ChannelError) as ctx:
            fetch(self.base + "/absent.json")
        self.assertIn("HTTP 404", str(ctx.exception))

    def test_fetch_non_json_is_channel_error(self):
        path = os.path.join(self.tmp, "junk.json")
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("not json")
        with self.assertRaises(ChannelError):
            fetch(self.base + "/junk.json")

    def test_poll_times_out_without_target(self):
        out = poll(self.base + "/coverage.json", lambda c: c.get("sequence") < 0,
                   timeout_s=0.6, interval_s=0.1)
        self.assertFalse(out["ok"])
        self.assertGreaterEqual(out["polls"], 1)
        self.assertEqual(out["cov"], {"sequence": 1})

    def test_poll_observes_replacement(self):
        # 时序脆点（2026-11-24 实测）：原来用 `threading.Timer(0.25, ...)` 定时替换，
        # 整仓 1,500+ 用例并行跑时这条定时线程可能被饿到 5 秒窗口之外，poll 于是超时——
        # 单跑必过、全量跑偶发失败（uibc-bench D1 在 Windows 上撞到一次，单条复跑 PASS）。
        # 改成"轮询真的开始之后才替换"，把"定时"换成"先后关系"，与机器负载无关。
        path = os.path.join(self.tmp, "coverage.json")
        first_poll = threading.Event()

        def replace():
            first_poll.wait(10.0)          # 等到 poll 至少读过一次，再替换
            time.sleep(0.05)
            tmp = path + ".tmp"
            with open(tmp, "w", encoding="utf-8") as fh:
                json.dump({"sequence": 2}, fh)
            os.replace(tmp, path)

        worker = threading.Thread(target=replace, daemon=True)
        worker.start()

        def is_new(c):
            first_poll.set()
            return c.get("sequence") == 2

        out = poll(self.base + "/coverage.json", is_new, timeout_s=10.0, interval_s=0.1)
        worker.join(5.0)
        self.assertTrue(out["ok"], "the replacement was never observed: %r" % (out,))
        self.assertGreaterEqual(out["latency_s"], 0.0)

    def test_poll_reports_last_error_when_feed_dies(self):
        url = "http://127.0.0.1:1/coverage.json"      # nothing listens there
        out = poll(url, lambda c: True, timeout_s=0.5, interval_s=0.1)
        self.assertFalse(out["ok"])
        self.assertIsNotNone(out["last_error"])


class GateChannelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="covgate_")
        self.pkg, self.keyfile = tg._make_pkg(self.tmp, sign_ed=True)
        self.seed = tg._seed_from_keyfile(self.keyfile)
        self.pub = ed_public_key(self.seed)
        self.feed_dir = os.path.join(self.tmp, "feed")
        os.makedirs(self.feed_dir, exist_ok=True)
        statement = _statement(tg._read_manifest_root(self.pkg), self.seed, seq=2)
        with open(os.path.join(self.feed_dir, "coverage.json"), "w", encoding="utf-8") as fh:
            json.dump(statement, fh)
        self.httpd = _serve(self.feed_dir)
        self.url = (f"http://127.0.0.1:{self.httpd.server_address[1]}"
                    "/coverage.json")

    def tearDown(self):
        self.httpd.shutdown()
        self.httpd.server_close()

    def test_verified_statement_over_http_allows(self):
        state = os.path.join(self.tmp, "state.json")
        out = gate(self.pkg, pubkey=self.pub, coverage_url=self.url,
                   coverage_state_path=state)
        self.assertEqual(out["decision"], "ALLOW")
        self.assertEqual(out["coverage"]["status"], "VERIFIED")

    def test_unreachable_feed_holds_not_allows(self):
        out = gate(self.pkg, pubkey=self.pub,
                   coverage_url="http://127.0.0.1:1/coverage.json",
                   coverage_channel_timeout_s=1.0)
        self.assertEqual(out["decision"], "HOLD")
        self.assertEqual(out["exit_code"], 3)
        self.assertEqual(out["coverage"]["status"], "UNREACHABLE")
        self.assertIn("unreachable", out["coverage"]["detail"])

    def test_absent_from_feed_holds_when_required(self):
        # feed serves a statement for a different evidence_root -> MISMATCH, HOLD
        statement = _statement("sha256:" + "1" * 64, self.seed, seq=3)
        with open(os.path.join(self.feed_dir, "wrong.json"), "w", encoding="utf-8") as fh:
            json.dump(statement, fh)
        out = gate(self.pkg, pubkey=self.pub,
                   coverage_url=self.url.rsplit("/", 1)[0] + "/wrong.json")
        self.assertEqual(out["decision"], "HOLD")
        self.assertEqual(out["coverage"]["status"], "MISMATCH")


if __name__ == "__main__":
    unittest.main()
