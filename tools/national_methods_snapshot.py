"""Snapshot the national/government-related DID methods from the W3C registry.

Why a snapshot
--------------
"Only N of 282 registered methods are national" is a claim about a moving
registry. If the claim lives only in prose, nobody can tell whether the registry
changed or the prose did. This writes the registry's own answers (contact name,
verifiable data registry, specification URL, status) into one JSON file, for the
methods that look state-related, plus the registry-wide method count.

Refresh with --write (needs network); verify offline with --check.
"""
import argparse, base64, json, os, re, sys, urllib.request

API = "https://api.github.com/repos/w3c/did-extensions"
UA = {"User-Agent": "uibc-national-methods/1.0"}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                   "docs", "NATIONAL-ID-METHODS.json")

# Methods whose registry entry claims a state / national body, or a national
# registry as its verifiable data registry. Everything else stays out on purpose:
# this file is a census of the national subset, not of the whole registry.
CANDIDATES = ["cn", "bid", "cndid", "ioa", "ctid", "kr", "andorra", "pki"]


def get(url):
    return json.load(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=40))


def owner_type(spec):
    """User or Organization for the account hosting the specification.

    A path depth heuristic cannot tell `teleinfo-bif` (org) from `617640999`
    (user), and the difference is the whole point of recording this field, so ask
    the API instead of guessing from the URL shape.
    """
    m = re.match(r"https://(?:www\.)?(github|gitlab)\.com/([A-Za-z0-9._-]+)/", spec or "")
    if not m:
        return None, None
    host, owner = m.group(1), m.group(2)
    if host == "gitlab":
        return owner, "gitlab-host"
    try:
        t = get("https://api.github.com/users/" + owner).get("type")
    except Exception:
        t = "unknown"
    return owner, {"User": "personal-account", "Organization": "org-account"}.get(t, t or "unknown")


def entry(name):
    d = get("%s/contents/methods/%s.json" % (API, name))
    j = json.loads(base64.b64decode(d["content"]).decode("utf-8"))
    owner, kind = owner_type(j.get("specification"))
    return {
        "method": name,
        "status": j.get("status"),
        "contactName": j.get("contactName"),
        "contactEmail": j.get("contactEmail"),
        "vdr": j.get("verifiableDataRegistry"),
        "specification": j.get("specification"),
        "spec_owner": owner,
        "spec_owner_kind": kind,
    }


def build():
    files = [x["name"] for x in get("%s/contents/methods" % API) if x["name"].endswith(".json")]
    entries = []
    for c in CANDIDATES:
        e = entry(c)
        e["in_registry"] = (c + ".json") in files
        entries.append(e)
    return {
        "registry": "W3C DID Methods (w3c/did-extensions, methods/)",
        "registry_url": "https://www.w3.org/TR/did-extensions-methods/",
        "total_methods": len(files),
        "national_related": entries,
        "reading": "registry entries only; a national body named in a contact field is "
                   "not proof that the method is operated, resolvable, or authorised",
    }


def check():
    if not os.path.exists(OUT):
        print("PROBLEM: snapshot missing:", OUT); return 1
    snap = json.load(open(OUT, encoding="utf-8"))
    problems = []
    if snap.get("total_methods", 0) < 200:
        problems.append("total_methods looks wrong: %r" % snap.get("total_methods"))
    seen = [e["method"] for e in snap.get("national_related") or []]
    if seen != CANDIDATES:
        problems.append("national subset changed: %r" % (seen,))
    for e in snap["national_related"]:
        if not e.get("specification"):
            problems.append("%s: no specification URL recorded" % e["method"])
        if e.get("method") == "ctid" and e.get("vdr"):
            problems.append("ctid: vdr is recorded non-empty, but the registry entry has it empty")
    if not snap.get("reading"):
        problems.append("snapshot does not say what it does not prove")
    for p in problems:
        print("PROBLEM:", p)
    print("NATIONAL METHODS OK: %d of %d registry entries, %d national-related"
          % (len(seen), snap["total_methods"], len(seen)) if not problems
          else "NATIONAL METHODS FAILED")
    return 0 if not problems else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="re-fetch from GitHub and rewrite the snapshot")
    ap.add_argument("--check", action="store_true", help="verify the snapshot offline")
    a = ap.parse_args(argv)
    if a.write:
        snap = build()
        open(OUT, "w", encoding="utf-8", newline="\n").write(
            json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
        print("written: %s (%d of %d)" % (OUT, len(snap["national_related"]), snap["total_methods"]))
        return 0
    if a.check:
        return check()
    ap.print_help(); return 2


if __name__ == "__main__":
    sys.exit(main())
