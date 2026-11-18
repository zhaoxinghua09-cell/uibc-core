"""A verify endpoint: upload a package, get a verdict.

Every profile in this space eventually gets asked the same question -- "can I
check this without installing anything?" -- and the answer that everyone else
gives is a URL. We had a CLI, an archive, and no endpoint, which is a gap you
can measure by looking at the competitor's page.

    python3 tools/serve_verify.py --port 8770
    curl -X POST --data-binary @pkg.zip http://127.0.0.1:8770/verify

Design constraints, in order of how easy they are to get wrong:

**It only ever sees bytes we accept.** No path parameter, no "verify this
directory on your machine". The request body is the package. That removes the
whole class of bugs where a caller asks the server to read something it was
never meant to read.

**An archive is hostile input.** A zip can carry `../../etc/passwd` as a member
name, tens of thousands of entries, or a decompression bomb. So: names are
checked before extraction, members and unpacked size are capped, and anything
that fails a check is rejected with 400 instead of half-extracted.

**A verdict is not a promise.** The response says what each check found and
which ones were inconclusive. It never says "valid" -- the package decides
that, the endpoint only reports.

Nothing here is exposed to the network by default: it binds 127.0.0.1.
"""

import base64
import io
import json
import os
import shutil
import sys
import tempfile
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

from uibc_core.verify import verify as verify_package  # noqa: E402

MAX_BODY = 8 * 1024 * 1024       # a package is kilobytes; 8 MB is generous
MAX_MEMBERS = 5000
MAX_UNPACKED = 64 * 1024 * 1024


class RateLimiter:
    """A token bucket per caller, because an endpoint without one is a way to
    make someone else's CPU bill your problem.

    Defaults are deliberately low: this is a public verifier for packages of a
    few kilobytes, so sixty calls a minute per address is generous for a human
    and useless for a loop. `0` disables it, which is what a local run wants.
    """

    def __init__(self, per_minute=60, burst=10, max_callers=4096,
                 trust_forwarded=False):
        # A bucket keyed on a header the caller controls is not a limiter: one
        # forged X-Forwarded-For per request and the bucket never fills. So the
        # header is ignored unless the operator says a proxy strips it first.
        self.trust_forwarded = trust_forwarded
        self.per_minute = per_minute
        self.burst = max(1, burst)
        self.rate = per_minute / 60.0
        self.max_callers = max_callers
        self._state = {}
        self._lock = threading.Lock()

    def take(self, key):
        """Return (allowed, retry_after_seconds)."""
        if self.per_minute <= 0:
            return True, 0.0
        now = time.monotonic()
        with self._lock:
            tokens, last = self._state.get(key, (float(self.burst), now))
            tokens = min(float(self.burst), tokens + (now - last) * self.rate)
            if len(self._state) > self.max_callers:
                # Drop the stalest quarter rather than grow without bound.
                for k in sorted(self._state, key=lambda k: self._state[k][1],
                                reverse=True)[: self.max_callers // 4]:
                    self._state.pop(k, None)
            if tokens < 1.0:
                self._state[key] = (tokens, now)
                return False, (1.0 - tokens) / self.rate if self.rate else 60.0
            self._state[key] = (tokens - 1.0, now)
            return True, 0.0


LIMITER = RateLimiter(per_minute=0, burst=10)   # off unless configured


class Rejected(Exception):
    """Input we refuse to unpack. Carries the reason for the 400."""


def _member_problem(name):
    if not name or name.startswith("/") or "\\" in name:
        return "absolute or backslash path: %r" % name
    parts = name.split("/")
    if ".." in parts:
        return "parent traversal in member name: %r" % name
    if len(name) > 255:
        return "member name too long"
    return None


def unpack_safely(blob):
    """Extract a package zip into a temp dir, or raise Rejected."""
    if len(blob) > MAX_BODY:
        raise Rejected("body exceeds %d bytes" % MAX_BODY)
    try:
        zf = zipfile.ZipFile(io.BytesIO(blob))
    except zipfile.BadZipFile:
        raise Rejected("not a zip archive")
    members = zf.infolist()
    if len(members) > MAX_MEMBERS:
        raise Rejected("archive has %d members (max %d)"
                       % (len(members), MAX_MEMBERS))
    total = 0
    for m in members:
        problem = _member_problem(m.filename)
        if problem:
            raise Rejected(problem)
        total += m.file_size
        if total > MAX_UNPACKED:
            raise Rejected("unpacked size exceeds %d bytes" % MAX_UNPACKED)
        if m.is_dir():
            continue
        if m.filename.endswith("/"):
            continue
    tmp = tempfile.mkdtemp(prefix="verify-")
    try:
        zf.extractall(tmp)
        # One top-level directory is the common shape; if the archive has a
        # single one, treat it as the package root.
        entries = os.listdir(tmp)
        if len(entries) == 1 and os.path.isdir(os.path.join(tmp, entries[0])):
            return tmp, os.path.join(tmp, entries[0])
        return tmp, tmp
    except Exception:
        shutil.rmtree(tmp, ignore_errors=True)
        raise


def verdict_for(blob):
    """The whole operation: bytes in, report out."""
    tmp, pkg = unpack_safely(blob)
    try:
        result = verify_package(pkg)
        checks = [{"id": c.get("id"), "name": c.get("name"),
                   "result": c.get("result"), "detail": c.get("detail")}
                  for c in result.get("checks", [])]
        counts = {}
        for c in checks:
            counts[c["result"]] = counts.get(c["result"], 0) + 1
        return {
            "result": result.get("result"),
            "checks": checks,
            "counts": counts,
            "failed": [c["id"] for c in checks if c["result"] == "FAIL"],
            "inconclusive": [c["id"] for c in checks
                             if c["result"] == "INCONCLUSIVE"],
            "note": "the endpoint reports what the package shows; it does not "
                    "assert the package is valid, and it signs nothing",
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "uibc-verify/0.1"

    def _json(self, code, payload):
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def _key(self):
        if LIMITER.trust_forwarded:
            forwarded = self.headers.get("X-Forwarded-For")
            if forwarded:
                return forwarded.split(",")[0].strip()
        return self.client_address[0] if self.client_address else "unknown"

    def do_GET(self):
        if self.path in ("/health", "/"):
            self._json(200, {"ok": True, "service": "uibc-verify",
                             "accepts": "POST /verify with a package zip",
                             "limits": {"body_bytes": MAX_BODY,
                                        "members": MAX_MEMBERS,
                                        "unpacked_bytes": MAX_UNPACKED,
                                        "requests_per_minute": LIMITER.per_minute,
                                        "burst": LIMITER.burst}})
            return
        self._json(404, {"error": "no such route"})

    def do_POST(self):
        if self.path != "/verify":
            self._json(404, {"error": "no such route"})
            return
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            self._json(400, {"error": "empty body"})
            return
        if length > MAX_BODY:
            self._json(413, {"error": "body exceeds %d bytes" % MAX_BODY})
            return
        allowed, retry_after = LIMITER.take(self._key())
        if not allowed:
            self.send_response(429)
            body = json.dumps({"error": "rate limited",
                               "retry_after_seconds": round(retry_after, 2)},
                              indent=2).encode()
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Retry-After", str(int(retry_after) + 1))
            self.end_headers()
            self.wfile.write(body)
            return
        blob = self.rfile.read(length)
        try:
            self._json(200, verdict_for(blob))
        except Rejected as exc:
            self._json(400, {"error": str(exc)})
        except Exception as exc:  # a verifier crash must not look like a verdict
            self._json(500, {"error": "verifier raised: %r" % exc})

    def log_message(self, fmt, *args):
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))


def serve(host="127.0.0.1", port=8770, per_minute=0, burst=10,
          trust_forwarded=False):
    global LIMITER
    LIMITER = RateLimiter(per_minute=per_minute, burst=burst,
                          trust_forwarded=trust_forwarded)
    httpd = ThreadingHTTPServer((host, port), Handler)
    return httpd


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--rate", type=int, default=0,
                    help="requests per minute per caller; 0 disables the limit")
    ap.add_argument("--burst", type=int, default=10)
    ap.add_argument("--trust-forwarded", action="store_true",
                    help="key the limiter on X-Forwarded-For; only behind a "
                         "proxy that overwrites the header")
    args = ap.parse_args()
    httpd = serve(args.host, args.port, args.rate, args.burst,
                  args.trust_forwarded)
    print("listening on http://%s:%d  (POST /verify, %s)"
          % (args.host, args.port,
             "unlimited" if args.rate <= 0 else "%d req/min per caller" % args.rate))
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
        httpd.server_close()


if __name__ == "__main__":
    main()
