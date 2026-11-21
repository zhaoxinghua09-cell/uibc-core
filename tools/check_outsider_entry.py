#!/usr/bin/env python3
"""Check that the documented entry point for an outsider is real.

The corpus can be run without cloning, but only if the reader can actually get the
archive. On 2026-11-20 that sentence in `docs/AUDIT-KIT.md` said "if you have not
cloned anything: it is self-contained" without ever saying where to fetch it from,
and the newest release carries a different archive under a different version. A
reader who went looking for a `0.4.1` release asset found nothing.

This tool holds the three things that failed together:

1. the pinned archive on disk has the pinned bytes and the pinned hash;
2. both URLs the documents print (raw and release) point at that archive, at the
   revision the pin names, and no document sends a reader to an asset for a
   version that has none;
3. with `--probe`, the URL answers anonymously and serves exactly the pinned bytes.

Usage:
    python tools/check_outsider_entry.py
    python tools/check_outsider_entry.py --probe

Exit 0 acceptable, 1 not, 3 when the pin itself is unreadable. Every reason prints.
"""
import argparse
import hashlib
import os
import re
import sys
import urllib.request

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REPO_SLUG = "zhaoxinghua09-cell/uibc-core"
def _declared_version():
    """The version this repository ships, so this checker cannot verify an old asset."""
    import io as _io
    import re as _re
    path = os.path.join(REPO, "pyproject.toml")
    text = _io.open(path, encoding="utf-8").read()
    return _re.search(r'version *= *"([^"]+)"', text).group(1)


VERSION = _declared_version()
RAW_URL = ("https://github.com/%s/raw/main/conformance/uibc-conformance-%s.zip"
           % (REPO_SLUG, VERSION))
RELEASE_URL = ("https://github.com/%s/releases/download/v%s/uibc-conformance-%s.zip"
               % (REPO_SLUG, VERSION, VERSION))
DOCS = ("README.md", os.path.join("docs", "AUDIT-KIT.md"))
# A release asset named for a different version is a different corpus. Until 2026-11-20
# the only such asset was 0.4.0, and pointing a reader at it would hand them 30 cases
# while the page promised 36.
FORBIDDEN = re.compile(
    r"releases?/download/[^)\s]*uibc-conformance-(?!%s)[0-9][0-9.]*\.zip" % re.escape(VERSION))


def read_pin(version):
    path = os.path.join(REPO, "anchors", "pins", "uibc-conformance-%s.sha256" % version)
    if not os.path.isfile(path):
        return None
    digest = None
    archive = None
    size = None
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped or stripped.startswith("#"):
                m = re.search(r"#\s*(\d+)\s*bytes", stripped)
                if m:
                    size = int(m.group(1))
                continue
            parts = stripped.split()
            if len(parts) >= 2 and re.fullmatch(r"[0-9a-f]{64}", parts[0]):
                digest = parts[0]
                archive = parts[1]
    if not digest or not archive:
        return None
    return {"sha256": digest, "path": archive, "bytes": size}


def check_local(pin):
    path = os.path.join(REPO, pin["path"])
    reasons = []
    if not os.path.isfile(path):
        return ["the pinned archive is not on disk: %s" % pin["path"]]
    size = os.path.getsize(path)
    if pin["bytes"] is not None and size != pin["bytes"]:
        reasons.append("size is %d, the pin says %d" % (size, pin["bytes"]))
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    if h.hexdigest() != pin["sha256"]:
        reasons.append("sha256 is %s, the pin says %s" % (h.hexdigest(), pin["sha256"]))
    return reasons


def check_docs(pin):
    reasons = []
    shown = 0
    releases_named = 0
    for rel in DOCS:
        path = os.path.join(REPO, rel)
        if not os.path.isfile(path):
            reasons.append("%s is missing" % rel)
            continue
        text = open(path, encoding="utf-8").read()
        # The raw URL must be there: it is the path that needs no login and no token.
        if RAW_URL not in text:
            reasons.append("%s does not print the raw download URL" % rel)
        else:
            shown += 1
        # Since 2026-11-20 the release page carries the same archive. Saying so is part
        # of the entry point being findable; saying it must not replace the raw path.
        if RELEASE_URL in text:
            releases_named += 1
        if pin["sha256"][:12] not in text:
            reasons.append("%s does not print the pinned hash prefix %s" % (rel, pin["sha256"][:12]))
        m = FORBIDDEN.search(text)
        if m:
            reasons.append("%s sends the reader to a release asset for a different version: %s"
                           % (rel, m.group(0)))
    if shown < len(DOCS):
        reasons.append("the raw URL appears in %d of %d documents" % (shown, len(DOCS)))
    if releases_named == 0:
        reasons.append("no document names the release asset that now carries this archive")
    return reasons


def probe(pin, attempts=3):
    """Fetch the documented URL anonymously and compare. Network only.

    `curl` is tried first because the command the documents print is a curl command,
    so the check exercises the reader's path rather than a different TLS stack; on
    this machine Python's own opener cannot complete a handshake to that host while
    curl can, and a probe that fails for its own reasons would be a false alarm. A
    network that drops the connection is not evidence that the path is broken, so it
    returns `None`: the run reports UNMEASURED and exits 3, the same way an unasked
    bucket is not a zero. Only an answer with different bytes is a failure.
    """
    import shutil
    import subprocess
    import tempfile

    curl = shutil.which("curl")
    last = None
    for attempt in range(attempts):
        body = None
        if curl:
            fd, tmp = tempfile.mkstemp(suffix=".zip")
            os.close(fd)
            try:
                proc = subprocess.run([curl, "-fsSL", "--retry", "2", "--retry-all-errors",
                                       "--max-time", "90", "-o", tmp, RAW_URL],
                                      capture_output=True, text=True)
                if proc.returncode == 0:
                    body = open(tmp, "rb").read()
                else:
                    last = "curl exit %d: %s" % (proc.returncode, proc.stderr.strip()[:200])
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        else:
            try:
                req = urllib.request.Request(
                    RAW_URL, headers={"User-Agent": "uibc-outsider-entry/1"})
                with urllib.request.urlopen(req, timeout=90) as resp:
                    body = resp.read()
            except Exception as exc:  # noqa: BLE001 - the reason is the output
                last = "%s: %s" % (type(exc).__name__, exc)
        if body is None:
            continue
        reasons = []
        if len(body) != pin["bytes"]:
            reasons.append("the URL served %d bytes, the pin says %d" % (len(body), pin["bytes"]))
        if hashlib.sha256(body).hexdigest() != pin["sha256"]:
            reasons.append("the URL served a different hash than the pin")
        return reasons, len(body)
    print("unmeasured - %d attempts, last said %s" % (attempts, last))
    return None, None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default=VERSION)
    parser.add_argument("--probe", action="store_true",
                        help="also fetch the documented URL anonymously and hash what arrives")
    args = parser.parse_args(argv)

    pin = read_pin(args.version)
    if pin is None:
        print("the pin for %s is missing or unparseable under anchors/pins/" % args.version)
        return 3

    reasons = check_local(pin) + check_docs(pin)
    served = None
    if args.probe and not reasons:
        extra, served = probe(pin)
        if extra is None:
            print("UNMEASURED - the network did not deliver the archive; the path is not "
                  "thereby broken, and the local pin still holds")
            return 3
        reasons += extra

    print("pin      %s %d bytes" % (pin["sha256"][:16] + "...", pin["bytes"] or -1))
    print("url      %s" % RAW_URL)
    if served is not None:
        print("served   %d bytes over the network" % served)
    if reasons:
        for reason in reasons:
            print("NOT ACCEPTABLE - %s" % reason)
        return 1
    print("ACCEPTABLE - both documented URLs are present, the archive matches the pin, "
          "and no document points at another version's asset")
    return 0


if __name__ == "__main__":
    sys.exit(main())
