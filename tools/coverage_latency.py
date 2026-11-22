"""Measure the coverage-distribution detection latency (local loopback only).

What is being measured: the time between "publisher replaced the coverage
statement on disk and the feed server can serve it" and "a polling verifier
actually holds the new statement". That is the blind window a verifier lives
with. It is bounded by the poll interval, not by the publisher.

What is NOT measured: network propagation across the real internet, the
publisher's own delay in writing the statement, or any third-party attestation.
Those need a real deployment; this number exists so the *poll-side* bound is
measured rather than assumed.

Usage:
  python tools/coverage_latency.py [--trials 20] [--interval 0.2] [--out ...]
"""

import argparse
import json
import os
import random
import statistics
import sys
import tempfile
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.coverage_feed import poll  # noqa: E402


class _NoStoreHandler(SimpleHTTPRequestHandler):
    """Serve the feed without caching, so a poll cannot be answered from cache."""

    def end_headers(self):
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("Pragma", "no-cache")
        super().end_headers()

    def log_message(self, *args):      # keep the measurement output clean
        pass


def _serve(directory):
    handler = lambda *a, **kw: _NoStoreHandler(*a, directory=directory, **kw)  # noqa: E731
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def _write_statement(path, sequence, issued_at):
    statement = {
        "coverage_id": f"lat-{sequence}",
        "target_root": "sha256:" + "0" * 64,
        "issued_at": issued_at,
        "sequence": sequence,
        "no_revocation": True,
        "key_id": "measurement-only",
        "algorithm": "Ed25519",
        "signature": "measurement-only-not-verified-here",
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(statement, fh)
    os.replace(tmp, path)          # atomic publish, like the state file


def _iso_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--interval", type=float, default=0.2, help="poll interval (s)")
    ap.add_argument("--deadline", type=float, default=10.0, help="per-trial deadline (s)")
    ap.add_argument("--out", default=os.path.join("tools", "out", "coverage_latency.json"))
    args = ap.parse_args(argv)

    work = tempfile.mkdtemp(prefix="cov_lat_")
    feed = os.path.join(work, "coverage.json")
    _write_statement(feed, 1, _iso_now())
    httpd, _thread = _serve(work)
    url = f"http://127.0.0.1:{httpd.server_address[1]}/coverage.json"

    samples, misses = [], 0
    try:
        for trial in range(args.trials):
            seq_old = 1 + 2 * trial
            seq_new = seq_old + 1
            _write_statement(feed, seq_old, _iso_now())
            # wait until the verifier actually holds the old statement
            ready = poll(url, lambda c: c.get("sequence") == seq_old,
                         timeout_s=args.deadline, interval_s=args.interval)
            if not ready["ok"]:
                misses += 1
                continue
            # Publish at a random phase inside the poll interval: a real
            # revocation does not wait for the verifier's next GET.
            published = {"t": None}

            def _publish(seq=seq_new, when=published):
                time.sleep(random.uniform(0.0, args.interval))
                _write_statement(feed, seq, _iso_now())
                when["t"] = time.monotonic()

            writer = threading.Thread(target=_publish, daemon=True)
            writer.start()
            seen = poll(url, lambda c: c.get("sequence") == seq_new,
                        timeout_s=args.deadline, interval_s=args.interval)
            writer.join()
            if not seen["ok"] or published["t"] is None:
                misses += 1
                continue
            samples.append(time.monotonic() - published["t"])
    finally:
        httpd.shutdown()
        httpd.server_close()

    result = {
        "schema": "uibc-coverage-latency/1",
        "scope": "local loopback, poll-side detection only",
        "trials_requested": args.trials,
        "trials_measured": len(samples),
        "misses": misses,
        "poll_interval_s": args.interval,
        "latency_ms": {
            "median": round(statistics.median(samples) * 1000, 2) if samples else None,
            "p95": round(sorted(samples)[max(0, int(round(0.95 * len(samples))) - 1)] * 1000, 2)
            if samples else None,
            "max": round(max(samples) * 1000, 2) if samples else None,
        },
        "bound": ("detection latency is bounded by the poll interval plus one GET; "
                  "it is not a delivery guarantee and not a third-party attestation"),
    }
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(result, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"RESULT_JSON={args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
