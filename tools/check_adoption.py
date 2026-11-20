"""How many parties outside this repository have adopted this format?

The honest answer for most of this project's life has been "none", and that answer
was written by hand in prose. Prose decays; a check does not. This asks questions
to parties we do not run, and prints what it found — including, in a state of its
own, what it could not ask.

    python3 tools/check_adoption.py              # 0 = measured zero, 1 = signal, 3 = incomplete
    python3 tools/check_adoption.py --json
    python3 tools/check_adoption.py --out report.json

States, per bucket: `measured` (a number, zero or not), `unmeasured` (the source
answered something other than a result), `context` (a number that is real but is
not adoption and must not be summed into it).

The third exit code is the lesson of #263 applied here: a source that refused to
answer is not a zero. A 401 from code search is not evidence that nobody outside
this account emits the identifier; it is evidence that we did not get to ask.
Reporting it as zero is the same defect that made a missing interpreter look like a
corpus that fails everything.
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

OWNER = "zhaoxinghua09-cell"
UA = {"User-Agent": "uibc-core-adoption-check"}
TIMEOUT = 25
LIMITS = [
    "a zero is not proof of absence: it is proof that this search, at this time, found nothing",
    "downloads are not a party: a mirror, a cache and a CI image all download without adopting",
    "a repository naming the format is not a repository emitting it",
    "this measures the format's own coinage only, never an acronym other fields already own",
]


def get(url, token=None, _get=None):
    fetcher = _get or _fetch
    return fetcher(url, token)


def _fetch(url, token=None):
    h = dict(UA)
    if token:
        h["Authorization"] = "Bearer %s" % token
        h["Accept"] = "application/vnd.github+json"
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=TIMEOUT) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"_error": "HTTP %d" % e.code}
    except Exception as e:  # noqa: BLE001
        return {"_error": str(e)[:140]}


def token():
    for var in ("UIBC_ADOPTION_TOKEN", "GITHUB_TOKEN"):
        value = os.environ.get(var)
        if value:
            return value.strip()
    for p in ("/tmp/.ght", os.path.expanduser("~/.ght")):
        try:
            with open(p, encoding="utf-8") as fh:
                return fh.read().strip()
        except OSError:
            continue
    return _gh_token()


def _gh_token():
    """The gh CLI is usually already authenticated; borrow it instead of asking again.

    Borrowed, never stored: the value is used for one request in memory and is not
    written into the report, which records only whether a credential was present.
    """
    try:
        import shutil
        import subprocess
        gh = shutil.which("gh") or r"C:\Program Files\GitHub CLI\gh.exe"
        if not os.path.exists(gh) and not shutil.which("gh"):
            return None
        out = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, timeout=8)
        value = out.stdout.strip()
        return value if out.returncode == 0 and value else None
    except Exception:  # noqa: BLE001
        return None


def _other_accounts(items, key="full_name"):
    return [i for i in items if OWNER not in str(i.get(key, ""))]


def measure(_get=None):
    """Return (buckets, verdict). Pure enough to test: pass a fake `_get`."""
    tok = token()
    buckets = []

    def bucket(name, url, question):
        return {"bucket": name, "question": question, "url": url,
                "state": "unmeasured", "found": None, "sample": [], "error": None}

    hits, err = [], None
    for q in ("uibc-core", "uibc-anchor"):
        url = "https://api.github.com/search/repositories?q=%s+in:name,description&per_page=20" % q
        d = get(url, tok, _get)
        err = err or d.get("_error")
        hits.extend(_other_accounts(d.get("items", [])))
    b = bucket("another repository",
               "https://api.github.com/search/repositories?q=uibc-core+in:name,description",
               "does any repository outside our account exist under the format's own coinage?")
    if err:
        b["error"] = err
    else:
        # The same repository can answer both queries; counting it twice would
        # turn one adoption into two, which is the direction that flatters.
        unique = sorted({h["full_name"] for h in hits})
        b.update(state="measured", found=len(unique), sample=unique[:5])
    buckets.append(b)

    q = urllib.parse.quote('"uibc-anchor/0.1" -user:%s' % OWNER)
    url = "https://api.github.com/search/code?q=%s&per_page=20" % q
    d = get(url, tok, _get)
    b = bucket("another codebase", url,
               "does any code outside our account emit or consume the wire identifier?")
    if d.get("_error"):
        b["error"] = d["_error"]
        if d["_error"] == "HTTP 401":
            b["error"] = "HTTP 401 — code search needs an authenticated request; without one this bucket was not asked"
    else:
        b.update(state="measured", found=d.get("total_count", 0),
                 sample=[i["repository"]["full_name"] for i in d.get("items", [])][:5])
    buckets.append(b)

    url = "https://datatracker.ietf.org/api/v1/doc/document/?name__contains=uibc&format=json"
    d = get(url, tok, _get)
    b = bucket("a standards body", url, "has a standards organisation taken up the name?")
    if d.get("_error"):
        b["error"] = d["_error"]
    else:
        objs = d.get("objects", []) if isinstance(d, dict) else []
        b.update(state="measured", found=len(objs), sample=[o.get("name") for o in objs][:5])
    buckets.append(b)

    url = "https://pypi.org/pypi/agent-action-capsule/json"
    d = get(url, tok, _get)
    b = bucket("a neighbouring spec", url,
               "does the closest adjacent spec name us in its own metadata?")
    if d.get("_error"):
        b["error"] = d["_error"]
    else:
        text = json.dumps(d).lower()
        b.update(state="measured", found=1 if "uibc" in text else 0,
                 sample=["mentions uibc"] if "uibc" in text else [])
    buckets.append(b)

    url = "https://pypistats.org/api/packages/uibc-core/recent"
    d = get(url, tok, _get)
    b = bucket("package downloads", url,
               "how often was the package fetched? (context, not adoption)")
    b["state"] = "context"
    if d.get("_error"):
        b["error"] = d["_error"]
        b["found"] = None
    else:
        b["found"] = (d.get("data") or {}).get("last_month")
        b["sample"] = ["last_month=%s" % b["found"]]
    buckets.append(b)

    measured = [x for x in buckets if x["state"] == "measured"]
    unmeasured = [x for x in buckets if x["state"] == "unmeasured"]
    total = sum(x["found"] for x in measured)
    if unmeasured:
        names = ", ".join("%s (%s)" % (x["bucket"], x["error"]) for x in unmeasured)
        verdict = {"state": "incomplete", "exit": 3, "total": total,
                   "sentence": "INCOMPLETE — %d of %d buckets could not be measured: %s"
                              % (len(unmeasured), len(buckets), names)}
    elif total == 0:
        verdict = {"state": "zero", "exit": 0, "total": 0,
                   "sentence": "ZERO ADOPTION — each bucket was asked and each answered zero"}
    else:
        verdict = {"state": "signal", "exit": 1, "total": total,
                   "sentence": "%d ADOPTION SIGNAL(S) — the status page may now say more than 'zero'"
                              % total}
    verdict["credential"] = "present" if tok else "absent"
    return buckets, verdict

def report(buckets, verdict):
    return {
        "kind": "uibc-adoption-report-v0",
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z"),
        "verdict": verdict,
        "buckets": buckets,
        "limits": LIMITS,
        "how_to_reproduce": "python tools/check_adoption.py --out report.json; "
                            "set UIBC_ADOPTION_TOKEN to let the code-search bucket be asked",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json", action="store_true", help="print the report as JSON")
    parser.add_argument("--out", help="write the dated report here")
    args = parser.parse_args(argv)

    buckets, verdict = measure()
    rep = report(buckets, verdict)

    if args.json:
        print(json.dumps(rep, indent=2))
    else:
        print("%-22s %-11s %6s  %s" % ("bucket", "state", "found", "what"))
        for x in buckets:
            found = "—" if x["found"] is None else str(x["found"])
            print("%-22s %-11s %6s  %s%s" % (x["bucket"], x["state"], found,
                                             ", ".join(str(s) for s in x["sample"]),
                                             ("  [%s]" % x["error"]) if x["error"] else ""))
        print("")
        print("VERDICT: " + verdict["sentence"])
        for limit in LIMITS:
            print(" · " + limit)

    if args.out:
        with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(rep, fh, indent=2)
            fh.write("\n")
        print("\nwritten: %s" % args.out, file=sys.stderr)

    return verdict["exit"]


if __name__ == "__main__":
    sys.exit(main())
