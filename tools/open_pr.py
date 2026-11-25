#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Open (or reuse) a pull request and merge it, using the account this repo belongs to.

Why a script: `git push origin main` is refused by branch protection, and opening a PR
through the web UI is a manual step. This does the same two calls through the API,
verifies *which account* the token belongs to before writing anything (the three keys
on this machine belong to three different identities, and shipping theory artefacts
under the wrong one has happened before), and refuses to touch a repo the token cannot
write to.

CLI:
  python tools/open_pr.py --head release/v1.1-precheck --base main            # dry-run, prints plan
  python tools/open_pr.py --head release/v1.1-precheck --base main --go       # create/merge
"""

import json
import os
import re
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gh_api  # noqa: E402  (keeps the credential across a 307, refuses cross-host)

API = "https://api.github.com"
EXPECTED_LOGIN = "zhaoxinghua09-cell"
OWNER = "zhaoxinghua09-cell"
REPO = "uibc-core"
VAULT_SCRIPT = r"D:\标准\vault\get_github_pat.ps1"


def tokens():
    """Tokens never live in this repo: env first, then the DPAPI vault on this machine."""
    env = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if env:
        return [env.strip()]
    import shutil
    import subprocess
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        raise SystemExit("no PowerShell found to read the DPAPI vault")
    found = []
    for account in ("zhaoxinghua09-cell", "stevenzhao07", "LGD-Eval"):
        if not os.path.exists(VAULT_SCRIPT):
            break
        r = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                            "-File", VAULT_SCRIPT, "-Account", account],
                           capture_output=True, text=True, timeout=60)
        tok = (r.stdout or "").strip().splitlines()[-1].strip() if (r.stdout or "").strip() else ""
        if len(tok) >= 20 and not tok.lower().startswith(("exception", "error")):
            found.append(tok)
    if not found:
        raise SystemExit("no GitHub token available (env GITHUB_TOKEN unset and vault unreadable)")
    return found


def call(url, token, method="GET", payload=None):
    """One request through gh_api, which re-sends 307 on the same host with the token.

    A repository that has moved answers 307 to `api.github.com/repositories/<id>`.
    Following it with urllib's own handler is fine on one host and a token leak on
    two, so the hop is ours to take.
    """
    return gh_api.request(url, token=token, method=method, payload=payload)


def pick_token():
    for t in tokens():
        st, who = call(f"{API}/user", t)
        if st != 200:
            continue
        login = who.get("login", "")
        print(f"  token tail ...{t[-4:]} -> login={login}")
        if login == EXPECTED_LOGIN:
            return t, login
    raise SystemExit(f"no token belongs to {EXPECTED_LOGIN}; refuse to write")


def main(argv):
    def arg(name, default=None):
        return argv[argv.index(name) + 1] if name in argv else default

    go = "--go" in argv
    head = arg("--head", "release/v1.1-precheck")
    base = arg("--base", "main")
    title = arg("--title", "release: v1.1 precheck — external review, conformance corpus, measured peers")
    body = arg("--body", "")

    print("== account check ==")
    token, login = pick_token()
    st, repo = call(f"{API}/repos/{OWNER}/{REPO}", token)
    if st != 200:
        raise SystemExit("cannot read repo: %s" % st)
    perm = repo.get("permissions", {}).get("push")
    print(f"  repo {OWNER}/{REPO} push={perm}")
    if not perm:
        raise SystemExit("token has no push permission on this repo; refuse to open a PR")

    st, pulls = call(f"{API}/repos/{OWNER}/{REPO}/pulls?state=open&head={OWNER}:{head}", token)
    existing = None
    if st == 200 and isinstance(pulls, list) and pulls:
        existing = pulls[0]
        print(f"  open PR #{existing['number']} already exists: {existing['title']}")

    if not go:
        print(f"\nDRY-RUN: would open PR {head} -> {base}" if not existing
              else f"\nDRY-RUN: would merge PR #{existing['number']}")
        return 0

    if existing is None:
        st, pr = call(f"{API}/repos/{OWNER}/{REPO}/pulls", token, "POST",
                      {"head": head, "base": base, "title": title, "body": body})
        if st not in (200, 201):
            print("PR creation failed: %s %s" % (st, pr.get("message")))
            return 1
        print(f"  opened PR #{pr['number']}: {pr['html_url']}")
        number = pr["number"]
    else:
        number = existing["number"]

    st, res = call(f"{API}/repos/{OWNER}/{REPO}/pulls/{number}/merge", token, "PUT",
                   {"merge_method": "merge",
                    "commit_title": f"merge: {head} -> {base} (#{number})"})
    print(f"  merge -> {st} merged={res.get('merged')} sha={str(res.get('sha'))[:9]} msg={res.get('message','')}")
    if st == 405:
        print("  (branch protection or not mergeable yet — PR is open, leaving it for review)")
        return 0
    return 0 if (st == 200 and res.get("merged")) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
