#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pre-push account gate: refuse to push if the credential is not the right account.

Why this exists: on 2026-11-17 a push was made after checking only that the remote
URL pointed at the right repository and that authentication succeeded. Both facts
can be true while the credential belongs to a *different* account that happens to
have write access (collaborator, org member, or a shared token). The account is
now checked before every push instead of after.

    python tools/pre_push_gate.py            # standalone check
    .git/hooks/pre-push                      # installed hook calls this

Exit codes: 0 = identity matches the remote owner (or an explicitly allowed list);
1 = mismatch, unknown owner, or no credential (fail closed).
"""
import json
import os
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitbin  # noqa: E402  (git may be a .cmd shim on Windows)

HOST = "github.com"


def remote_owner(url):
    m = re.search(r"github\.com[:/]([^/]+)/", url or "")
    return m.group(1).lower() if m else None


def stored_secret():
    p = gitbin.run(["credential", "fill"],
                   input="protocol=https\nhost=%s\n\n" % HOST,
                   capture_output=True, text=True)
    for line in (p.stdout or "").splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    return None


def login_of(secret):
    req = urllib.request.Request("https://api.github.com/user", headers={
        "Authorization": "Bearer " + secret,
        "Accept": "application/vnd.github+json",
        "User-Agent": "account-gate/1.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode("utf-8")).get("login")


def main(argv=None):
    # allow an explicit allow-list for repos owned by another account
    # (e.g. an org), never a silent bypass
    allowed = [s.strip().lower() for s in
               (os.environ.get("GIT_ALLOWED_OWNERS") or "").split(",") if s.strip()]

    rc, url, _ = (gitbin.run(["remote", "get-url", "origin"],
                             capture_output=True, text=True).returncode,
                  gitbin.run(["remote", "get-url", "origin"],
                             capture_output=True, text=True).stdout.strip(), "")
    owner = remote_owner(url)
    if not owner:
        print("GATE FAIL: cannot parse a GitHub owner from origin=%r" % url)
        return 1

    secret = stored_secret()
    if not secret:
        print("GATE FAIL: no credential stored for %s" % HOST)
        return 1
    try:
        login = login_of(secret)
    except Exception as exc:
        print("GATE FAIL: cannot resolve the credential's account (%s). "
              "Refusing to push rather than guessing." % exc)
        return 1
    if not login:
        print("GATE FAIL: credential has no login")
        return 1

    who = login.lower()
    ok = (who == owner) or (who in allowed) or (owner in allowed)
    print("remote_owner=%s  credential_login=%s  allowed=%s  -> %s"
          % (owner, login, allowed or "-", "OK" if ok else "MISMATCH"))
    if not ok:
        print("GATE FAIL: this credential belongs to %r, but the remote belongs to "
              "%r. Not pushing. Set GIT_ALLOWED_OWNERS only if this is intended."
              % (login, owner))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
