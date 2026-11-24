"""Probe the AIP reference implementation repositories for anonymously readable code.

The claim under test is "the seven-part standard has a code reference implementation".
This script asks a narrower question: what can a third party, with no account and no
token, actually read from those repositories?

Run:  python tools/probe_reference_repos.py
Exit: 0 if every probe completed (whatever the counts were); 1 if any request failed.
Output is a table of repo -> branch -> number of readable blobs -> first paths.
"""

from __future__ import annotations

import json
import sys
import urllib.request

API = "https://atomgit.com/api/v5/repos/AIP-PUB/{repo}/git/trees/{branch}?recursive=1"
UA = {"User-Agent": "uibc-core-probe"}

REPOS = [
    ("ACPs-community", "main"),
    ("ACPs-SDK", "master"),
    ("ACPs-CA-Server", "master"),
    ("ACPs-CA-Client", "master"),
    ("ACPs-CA-Challenge", "master"),
    ("ACPs-Registry-Server", "master"),
    ("ACPs-Discovery-Server", "master"),
    ("ACPs-Demo-Project", "master"),
    ("Agent-Interconnection-Protocol-Project", "master"),
]


def probe(repo: str, branch: str, timeout: float = 25.0) -> dict:
    url = API.format(repo=repo, branch=branch)
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed host
        payload = json.loads(resp.read().decode("utf-8"))
    blobs = [e["path"] for e in payload.get("tree", []) if e.get("type") == "blob"]
    return {"repo": repo, "branch": branch, "blobs": len(blobs), "paths": blobs[:6]}


def main() -> int:
    failed = False
    print(f"{'repo':<34}{'branch':<9}{'blobs':>6}  first paths")
    for repo, branch in REPOS:
        try:
            r = probe(repo, branch)
        except Exception as exc:  # noqa: BLE001 - probe reports, never raises
            failed = True
            print(f"{repo:<34}{branch:<9}{'-':>6}  ERROR {exc}")
            continue
        head = " | ".join(r["paths"]) if r["paths"] else "(no files)"
        print(f"{r['repo']:<34}{r['branch']:<9}{r['blobs']:>6}  {head}")
    print()
    print("A tree containing only README.md means: no anonymous reader can inspect the code.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
