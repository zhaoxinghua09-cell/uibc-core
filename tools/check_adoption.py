"""How many parties outside this repository have adopted this format?

The honest answer for most of this project's life has been "none", and that answer
was written by hand in prose. Prose decays; a check does not. This asks four
questions to four parties we do not run, and prints what it found.

    python3 tools/check_adoption.py          # exits 0 either way, 1 if a bucket went non-zero
    python3 tools/check_adoption.py --json

Buckets:
  1. another repository  - GitHub repo search for the project name, excluding our account
  2. another codebase    - GitHub code search for the anchor schema strings, excluding our account
  3. a standards body    - IETF Datatracker for a draft carrying the name
  4. a neighbouring spec - the nearest SCITT profile, which would name us if it interoperated

A non-zero bucket is not a win to celebrate silently — it changes what the status
page may claim, so it exits 1 and makes someone look.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

OWNER = "zhaoxinghua09-cell"
UA = {"User-Agent": "uibc-core-adoption-check"}


def get(url, token=None):
    h = dict(UA)
    if token:
        h["Authorization"] = "Bearer %s" % token
        h["Accept"] = "application/vnd.github+json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=25) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": "HTTP %d" % e.code}
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)}


def token():
    for p in ("/tmp/.ght", os.path.expanduser("~/.ght")):
        try:
            with open(p, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            continue
    return None


def others(items, key="full_name"):
    return [i for i in items if OWNER not in str(i.get(key, ""))]


def main():
    tok = token()
    out = []

    # "uibc" alone is a name collision with an UPnP protocol and a dozen unrelated
    # repositories; only our own coinage ("uibc-core" / "uibc-anchor") counts.
    hits, err = [], None
    for q in ("uibc-core", "uibc-anchor"):
        d = get("https://api.github.com/search/repositories?q=%s+in:name,description&per_page=20" % q, tok)
        err = err or d.get("_error")
        hits.extend(others(d.get("items", [])))
    names = sorted({h["full_name"] for h in hits} | {h.get("name", "") for h in hits})
    out.append(("another repository", len(hits), sorted({h["full_name"] for h in hits})[:5], err))

    q = urllib.parse.quote('"uibc-anchor/0.1" -user:%s' % OWNER)
    d = get("https://api.github.com/search/code?q=%s&per_page=20" % q, tok)
    out.append(("another codebase", d.get("total_count", 0),
                [i["repository"]["full_name"] for i in d.get("items", [])][:5], d.get("_error")))

    d = get("https://datatracker.ietf.org/api/v1/doc/document/?name__contains=uibc&format=json", tok)
    objs = d.get("objects", []) if isinstance(d, dict) else []
    out.append(("a standards body", len(objs), [o.get("name") for o in objs][:5],
                d.get("_error") if isinstance(d, dict) else None))

    # The nearest profile names interoperating formats in its prose; if it ever
    # names ours, this string is where it would show up.
    d = get("https://pypi.org/pypi/agent-action-capsule/json")
    text = json.dumps(d).lower()
    out.append(("a neighbouring spec", 1 if "uibc" in text else 0,
                ["mentions uibc"] if "uibc" in text else [], d.get("_error")))

    print("%-24s %6s  %s" % ("bucket", "found", "what"))
    total = 0
    for name, n, sample, err in out:
        total += n
        print("%-24s %6d  %s%s" % (name, n, ", ".join(str(s) for s in sample),
                                   ("  [%s]" % err) if err else ""))

    print("")
    if total == 0:
        print("VERDICT: ZERO ADOPTION - no party outside this account has taken up the format")
        rc = 0
    else:
        print("VERDICT: %d ADOPTION SIGNAL(S) - the status page may now say more than 'zero'" % total)
        rc = 1

    if "--json" in sys.argv:
        print(json.dumps([{"bucket": n, "found": c, "sample": s, "error": e} for n, c, s, e in out], indent=2))
    return rc


if __name__ == "__main__":
    sys.exit(main())
