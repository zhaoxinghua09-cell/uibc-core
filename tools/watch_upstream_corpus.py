"""Notice the day somebody else's corpus moves, instead of noticing a year later.

`corpus-sweep-39daf704.json` is a statement about 171 files on one day. Its
manifest makes the statement checkable, but nothing checked it again: if the
upstream project adds, removes or edits a vector, our page keeps quoting 69 of 171
about bytes that no longer exist -- and the failure mode is silent, because a
stale page reads exactly like a fresh one.

This fetches the upstream corpus at its current head, digests it, and compares
against the receipt we committed:

  NO DRIFT   the head's corpus is the same files with the same digests
  DRIFT      named changes, by file, with counts -- and a non-zero exit so a
             scheduled job turns red instead of printing a line nobody reads

It compares, it does not update. Re-running the sweep and rewriting the receipt is
a human decision (the numbers change, so a doc, a picture and a register row have
to change with them); this tool's job is only to make sure the decision is not
missed.

Usage
-----
  python tools/watch_upstream_corpus.py                # upstream main
  python tools/watch_upstream_corpus.py --ref <sha>    # a specific commit
  python tools/watch_upstream_corpus.py --dir <corpus> # bytes you already have
  python tools/watch_upstream_corpus.py --json
  python tools/watch_upstream_corpus.py --selftest     # no network
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _REPO)

import sweep_competitor_corpus as sweep
from compare_corpus_snapshots import compare, manifest_digest
from stranger_competitor_check import fetch, find_corpus

UPSTREAM_REPO = "probityai/agent-evidence-vectors"
RECEIPT = os.path.join(_REPO, "docs", "upstream-package", "competitor-defects",
                       "corpus-sweep-39daf704.json")


def _head_sha(ref):
    """The commit a moving ref currently points at (public repo, no token needed)."""
    import urllib.request
    url = "https://api.github.com/repos/%s/commits/%s" % (UPSTREAM_REPO, ref)
    req = urllib.request.Request(url)
    req.add_header("Accept", "application/vnd.github+json")
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())["sha"]


def snapshot(corpus_dir, head):
    m = sweep.manifest(corpus_dir)
    return {"head": head, "manifest": {"files": m["files"], "count": m["count"]},
            "manifest_digest": manifest_digest(m["files"])}


def watch(ref=None, dir_arg=None, verbose=True):
    with open(RECEIPT, encoding="utf-8") as f:
        ours = json.load(f)
    workdir = None
    try:
        if dir_arg:
            corpus = dir_arg
            if os.path.basename(dir_arg) != "corpus":
                corpus = find_corpus(dir_arg) or dir_arg
            head = ref or "local"
        else:
            if not ref:
                ref = "main"
            head = _head_sha(ref)
            workdir = tempfile.mkdtemp(prefix="watch-")
            corpus, nbytes = fetch(head, workdir)
            if not corpus:
                if verbose:
                    print("VERDICT: no corpus in %s" % head)
                return 2, {"head": head, "verdict": "no corpus"}
        theirs = snapshot(corpus, head)
        r = compare(ours, theirs)
        r["upstream_tarball_bytes"] = nbytes if not dir_arg else None
        if verbose:
            print("receipt: %s (%d files, digest %s..)"
                  % (ours.get("head"), ours["manifest"]["count"],
                     (ours.get("manifest_digest") or "")[:16] or "-"))
            print("upstream: %s (%d files, digest %s..)"
                  % (str(head)[:12], theirs["manifest"]["count"],
                     theirs["manifest_digest"][:16]))
            print("VERDICT: %s" % ("NO DRIFT" if r["verdict"] == "IDENTICAL"
                                   else "DRIFT"))
            for key in ("changed", "added", "removed"):
                if r.get(key):
                    print("  %s %d: %s%s" % (key, len(r[key]), r[key][:3],
                                             "" if len(r[key]) <= 3 else " ..."))
        return (0 if r["verdict"] == "IDENTICAL" else 1), r
    finally:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)


def selftest():
    """Drift must be named per file, and a missing vector is drift too."""
    root = tempfile.mkdtemp(prefix="watch-selftest-")
    try:
        def make(name, files):
            d = os.path.join(root, name, "poc_evidence_vectors", "corpus")
            for rel, body in files.items():
                path = os.path.join(d, *rel.split("/"))
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(body)
            return d

        a = make("a", {"inclusion/A.json": "{}", "token/B.json": '{"x":1}'})
        b = make("b", {"inclusion/A.json": "{}", "token/B.json": '{"x":1}'})
        same = compare(snapshot(a, "A"), snapshot(b, "B"))
        assert same["verdict"] == "IDENTICAL", same

        c = make("c", {"inclusion/A.json": "{} ", "token/B.json": '{"x":1}'})
        moved = compare(snapshot(a, "A"), snapshot(c, "C"))
        assert moved["verdict"] == "DIFFERENT", moved
        assert moved["changed"] == ["corpus/inclusion/A.json"], moved

        d = make("d", {"inclusion/A.json": "{}"})
        gone = compare(snapshot(a, "A"), snapshot(d, "D"))
        assert gone["removed"] == ["corpus/token/B.json"], gone

        e = make("e", {"inclusion/A.json": "{}", "token/B.json": '{"x":1}',
                       "chain/C.json": "[]"})
        added = compare(snapshot(a, "A"), snapshot(e, "E"))
        assert added["added"] == ["corpus/chain/C.json"], added
        # find_corpus must land on a corpus, whatever the wrapper directory is called.
        assert find_corpus(os.path.join(root, "a")) == a
        print("selftest: identical, changed, removed and added all behave")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref", help="upstream ref or sha (default: main)")
    ap.add_argument("--dir", help="an already unpacked corpus")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    code, r = watch(a.ref, a.dir, verbose=not a.json)
    if a.json:
        print(json.dumps(r, indent=2, sort_keys=True))
    return code


if __name__ == "__main__":
    sys.exit(main())

