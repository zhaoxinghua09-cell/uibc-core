"""Census of the whole W3C DID method registry, not just the national subset.

Why this exists
---------------
The national-subset file answers "which of the 282 are state-related". It cannot
answer "how good is the registry itself", and that question decides whether a
state attribution can rest on it. This walks every entry in `methods/` and records
what the entry itself says: whether the verifiable data registry is filled in,
where the specification lives, and what kind of account hosts it.

It deliberately records no judgement about whether a method is *reachable*: a
registry entry has no endpoint field, and inferring one from prose would be
guessing. Reachability is what AITB measures, one method at a time.

Refresh with --write (needs network); verify offline with --check.
"""
import argparse, io, json, os, re, sys, tarfile, urllib.request

API = "https://api.github.com/repos/w3c/did-extensions"
TARBALLS = ["https://codeload.github.com/w3c/did-extensions/tar.gz/refs/heads/main",
            "https://codeload.github.com/w3c/did-extensions/tar.gz/refs/heads/master"]
UA = {"User-Agent": "uibc-registry-census/1.0"}
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "docs", "REGISTRY-CENSUS.json")
MD = os.path.join(ROOT, "docs", "REGISTRY-CENSUS.md")
NATIONAL = os.path.join(ROOT, "docs", "NATIONAL-ID-METHODS.json")
GH_SPEC = re.compile(r"https://(?:www\.)?github\.com/([A-Za-z0-9._-]+)/")
GH_USER = re.compile(r"https://(?:www\.)?github\.com/([A-Za-z0-9._-]+)")


def fetch(url, headers=None, timeout=90):
    req = urllib.request.Request(url, headers=headers or UA)
    return urllib.request.urlopen(req, timeout=timeout).read()


def token():
    t = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    return {"Authorization": "Bearer " + t} if t else {}


def load_entries():
    """All method JSONs, from one tarball when possible, else one request each."""
    for url in TARBALLS:
        try:
            raw = fetch(url)
            out = {}
            with tarfile.open(fileobj=io.BytesIO(raw), mode="r:gz") as tf:
                for m in tf.getmembers():
                    if "/methods/" in m.name and m.name.endswith(".json"):
                        out[os.path.basename(m.name)[:-5]] = json.loads(
                            tf.extractfile(m).read().decode("utf-8"))
            if len(out) > 200:
                return out
        except Exception as e:
            print("tarball %s failed (%s)" % (url, e))
    names = [x["name"][:-5] for x in json.loads(
        fetch(API + "/contents/methods", token())) if x["name"].endswith(".json")]
    out = {}
    for n in names:
        d = json.loads(fetch("%s/contents/methods/%s.json" % (API, n), token()))
        import base64
        out[n] = json.loads(base64.b64decode(d["content"]).decode("utf-8"))
    return out


def owner_kinds(owners):
    """Ask the API whether each GitHub owner is a User or an Organization.

    A URL-depth guess gets this wrong (`teleinfo-bif` reads like a body but is a
    personal account), and this is the field the census is built to expose.
    """
    kinds = {}
    for o in sorted(owners):
        try:
            j = json.loads(fetch("https://api.github.com/users/" + o, token()))
            kinds[o] = {"User": "personal-account",
                        "Organization": "org-account"}.get(j.get("type"), j.get("type") or "unknown")
        except Exception:
            kinds[o] = "unknown"
    return kinds


def as_text(v):
    """The registry uses strings, lists of strings, and occasionally objects."""
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (list, tuple)):
        return "; ".join(as_text(x) for x in v if x is not None)
    if isinstance(v, dict):
        return "; ".join("%s=%s" % (k, as_text(x)) for k, x in v.items())
    return str(v).strip()


def build():
    entries = load_entries()
    rows, owners = [], set()
    for name in sorted(entries):
        j = entries[name]
        spec = as_text(j.get("specification"))
        m = GH_SPEC.match(spec)
        if m:
            owners.add(m.group(1))
        ex = as_text(j.get("example"))
        contact = as_text(j.get("contactName"))
        vdr = as_text(j.get("verifiableDataRegistry"))
        rows.append({
            "method": name,
            "status": j.get("status"),
            "kind_field": j.get("kind"),
            "contactName": contact,
            "has_contact": bool(contact),
            "verifiableDataRegistry": vdr,
            "vdr_empty": not vdr,
            "specification": spec,
            "spec_host": "github" if m else ("none" if not spec else "other"),
            "spec_owner": m.group(1) if m else None,
            "example_prefix_ok": (not ex) or ex.startswith("did:%s:" % name) or ex.startswith("did:%s" % name),
            "definitions": bool(j.get("definitions")),
        })
    kinds = owner_kinds(owners)
    for r in rows:
        r["spec_owner_kind"] = kinds.get(r["spec_owner"]) if r["spec_owner"] else None
    counts = {
        "methods": len(rows),
        "vdr_empty": sum(1 for r in rows if r["vdr_empty"]),
        "vdr_present": sum(1 for r in rows if not r["vdr_empty"]),
        "no_specification": sum(1 for r in rows if r["spec_host"] == "none"),
        "spec_on_github": sum(1 for r in rows if r["spec_host"] == "github"),
        "spec_other_host": sum(1 for r in rows if r["spec_host"] == "other"),
        "github_personal": sum(1 for r in rows if r["spec_owner_kind"] == "personal-account"),
        "github_org": sum(1 for r in rows if r["spec_owner_kind"] == "org-account"),
        "example_prefix_mismatch": sum(1 for r in rows if not r["example_prefix_ok"]),
        "with_contact": sum(1 for r in rows if r["has_contact"]),
        "status_registered": sum(1 for r in rows if (r["status"] or "").lower() == "registered"),
        "status_deprecated": sum(1 for r in rows if (r["status"] or "").lower() == "deprecated"),
        "empty_vdr_methods": [r["method"] for r in rows if r["vdr_empty"]],
        "no_spec_methods": [r["method"] for r in rows if r["spec_host"] == "none"],
        "deprecated_methods": [r["method"] for r in rows if (r["status"] or "").lower() == "deprecated"],
    }
    return {
        "registry": "W3C DID Methods registry (w3c/did-extensions, methods/)",
        "registry_url": "https://www.w3.org/TR/did-extensions-methods/",
        "counts": counts,
        "owner_kinds": {k: kinds[k] for k in sorted(kinds)},
        "methods": rows,
        "reading": "what the registry entries say, nothing about whether a method resolves, "
                   "is operated, or is authorised. An empty verifiableDataRegistry is a gap "
                   "in the entry, not evidence that no registry exists; a personal account "
                   "hosting a specification is a hosting fact, not a claim about who wrote it",
    }


def md(snap):
    c = snap["counts"]
    lines = [
        "# Registry census, all %d methods" % c["methods"],
        "",
        "Facts: current. Regenerate with `python tools/registry_census.py --write`, verify with `--check`.",
        "",
        "Everyone quotes \"282 DID methods\". Almost nobody has counted what the entries themselves contain.",
        "This counts four things per entry, and nothing else: the verifiable data registry field, the",
        "specification URL, the kind of account hosting that URL, and whether the example identifier",
        "agrees with the method's own name.",
        "",
        "| what the entry says | count | share |",
        "|---|---|---|",
        "| entries in `methods/` | %d | 100%% |" % c["methods"],
        "| verifiable data registry **empty** | %d | %.1f%% |" % (c["vdr_empty"], 100.0 * c["vdr_empty"] / c["methods"]),
        "| verifiable data registry filled | %d | %.1f%% |" % (c["vdr_present"], 100.0 * c["vdr_present"] / c["methods"]),
        "| no specification URL at all | %d | %.1f%% |" % (c["no_specification"], 100.0 * c["no_specification"] / c["methods"]),
        "| specification hosted on GitHub | %d | %.1f%% |" % (c["spec_on_github"], 100.0 * c["spec_on_github"] / c["methods"]),
        "| — of those, **personal account** | %d | %.1f%% |" % (c["github_personal"], 100.0 * c["github_personal"] / c["methods"]),
        "| — of those, organisation account | %d | %.1f%% |" % (c["github_org"], 100.0 * c["github_org"] / c["methods"]),
        "| specification on some other host | %d | %.1f%% |" % (c["spec_other_host"], 100.0 * c["spec_other_host"] / c["methods"]),
        "| example identifier disagrees with the method name | %d | %.1f%% |" % (c["example_prefix_mismatch"], 100.0 * c["example_prefix_mismatch"] / c["methods"]),
        "| entry carries a contact name | %d | %.1f%% |" % (c["with_contact"], 100.0 * c["with_contact"] / c["methods"]),
        "| status `registered` | %d | %.1f%% |" % (c["status_registered"], 100.0 * c["status_registered"] / c["methods"]),
        "| status `deprecated` | %d | %.1f%% |" % (c["status_deprecated"], 100.0 * c["status_deprecated"] / c["methods"]),
        "",
        "The entries with no verifiable data registry are: %s." % ", ".join(
            "`%s`" % m for m in c["empty_vdr_methods"]),
        "The entries with no specification URL are: %s." % ", ".join(
            "`%s`" % m for m in c["no_spec_methods"]),
        "The deprecated ones are: %s." % ", ".join("`%s`" % m for m in c["deprecated_methods"]),
        "",
        "## What this number means for a resolver",
        "",
        "An empty `verifiableDataRegistry` means the entry does not say where identifiers live. That is",
        "not the same as \"no registry exists\" — it means a reader cannot check the method's own account of",
        "itself, and a resolver built from it is resolving against something the entry never described.",
        "",
        "Specifications hosted on a personal account are checkable but not durable: the account can",
        "disappear, the repository can be force-pushed, and the registry keeps pointing at it. The census",
        "records which ones, so the question can be asked by name instead of in aggregate.",
        "",
        "## What this census does not claim",
        "",
        snap["reading"] + ".",
        "",
        "Nor does it claim any of the %d methods can be resolved: the registry has no endpoint field."
        % c["methods"],
    ]
    return "\n".join(lines) + "\n"


def check():
    problems = []
    if not os.path.exists(OUT):
        print("PROBLEM: census missing:", OUT); return 1
    snap = json.load(open(OUT, encoding="utf-8"))
    rows = snap.get("methods") or []
    c = snap.get("counts") or {}
    if len(rows) < 250:
        problems.append("only %d methods recorded" % len(rows))
    names = [r["method"] for r in rows]
    if len(set(names)) != len(names):
        problems.append("duplicate method rows")
    if names != sorted(names):
        problems.append("rows are not in a stable order")
    recomputed = {
        "vdr_empty": sum(1 for r in rows if r["vdr_empty"]),
        "spec_on_github": sum(1 for r in rows if r["spec_host"] == "github"),
        "github_personal": sum(1 for r in rows if r["spec_owner_kind"] == "personal-account"),
    }
    for k, v in recomputed.items():
        if c.get(k) != v:
            problems.append("counts.%s says %r, rows say %r" % (k, c.get(k), v))
    for k in ("vdr_present", "no_specification", "spec_other_host", "github_org", "with_contact",
              "example_prefix_mismatch", "status_registered", "status_deprecated"):
        if k not in c:
            problems.append("counts missing %s" % k)
    for k in ("empty_vdr_methods", "no_spec_methods", "deprecated_methods"):
        if not isinstance(c.get(k), list):
            problems.append("counts.%s is not a list" % k)
    if c.get("vdr_empty") != len(c.get("empty_vdr_methods") or []):
        problems.append("empty_vdr_methods does not match vdr_empty")
    if "ctid" not in (c.get("empty_vdr_methods") or []):
        problems.append("ctid is no longer listed as an empty-VDR entry: the ctid review rests on that")
    if c.get("methods") != len(rows):
        problems.append("counts.methods does not equal the row count")
    for r in rows:
        if r["spec_host"] == "none" and r["specification"]:
            problems.append("%s: spec_host=none but a URL is recorded" % r["method"])
        if r["spec_host"] == "github" and not r["spec_owner"]:
            problems.append("%s: github host without an owner" % r["method"])
        if r["spec_owner_kind"] not in (None, "personal-account", "org-account", "unknown"):
            problems.append("%s: unexpected owner kind %r" % (r["method"], r["spec_owner_kind"]))
    if not snap.get("reading"):
        problems.append("census does not say what it does not prove")
    if os.path.exists(MD):
        text = open(MD, encoding="utf-8").read()
        for needle in ("all %d methods" % c.get("methods"),
                       "| verifiable data registry **empty** | %d |" % c.get("vdr_empty"),
                       "| — of those, **personal account** | %d |" % c.get("github_personal")):
            if needle not in text:
                problems.append("REGISTRY-CENSUS.md does not carry %r" % needle)
    else:
        problems.append("REGISTRY-CENSUS.md missing")
    if os.path.exists(NATIONAL):
        nat = json.load(open(NATIONAL, encoding="utf-8"))
        if nat.get("total_methods") and nat["total_methods"] != c.get("methods"):
            problems.append("the two files disagree on the registry total: %r vs %r"
                            % (nat["total_methods"], c.get("methods")))
        by = {r["method"]: r for r in rows}
        for e in nat.get("national_related") or []:
            r = by.get(e["method"])
            if not r:
                problems.append("%s is in the national subset but not in the census" % e["method"])
            elif (r.get("specification") or "") != (e.get("specification") or ""):
                problems.append("%s: specification differs between the two files" % e["method"])
    for p in problems:
        print("PROBLEM:", p)
    print("REGISTRY CENSUS OK: %d methods, %d empty VDR, %d on personal accounts"
          % (len(rows), c.get("vdr_empty"), c.get("github_personal")) if not problems
          else "REGISTRY CENSUS FAILED")
    return 0 if not problems else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true", help="re-fetch and rewrite the census")
    ap.add_argument("--check", action="store_true", help="verify the census offline")
    a = ap.parse_args(argv)
    if a.write:
        snap = build()
        open(OUT, "w", encoding="utf-8", newline="\n").write(
            json.dumps(snap, ensure_ascii=False, indent=1) + "\n")
        open(MD, "w", encoding="utf-8", newline="\n").write(md(snap))
        print("written: %s + %s (%d methods)" % (OUT, MD, snap["counts"]["methods"]))
        return 0
    if a.check:
        return check()
    ap.print_help(); return 2


if __name__ == "__main__":
    sys.exit(main())
