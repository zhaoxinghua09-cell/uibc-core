#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Record where the release actually is: local head vs the public branch.

The board must not claim the world has what we have locally. When the network is
down, `git ls-remote` fails - that failure IS the status, and it is written into
the JSON rather than glossed over.

    python tools/release_status.py
"""
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "tools", "out", "release_status.json")
BRANCH = "release/v1.1-precheck"


def git(*args, timeout=25):
    try:
        r = subprocess.run(["git"] + list(args), cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout)
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as exc:
        return 1, "", str(exc)


def main():
    rc, head, _ = git("rev-parse", "HEAD")
    rc2, remote, err2 = git("ls-remote", "origin", BRANCH)
    remote_sha = remote.split()[0] if rc2 == 0 and remote else None
    status = {
        "when_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "branch": BRANCH,
        "local_head": head if rc == 0 else None,
        "public_head": remote_sha,
        "reachable": rc2 == 0,
        "in_sync": bool(remote_sha and head and remote_sha == head),
        "unreachable_reason": None if rc2 == 0 else (err2.splitlines()[-1] if err2 else "unknown"),
    }
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)
    print("local=%s public=%s in_sync=%s" % (status["local_head"], status["public_head"],
                                             status["in_sync"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
