#!/usr/bin/env python3
"""Measure the verify endpoint under concurrency, and prove the limiter bites.

Two runs, because they answer two different questions:

- unlimited: what does one process do when nobody is throttling it? This is the
  number a stranger cares about when deciding whether to run one themselves.
- limited: does the bucket actually return 429 instead of quietly absorbing
  everything? A limiter nobody has watched fire is a limiter nobody knows works.

    python3 tools/stress_verify.py --workers 16 --requests 400
"""
import argparse
import json
import os
import statistics
import sys
import threading
import time
import urllib.error
import urllib.request
import zipfile
import io

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
                rel = os.path.relpath(full, CLEAN)
                z.write(full, rel)
    return buf.getvalue()


def one(port, blob, out):
    start = time.perf_counter()
    req = urllib.request.Request("http://127.0.0.1:%d/verify" % port,
                                 data=blob, method="POST",
                                 headers={"Content-Type": "application/zip"})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            out.append((time.perf_counter() - start, resp.status))
    except urllib.error.HTTPError as exc:
        out.append((time.perf_counter() - start, exc.code))
    except Exception:
        out.append((time.perf_counter() - start, 0))


def drive(port, blob, workers, total):
    lat, codes = [], []
    per = max(1, total // workers)
    def run():
        local = []
        for _ in range(per):
            one(port, blob, local)
        lat.extend([x[0] for x in local])
        codes.extend([x[1] for x in local])
    threads = [threading.Thread(target=run) for _ in range(workers)]
    t0 = time.perf_counter()
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    elapsed = time.perf_counter() - t0
    n = len(lat)
    lat.sort()
    return {
        "requests": n,
        "seconds": round(elapsed, 2),
        "throughput_rps": round(n / elapsed, 1) if elapsed else None,
        "p50_ms": round(statistics.median(lat) * 1000, 1),
        "p95_ms": round(lat[min(n - 1, int(n * 0.95))] * 1000, 1),
        "p99_ms": round(lat[min(n - 1, int(n * 0.99))] * 1000, 1),
        "codes": {str(c): codes.count(c) for c in sorted(set(codes))},
    }


def run(port, per_minute, burst, workers, total):
    httpd = serve_verify.serve("127.0.0.1", port, per_minute, burst)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.3)
    try:
        blob = package_zip()
        return drive(port, blob, workers, total)
    finally:
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--requests", type=int, default=400)
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    unlimited = run(a.port, 0, 10, a.workers, a.requests)
    limited = run(a.port + 1, 60, 10, a.workers, a.requests)
    out = {"workers": a.workers, "requests_per_run": unlimited["requests"],
           "unlimited": unlimited, "limited_60_per_min_burst_10": limited}
    if a.json:
        print(json.dumps(out, indent=2))
    else:
        for name in ("unlimited", "limited_60_per_min_burst_10"):
            r = out[name]
            print("%-26s %s req in %ss  %.1f rps  p50 %.1f  p95 %.1f  p99 %.1f ms  %s"
                  % (name, r["requests"], r["seconds"], r["throughput_rps"],
                     r["p50_ms"], r["p95_ms"], r["p99_ms"], r["codes"]))
