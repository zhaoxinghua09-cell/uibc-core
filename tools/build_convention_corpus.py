#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build a corpus whose purpose is to exercise the *convention* axis, not the anchor axis.

Background: the 500-case corpus contains no INCONCLUSIVE verdicts, so 'strict / lenient /
excluded' all return the same rate on it (12.0 / 12.0 / 12.0). The axis is real but unmeasurable
there. This builder produces artifacts that a current verifier genuinely cannot judge, because
they were sealed under a superseded scheme: HMAC-SHA256 (v0.2 lineage) instead of Ed25519.

Each artifact below is a real package, copied from the shipped v0.3 clean sample and then mutated
and re-sealed with the owner's HMAC key — the same construction `fixtures/generate_fixtures.py`
uses. Truth comes from the mutation, never from the verdict.

  family                           truth    expected verdict (0.4.x, open mode)
  forgeries-selfconsistent (24)     harmful  INCONCLUSIVE   (no pinned key can be used: scheme superseded)
  tampered-bytes (10)               harmful  FAIL           (S4 catches it regardless of scheme)
  clean-copies (2)                  benign   INCONCLUSIVE

The result is not a security benchmark. It is a measuring instrument for the question "does
the convention change the number", and it says so in the output.

Usage:
  python build_convention_corpus.py --repo <uibc-core> --uibc <uibc[.exe]> --out DIR
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time

FORGERY_N = 24
TAMPER_N = 10
CLEAN_N = 2


def verify(uibc, pkg):
    p = subprocess.run([uibc, "verify", pkg], capture_output=True, text=True, timeout=120)
    out = (p.stdout or "") + (p.stderr or "")
    try:
        doc = json.loads(out[out.index("{"):out.rindex("}") + 1])
    except Exception:
        return "UNPARSED"
    return doc.get("result", "UNPARSED")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", required=True)
    ap.add_argument("--uibc", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    repo = os.path.abspath(a.repo)
    sys.path.insert(0, os.path.join(repo, "fixtures"))
    import generate_fixtures as gf  # noqa: E402  (needs repo on sys.path)

    seed = os.path.join(repo, "fixtures", "clean.uibc")
    if not os.path.isdir(seed):
        print("MISSING seed: %s" % seed)
        return 2
    outdir = os.path.abspath(a.out)
    pkgs = os.path.join(outdir, "packages")
    os.makedirs(pkgs, exist_ok=True)

    cases = []
    t0 = time.time()

    def reseal_owner(pkg):
        identity = gf._read(os.path.join(pkg, "identity.json"))
        manifest = gf._read(os.path.join(pkg, "manifest.json"))
        gf._write(os.path.join(pkg, "signatures", "seal.json"), {
            "schema": "uibc-core/0.2.0-proposal",
            "algorithm": "HMAC-SHA256",
            "key_id": gf.key_id(gf.OWNER_KEY),
            "signed": "identity+manifest",
            "signature": gf.seal_sign(gf.OWNER_KEY, identity, manifest),
            "created_at": "convention-corpus",
        })

    # 1. self-consistent forgeries: payload replaced, index hash rewritten,
    #    evidence_root recomputed, seal recomputed with the owner key. Nothing
    #    is detectable inside the package; a current verifier cannot judge it.
    for i in range(FORGERY_N):
        name = "forgery-%02d" % i
        dst = os.path.join(pkgs, name + ".uibc")
        shutil.copytree(seed, dst)
        payload = os.path.join(dst, "evidence", "files", "action-log.txt")
        with open(payload, "w", encoding="utf-8", newline="\n") as f:
            f.write("agent fx-agent executed db:%d; result: %d rows; reviewer: forged-%d\n"
                    % (i, 1000 + i, i))
        gf.mut_malicious(dst)
        reseal_owner(dst)
        v = verify(a.uibc, dst)
        cases.append({"id": name, "truth": "harmful", "verdict": v,
                      "family": "forgeries-selfconsistent", "artifact": dst})

    # 2. byte tampering: a content hash check catches it in any scheme.
    for i in range(TAMPER_N):
        name = "tamper-%02d" % i
        dst = os.path.join(pkgs, name + ".uibc")
        shutil.copytree(seed, dst)
        payload = os.path.join(dst, "evidence", "files", "action-log.txt")
        with open(payload, "a", encoding="utf-8", newline="\n") as f:
            f.write("extra-line-%d\n" % i)
        v = verify(a.uibc, dst)
        cases.append({"id": name, "truth": "harmful", "verdict": v,
                      "family": "tampered-bytes", "artifact": dst})

    # 3. untouched copies with a fresh seal: benign, and still unjudgeable under 0.4.x
    for i in range(CLEAN_N):
        name = "clean-%02d" % i
        dst = os.path.join(pkgs, name + ".uibc")
        shutil.copytree(seed, dst)
        reseal_owner(dst)
        v = verify(a.uibc, dst)
        cases.append({"id": name, "truth": "benign", "verdict": v,
                      "family": "clean-copies", "artifact": dst})

    counts = {}
    for c in cases:
        k = (c["truth"], c["verdict"])
        counts["%s/%s" % k] = counts.get("%s/%s" % k, 0) + 1

    payload = {
        "subject": "convention corpus: superseded-scheme artifacts (HMAC v0.2 lineage)",
        "convention_claimed": "unknown",
        "purpose": "exercise the decision-convention axis, not a security benchmark",
        "generated": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "builder": "build_convention_corpus.py",
        "wall_clock_s": round(time.time() - t0, 1),
        "counts": counts,
        "cases": [{"id": c["id"], "truth": c["truth"], "verdict": c["verdict"],
                   "family": c["family"], "artifact": os.path.relpath(c["artifact"], outdir)}
                  for c in cases],
    }
    p = os.path.join(outdir, "convention_corpus.json")
    json.dump(payload, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({"counts": counts, "cases": len(cases),
                      "wall_clock_s": payload["wall_clock_s"], "file": p},
                     ensure_ascii=False, indent=2))
    # A builder that silently produced a uniform verdict set would be useless for its purpose.
    uniq = {c["verdict"] for c in cases}
    if len(uniq) < 2:
        print("!! all verdicts are %r — the convention axis still has nothing to measure" % uniq)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
