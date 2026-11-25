#!/usr/bin/env python3
"""Keep the vendored corpus honest.

`docs/upstream-package/competitor/corpus/` carries the 171 vectors every number
in this repository is computed on. Shipping them removed the download step; it
also created a new way to be wrong -- somebody edits one byte in a vector, and
the receipts that quote 171/69/88/14 keep printing the same digits while the
evidence underneath has moved.

So this tool re-derives the manifest from the bytes on disk rather than trusting
it:

    for every file under the corpus root  ->  sha256, compare with MANIFEST
    recompute the digest over path<TAB>sha256<LF>, sorted
        -> must equal MANIFEST.manifest_digest
        -> and must equal the digest the snapshot receipt recorded for 39daf704

Three agreements, none of which is a restatement of the others: the file list
equals the manifest, the manifest's own digest is what its lines produce, and
that digest is the one the receipt already carried.

    python3 tools/verify_vendored_corpus.py --check
    python3 tools/verify_vendored_corpus.py --json
    python3 tools/verify_vendored_corpus.py --selftest
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CORPUS = os.path.join(HERE, "docs", "upstream-package", "competitor", "corpus")
MANIFEST = os.path.join(HERE, "docs", "upstream-package", "competitor", "MANIFEST.json")
SNAPSHOT = os.path.join(HERE, "docs", "upstream-package", "competitor-defects",
                        "corpus-snapshots-22764551-39daf704.json")
UPSTREAM_COMMIT = "39daf704"


def digest_of(entries):
    body = "".join("%s\t%s\n" % (e["path"], e["sha256"])
                   for e in sorted(entries, key=lambda e: e["path"]))
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def scan(corpus_root):
    """Every file on disk, hashed, path relative to the corpus root."""
    out = []
    for root, dirs, files in os.walk(corpus_root):
        dirs.sort()
        for name in sorted(files):
            full = os.path.join(root, name)
            rel = os.path.relpath(full, corpus_root).replace(os.sep, "/")
            with open(full, "rb") as f:
                out.append({"local": rel, "path": "corpus/" + rel,
                            "sha256": hashlib.sha256(f.read()).hexdigest()})
    return out


def run(corpus_root=CORPUS, manifest_path=MANIFEST, snapshot_path=SNAPSHOT, verbose=True):
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    with open(snapshot_path, encoding="utf-8") as f:
        snapshot = json.load(f)

    on_disk = scan(corpus_root)
    stated = {e["local"]: e for e in manifest["files"]}

    missing = sorted(set(stated) - {e["local"] for e in on_disk})
    extra = sorted({e["local"] for e in on_disk} - set(stated))
    changed = sorted(p for p in set(stated) & {e["local"] for e in on_disk}
                     if stated[p]["sha256"] != next(e["sha256"] for e in on_disk if e["local"] == p))

    redigested = digest_of(on_disk)
    receipt_digest = snapshot.get("b_digest")

    problems = []
    if missing:
        problems.append("missing from disk: %s" % ", ".join(missing[:5]))
    if extra:
        problems.append("not in the manifest: %s" % ", ".join(extra[:5]))
    if changed:
        problems.append("bytes changed: %s" % ", ".join(changed[:5]))
    if redigested != manifest["manifest_digest"]:
        problems.append("digest of the bytes %s != manifest %s"
                        % (redigested[:16], manifest["manifest_digest"][:16]))
    if redigested != receipt_digest:
        problems.append("digest %s != snapshot receipt %s"
                        % (redigested[:16], (receipt_digest or "none")[:16]))

    out = {
        "files": len(on_disk),
        "expected": manifest["file_count"],
        "digest": redigested,
        "manifest_digest": manifest["manifest_digest"],
        "snapshot_digest": receipt_digest,
        "upstream_commit": manifest.get("upstream_commit"),
        "missing": missing, "extra": extra, "changed": changed,
        "problems": problems,
        "verdict": "BYTES MATCH" if not problems else "BYTES DISAGREE",
        "code": 0 if not problems else 1,
    }
    if verbose:
        print("vendored corpus: %d files, upstream %s" % (len(on_disk), out["upstream_commit"]))
        print("digest: %s" % redigested)
        print("manifest: %s" % manifest["manifest_digest"])
        print("snapshot receipt: %s" % receipt_digest)
        print("VERDICT: %s" % ("BYTES MATCH" if not problems else
                               "; ".join(problems)))
    return out


def selftest():
    import shutil
    import tempfile
    ok = []

    def check(name, cond, detail=""):
        ok.append(bool(cond))
        print("%-58s %s %s" % (name, "ok" if cond else "FAIL", "" if cond else detail))

    root = tempfile.mkdtemp(prefix="vendored-")
    try:
        base = run(verbose=False)
        check("the shipped corpus matches its manifest", base["code"] == 0, base["problems"])
        check("its digest is the one in the snapshot receipt",
              base["digest"] == base["snapshot_digest"])
        check("it is 171 files", base["files"] == 171 == base["expected"], base["files"])
        check("upstream commit is recorded", base["upstream_commit"] == UPSTREAM_COMMIT)

        # One byte flipped in one vector must be caught, and named.
        work = os.path.join(root, "corpus")
        shutil.copytree(CORPUS, work)
        victim = sorted(scan(work), key=lambda e: e["local"])[0]["local"]
        path = os.path.join(work, *victim.split("/"))
        blob = bytearray(open(path, "rb").read())
        blob[0] = blob[0] ^ 0x01
        open(path, "wb").write(bytes(blob))
        bad = run(work, verbose=False)
        check("one flipped byte fails", bad["code"] == 1)
        check("and the changed file is named", victim in bad["changed"], bad["changed"])

        # A file added behind the manifest's back is not silently included.
        shutil.copyfile(path, os.path.join(work, "inclusion", "ZZZ-extra.json"))
        extra = run(work, verbose=False)
        check("an extra file fails", extra["code"] == 1)
        check("and the extra file is named", "inclusion/ZZZ-extra.json" in extra["extra"],
              extra["extra"])
    finally:
        shutil.rmtree(root, ignore_errors=True)

    passed = sum(ok)
    print("SELFTEST %s: %d checks" % ("OK" if passed == len(ok) else "FAILED", len(ok)))
    return 0 if passed == len(ok) else 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="verify and exit non-zero on drift")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    out = run(verbose=not a.json)
    if a.json:
        print(json.dumps(out, indent=2, sort_keys=True))
    return out["code"]


if __name__ == "__main__":
    sys.exit(main())
