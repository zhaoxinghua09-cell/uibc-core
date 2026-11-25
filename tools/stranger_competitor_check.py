"""One command for a stranger: fetch the corpus, check the bytes, re-run both tools.

The sweep and the mutation control are only as good as a stranger's ability to
reproduce them. Until now that took three things a reader had to get right
themselves -- clone upstream, check out the commit, point two tools at a directory
whose shape they had to guess -- and a reader who gets a step wrong concludes
"does not reproduce" without knowing whether they or we were wrong.

This does those steps in the right order and refuses to continue when they disagree:

  1. fetch the upstream tarball at the pinned commit (or take a local unpacked copy)
  2. digest every one of the 171 files and compare against the receipt we committed
     -- if their bytes are not the bytes we swept, nothing after this is meaningful
  3. run the sweep and the mutation control, and compare their totals against the
     same receipts

Every count printed is compared against a receipt, so "matches" is a comparison and
not a claim. Exit codes: 0 REPRODUCED, 1 DID NOT MATCH (a failing line says which),
2 no corpus in the tarball, 3 PARTIAL.

Dependencies: the byte check and the arithmetic steps need nothing beyond the
standard library. The ledger's signature column needs `cryptography`; without it
the run stops short and says PARTIAL rather than reporting 88 vectors as differing
ones - a missing verifier is not a disagreement with our receipts.

Usage
-----
  python tools/stranger_competitor_check.py                  # fetch and check
  python tools/stranger_competitor_check.py --dir <corpus>   # you already have it
  python tools/stranger_competitor_check.py --json
  python tools/stranger_competitor_check.py --selftest       # no network, no corpus
"""

import argparse
import hashlib
import json
import os
import shutil
import sys
import tarfile
import tempfile

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO = os.path.dirname(_HERE)
sys.path.insert(0, _HERE)
sys.path.insert(0, _REPO)

import sweep_competitor_corpus as sweep
import sweep_mutation_control as control
import build_upstream_ledger as ledger
import crosscheck_competitor_inclusion_sigstore as sigstore_inclusion

UPSTREAM_REPO = "probityai/agent-evidence-vectors"
SWEEP_RECEIPT = os.path.join(_REPO, "docs", "upstream-package", "competitor-defects",
                             "corpus-sweep-39daf704.json")
CONTROL_RECEIPT = os.path.join(_REPO, "docs", "upstream-package", "competitor-defects",
                               "sweep-mutation-control.json")
LEDGER_RECEIPT = ledger.RECEIPT


def _sha256_file(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def verify_bytes(corpus_dir, manifest):
    """Every manifest entry must exist under the corpus and carry its digest."""
    ok, missing, mismatched = 0, [], []
    for entry in manifest["files"]:
        rel = entry["path"].split("corpus/", 1)[-1]
        path = os.path.join(corpus_dir, *rel.split("/"))
        if not os.path.isfile(path):
            missing.append(rel)
            continue
        if _sha256_file(path) != entry["sha256"]:
            mismatched.append(rel)
            continue
        ok += 1
    return {"checked": len(manifest["files"]), "match": ok,
            "missing": sorted(missing), "mismatched": sorted(mismatched)}


def compare_totals(label, got, want, keys):
    """Differences as text; empty means the receipt was reproduced."""
    diffs = []
    for key in keys:
        if key not in want:
            continue
        if got.get(key) != want[key]:
            diffs.append("%s.%s: receipt says %r, this run says %r"
                         % (label, key, want[key], got.get(key)))
    return diffs


def find_corpus(root):
    """The corpus directory inside an unpacked tarball, recognised by its tail.

    The vectors sit one level down (inclusion/, consistency/, token/, chain/,
    canonical/), so a directory that merely contains json is not the corpus; the
    name and the parent's name are what identify it.
    """
    for here, dirs, _files in os.walk(root):
        if os.path.basename(here) != "corpus":
            continue
        if os.path.basename(os.path.dirname(here)) != "poc_evidence_vectors":
            continue
        if dirs:
            return here
    return None


def fetch(commit, workdir):
    """Download and unpack the upstream tarball at a commit. Standard library only."""
    import urllib.request
    url = "https://codeload.github.com/%s/tar.gz/%s" % (UPSTREAM_REPO, commit)
    path = os.path.join(workdir, "upstream.tar.gz")
    with urllib.request.urlopen(url, timeout=180) as resp:
        blob = resp.read()
    with open(path, "wb") as f:
        f.write(blob)
    with tarfile.open(path) as tar:
        try:
            tar.extractall(workdir, filter="data")
        except TypeError:  # Python without the extraction filter argument
            tar.extractall(workdir)
    return find_corpus(workdir), len(blob)


def run(dir_arg=None, verbose=True):
    with open(SWEEP_RECEIPT, encoding="utf-8") as f:
        sweep_receipt = json.load(f)
    with open(CONTROL_RECEIPT, encoding="utf-8") as f:
        control_receipt = json.load(f)
    commit = sweep_receipt.get("head") or "39daf704"

    out = {"upstream": {"repo": UPSTREAM_REPO, "commit": commit},
           "source": "local" if dir_arg else "fetch"}
    workdir = None
    try:
        corpus = dir_arg
        if dir_arg and os.path.basename(dir_arg) != "corpus":
            corpus = find_corpus(dir_arg) or dir_arg
        if not dir_arg:
            workdir = tempfile.mkdtemp(prefix="stranger-")
            corpus, nbytes = fetch(commit, workdir)
            out["tarball_bytes"] = nbytes
            if not corpus:
                out["verdict"] = "no corpus in the tarball"
                out["code"] = 2
                if verbose:
                    print("VERDICT: %s" % out["verdict"])
                return out

        out["bytes"] = verify_bytes(corpus, sweep_receipt["manifest"])
        b = out["bytes"]
        if verbose:
            print("bytes: %d checked, %d match" % (b["checked"], b["match"]))
            for rel in b["missing"][:5]:
                print("  MISSING %s" % rel)
            for rel in b["mismatched"][:5]:
                print("  DIFFERS %s" % rel)
        if b["missing"] or b["mismatched"]:
            out["verdict"] = "bytes are not the bytes we swept"
            out["code"] = 1
            if verbose:
                print("VERDICT: %s" % out["verdict"])
            return out

        out["sweep"] = sweep.run(corpus)["totals"]
        out["control"] = control.control(corpus)["totals"]
        try:
            fresh_ledger = ledger.build(corpus)
            ledger_skipped = None
        except ledger.SignatureLayerUnavailable as e:
            # The arithmetic steps above are complete without any dependency; the
            # ledger's signature column is not. Saying "did not match" here would
            # blame our numbers for a missing library, so this is a separate state.
            fresh_ledger, ledger_skipped = None, str(e)
            out["ledger_skipped"] = ledger_skipped
        out["ledger"] = fresh_ledger["totals"] if fresh_ledger else None
        with open(LEDGER_RECEIPT, encoding="utf-8") as f:
            stored_ledger = f.read()
        diffs = compare_totals("sweep", out["sweep"], sweep_receipt["totals"],
                               ("vectors", "n_replayable", "consistent",
                                "inconsistent", "none"))
        diffs += compare_totals("control", out["control"], control_receipt["totals"],
                                ("applied", "detected", "ambiguous", "unexplained"))
        # The ledger is compared row by row: a single vector whose reach level
        # moved is a difference, not a rounding error.
        if fresh_ledger is not None:
            diffs += ["ledger " + d for d in ledger._compare(
                stored_ledger, ledger._dump(fresh_ledger))]
        # The inclusion vectors are also folded by a vendored third-party
        # implementation; if that stops agreeing, the "independently replayable"
        # half of A18 is what breaks, so it is compared here too.
        fresh_sig = sigstore_inclusion.build(corpus)
        with open(sigstore_inclusion.RECEIPT, encoding="utf-8") as f:
            stored_sig = f.read()
        out["sigstore_inclusion"] = fresh_sig["totals"]
        diffs += ["inclusion " + d for d in
                  sigstore_inclusion._compare(stored_sig, sigstore_inclusion._dump(fresh_sig))]
        out["diffs"] = diffs
        if diffs:
            out["verdict"] = "DID NOT MATCH"
            out["code"] = 1
        elif ledger_skipped:
            out["verdict"] = ("PARTIAL: the arithmetic matched; the ledger's "
                              "signature layer was not evaluated")
            out["code"] = 3
        else:
            out["verdict"] = "REPRODUCED"
            out["code"] = 0
        if verbose:
            s, c, g = out["sweep"], out["control"], out["ledger"]
            print("sweep: %d vectors, %d replayable, %d consistent, %d inconsistent, "
                  "%d not replayable"
                  % (s["vectors"], s["n_replayable"], s["consistent"],
                     s["inconsistent"], s["vectors"] - s["n_replayable"]))
            print("control: %d applied, %d detected, %d ambiguous, %d unexplained"
                  % (c["applied"], c["detected"], c["ambiguous"], c["unexplained"]))
            if g is None:
                print("ledger: SKIPPED - %s" % ledger_skipped)
                if "install" not in ledger_skipped:
                    print("        install it (`pip install cryptography`) and rerun "
                          "for the complete check")
            else:
                print("ledger: %d verdict, %d signature-only, %d nothing, "
                      "%d signatures verify"
                      % (g["verdict"], g["signature-only"], g["nothing"],
                         g["signature_verified"]))
            si = out["sigstore_inclusion"]
            print("inclusion folded by vendored Sigstore: %d of %d agree with the "
                  "published verdict, %d not compared"
                  % (si["agree_with_published"], si["compared"],
                     si["skipped_no_empty_root"] + si["unusable"]))
            for d in diffs:
                print("  DIFF %s" % d)
            print("VERDICT: %s" % out["verdict"])
        return out
    finally:
        if workdir:
            shutil.rmtree(workdir, ignore_errors=True)


def selftest():
    """Changed bytes, a missing file and a moved count must each be caught."""
    root = tempfile.mkdtemp(prefix="stranger-selftest-")
    try:
        corpus = os.path.join(root, "poc_evidence_vectors", "corpus")
        os.makedirs(os.path.join(corpus, "inclusion"))
        good = {"id": "A", "tree_size": 0, "root": sweep.EMPTY_ROOT,
                "expect": {"result": "reject"}}
        path = os.path.join(corpus, "inclusion", "A.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(good, f)
        size = os.path.getsize(path)
        manifest = {"files": [{"path": "corpus/inclusion/A.json",
                               "sha256": _sha256_file(path), "bytes": size}],
                    "count": 1}
        assert verify_bytes(corpus, manifest)["match"] == 1
        # One byte changed and the checker has to say so, by name.
        with open(path, "a", encoding="utf-8") as f:
            f.write(" ")
        v = verify_bytes(corpus, manifest)
        assert v["match"] == 0 and v["mismatched"] == ["inclusion/A.json"], v
        # A missing file is a different failure from a changed one.
        os.unlink(path)
        v = verify_bytes(corpus, manifest)
        assert v["missing"] == ["inclusion/A.json"] and not v["mismatched"], v
        # A count that moves is reported, not rounded away or invented.
        assert compare_totals("sweep", {"n_replayable": 68},
                              {"n_replayable": 69}, ("n_replayable",))
        assert not compare_totals("sweep", {"n_replayable": 69},
                                  {"n_replayable": 69}, ("n_replayable",))
        assert not compare_totals("sweep", {}, {}, ("n_some_key",))
        # find_corpus lands on the corpus, not on some other json directory.
        with open(path, "w", encoding="utf-8") as f:
            json.dump(good, f)
        assert find_corpus(root) == corpus, find_corpus(root)
        print("selftest: bytes, counts and corpus discovery all behave")
        return 0
    finally:
        shutil.rmtree(root, ignore_errors=True)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", help="an already unpacked corpus (skips the download)")
    ap.add_argument("--json", action="store_true",
                    help="print one JSON object and nothing else")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    out = run(a.dir, verbose=not a.json)
    if a.json:
        # One object, nothing else, so a caller can parse it.
        print(json.dumps(out, indent=2, sort_keys=True))
    return out.get("code", 0)


if __name__ == "__main__":
    sys.exit(main())
