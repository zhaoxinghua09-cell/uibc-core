#!/usr/bin/env python3
"""Ask PyPI whether every file of a release carries a provenance attestation.

This exists because the check it replaces was free-form YAML heredoc: logic that
lives inside a workflow cannot be unit tested, and the release it guarded
(0.5.0) shipped while every provenance URL returned 404. The publish job proved
the *version* existed and never proved the *signal* existed.

Contract:
  exit 0  -> every published file has provenance
  exit 1  -> at least one file lacks it, or there are no files to check
  exit 2  -> could not determine what to check (bad input, PyPI unreachable)

The network calls are injected (`fetch`), so the decision logic is testable
without touching the internet.
"""

import argparse
import json
import sys
import urllib.request

PROVENANCE_URL = "https://pypi.org/integrity/{pkg}/{version}/{filename}/provenance"
RELEASE_URL = "https://pypi.org/pypi/{pkg}/json"
TIMEOUT = 20


def http_get(url, timeout=TIMEOUT):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def files_for_release(pkg, version, fetch=None):
    raw = (fetch or http_get)(RELEASE_URL.format(pkg=pkg))
    data = json.loads(raw)
    return [f["filename"] for f in (data.get("releases") or {}).get(version, [])]


def check(pkg, version, fetch=None):
    """Return (files, missing) where missing is a list of (filename, reason)."""
    fetch = fetch or http_get
    files = files_for_release(pkg, version, fetch=fetch)
    missing = []
    for fn in files:
        url = PROVENANCE_URL.format(pkg=pkg, version=version, filename=fn)
        try:
            fetch(url)
        except Exception as e:  # noqa: BLE001 - any failure means "not present"
            missing.append((fn, "%s: %s" % (type(e).__name__, e)))
    return files, missing


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--pkg", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    a = ap.parse_args(argv)

    try:
        files, missing = check(a.pkg, a.version)
    except Exception as e:  # noqa: BLE001
        print("cannot query PyPI for %s %s: %s: %s" % (a.pkg, a.version, type(e).__name__, e))
        return 2

    if a.json:
        print(json.dumps({"pkg": a.pkg, "version": a.version, "files": files,
                          "missing": [{"file": f, "reason": r} for f, r in missing]}, indent=2))

    if not files:
        print("no files published for %s %s" % (a.pkg, a.version))
        return 1

    for fn in files:
        if fn not in [m[0] for m in missing]:
            print("provenance present: %s" % fn)
    for fn, why in missing:
        print("MISSING provenance: %s (%s)" % (fn, why))

    if missing:
        print("RESULT: %d of %d file(s) lack provenance for %s %s"
              % (len(missing), len(files), a.pkg, a.version))
        return 1
    print("RESULT: all %d file(s) carry provenance for %s %s" % (len(files), a.pkg, a.version))
    return 0


if __name__ == "__main__":
    sys.exit(main())
