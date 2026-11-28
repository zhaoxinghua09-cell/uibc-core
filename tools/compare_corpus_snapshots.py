"""Compare two snapshots of somebody's corpus without shipping either of them.

One sweep at one commit answers "what were the bytes on that day". A reader is
entitled to ask the next question: did they fix it, and is your number therefore
stale? Typing "we also looked at the earlier head and it was the same" is not an
answer -- it is a memory. So both snapshots get a digest of their file list, and the
comparison is arithmetic:

    manifest_digest = sha256 over "path<TAB>sha256<LF>" for every entry, sorted

Two manifests with the same digest are the same 171 files, byte for byte, and that
digest is cheap enough to keep for a snapshot whose full file list we do not ship.
The consequence is worth stating plainly: a snapshot receipt can carry a digest
instead of 171 lines, and a later reader can prove it against the snapshot whose
lines we do ship.

Usage
-----
  python tools/compare_corpus_snapshots.py --a A.json --b B.json [--json]
  python tools/compare_corpus_snapshots.py --a A.json --b B.json --write out.json
  python tools/compare_corpus_snapshots.py --selftest
"""

import argparse
import hashlib
import json
import sys


def manifest_digest(entries):
    """One digest for a file list: sorted path, tab, digest, newline."""
    body = "".join("%s\t%s\n" % (e["path"], e["sha256"])
                   for e in sorted(entries, key=lambda e: e["path"]))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def _entries(snapshot):
    """Either the full file list or nothing; a digest alone cannot be diffed."""
    files = (snapshot.get("manifest") or {}).get("files")
    if files:
        return files
    return None


def compare(a, b):
    """What changed between two snapshots, named per file."""
    out = {"a": a.get("head"), "b": b.get("head")}
    ea, eb = _entries(a), _entries(b)
    out["a_count"] = (a.get("manifest") or {}).get("count", len(ea or []))
    out["b_count"] = (b.get("manifest") or {}).get("count", len(eb or []))
    out["a_digest"] = a.get("manifest_digest") or (
        manifest_digest(ea) if ea else None)
    out["b_digest"] = b.get("manifest_digest") or (
        manifest_digest(eb) if eb else None)

    if ea is None or eb is None:
        # No per-file list on one side: the digests are the whole answer.
        out["method"] = "digest only"
        out["changed"] = None if out["a_digest"] != out["b_digest"] else []
        out["verdict"] = ("IDENTICAL" if out["a_digest"] == out["b_digest"]
                          else "DIFFERENT - a full file list is needed to name what")
        return out

    sa = {e["path"]: e["sha256"] for e in ea}
    sb = {e["path"]: e["sha256"] for e in eb}
    out["method"] = "per file"
    out["changed"] = sorted(p for p in sa if p in sb and sa[p] != sb[p])
    out["added"] = sorted(set(sb) - set(sa))
    out["removed"] = sorted(set(sa) - set(sb))
    out["verdict"] = ("IDENTICAL" if not (out["changed"] or out["added"]
                                         or out["removed"]) else "DIFFERENT")
    return out


def selftest():
    """Same list must come out identical; one nibble must be named."""
    files = [{"path": "corpus/inclusion/A.json", "sha256": "a" * 64},
             {"path": "corpus/token/B.json", "sha256": "b" * 64}]
    a = {"head": "H1", "manifest": {"files": files, "count": len(files)}}
    b = {"head": "H1", "manifest": {"files": list(files), "count": len(files)}}
    r = compare(a, b)
    assert r["verdict"] == "IDENTICAL", r
    assert r["changed"] == [], r
    # Order in the list must not matter; that is what sorting is for.
    assert manifest_digest(list(reversed(files))) == manifest_digest(files)
    # One nibble in one file is a different snapshot, by name.
    files2 = [dict(files[0], sha256="a" * 63 + "0"), dict(files[1])]
    b2 = {"head": "H2", "manifest": {"files": files2, "count": len(files2)}}
    r = compare(a, b2)
    assert r["verdict"] == "DIFFERENT" and r["changed"] == ["corpus/inclusion/A.json"], r
    # An added or a removed file is not a "change" and must not be hidden in it.
    b3 = {"head": "H3", "manifest": {"files": files[:1], "count": 1}}
    r = compare(a, b3)
    assert r["removed"] == ["corpus/token/B.json"] and not r["changed"], r
    # A digest-only receipt compares by digest and refuses to name what moved.
    d = {"head": "H4", "manifest_digest": manifest_digest(files), "manifest": {"count": len(files)}}
    r = compare(a, d)
    assert r["verdict"] == "IDENTICAL" and r["method"] == "digest only", r
    e = {"head": "H5", "manifest_digest": "0" * 64, "manifest": {"count": len(files)}}
    r = compare(a, e)
    assert r["verdict"].startswith("DIFFERENT"), r
    print("selftest: identical, changed, added and digest-only all behave")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", metavar="PATH")
    ap.add_argument("--b", metavar="PATH")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--write", metavar="PATH")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if not (a.a and a.b):
        ap.error("--a and --b are required unless --selftest")
    with open(a.a, encoding="utf-8") as f:
        left = json.load(f)
    with open(a.b, encoding="utf-8") as f:
        right = json.load(f)
    r = compare(left, right)
    if a.write:
        with open(a.write, "w", encoding="utf-8", newline="\n") as f:
            json.dump(r, f, indent=2, sort_keys=True)
            f.write("\n")
    if a.json:
        print(json.dumps(r, indent=2, sort_keys=True))
        return 0
    print("%s vs %s: %s" % (r["a"], r["b"], r["verdict"]))
    print("  files %s / %s, method %s" % (r["a_count"], r["b_count"], r["method"]))
    print("  manifest digest %s.. / %s.." % ((r["a_digest"] or "")[:16],
                                             (r["b_digest"] or "")[:16]))
    for key in ("changed", "added", "removed"):
        if r.get(key):
            print("  %s %d: %s" % (key, len(r[key]), r[key][:3]))
    return 0 if r["verdict"] == "IDENTICAL" else 1


if __name__ == "__main__":
    sys.exit(main())
