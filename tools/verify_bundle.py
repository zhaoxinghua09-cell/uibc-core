"""Verification bundle: carry every claim needed to re-check a package, but no secret.

Why: Sigstore's bundle packs certificate, signature, timestamp and transparency-log
proof into one file so a stranger can verify offline, with no "best effort" path.
Our packages verify offline too, but the verifier still has to hunt for the pinned
key, the expected head and the remembered state. This tool closes that gap:

  build  : run the verifier once, record artifact digest, verifier identity, the
           inputs that were used, the per-axis outcome and the anchors present.
  verify : take the artifact plus the bundle and the key out of band, recompute
           everything, and say whether the bundle's claim still holds.

The bundle deliberately does NOT embed the owner key: it carries claims and
inputs, not secrets. A key fingerprint lets a caller see whether the key it holds
is the one the bundle was built with.

Usage:
  python tools/verify_bundle.py build  --package <dir> --key <hexfile> --out bundle.json [--expect-head H] [--state S]
  python tools/verify_bundle.py verify --package <dir> --key <hexfile> --bundle bundle.json

Exit: build 0 ok; verify 0 consistent, 1 diverged, 2 artifact changed/harness error.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys

AXES = {
    "structure": ["S11", "S1", "S2", "S3", "S4", "S12", "S14", "S7", "S5", "S8"],
    "seal": ["S6"],
    "anchor": ["S15", "S16"],
    "freshness": ["S9", "S19"],
}


def artifact_digest(path):
    rows = []
    total = 0
    for dirpath, _dirnames, filenames in os.walk(path):
        for fn in filenames:
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, path).replace(os.sep, "/")
            h = hashlib.sha256(open(full, "rb").read()).hexdigest()
            rows.append(f"{rel}\0{h}")
            total += os.path.getsize(full)
    rows.sort()
    d = hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()
    return {"root": "sha256:" + d, "files": len(rows), "bytes": total}


def key_fingerprint(keyfile):
    raw = open(keyfile, "rb").read().strip()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def run_verify(package, key=None, expect_head=None, state=None):
    cmd = [sys.executable, "-m", "uibc_core.cli", "verify", package]
    if key:
        cmd += ["--key", key]
    if expect_head:
        cmd += ["--expect-head", expect_head]
    if state:
        cmd += ["--state-file", state]
    p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    try:
        return json.loads(p.stdout)
    except json.JSONDecodeError:
        raise SystemExit(f"verifier did not return JSON: {p.stderr[-400:]}")


def axes_of(doc):
    by_id = {c["id"]: c["result"] for c in doc.get("checks", [])}
    out = {}
    for axis, ids in AXES.items():
        states = [by_id.get(i, "ABSENT") for i in ids]
        if any(s == "FAIL" for s in states):
            out[axis] = "FAIL"
        elif any(s == "INCONCLUSIVE" for s in states):
            out[axis] = "INCONCLUSIVE"
        elif "PASS" in states:
            out[axis] = "PASS"
        else:
            out[axis] = "N/A"
    return out


def anchors_of(package):
    found = []
    for dirpath, _d, files in os.walk(package):
        for fn in files:
            low = fn.lower()
            if low.endswith((".ots", ".tsr")) or "nostr" in low:
                found.append(os.path.relpath(os.path.join(dirpath, fn), package))
    return sorted(found)


def cmd_build(a):
    doc = run_verify(a.package, a.key, a.expect_head, a.state)
    bundle = {
        "v": "uibc-verify-bundle/1",
        "artifact": artifact_digest(a.package),
        "verifier": {
            "id": doc.get("verifier_id"),
            "version": doc.get("verifier_version"),
            "spec_id": doc.get("spec_id"),
        },
        "inputs": {
            "key_fingerprint": key_fingerprint(a.key) if a.key else None,
            "key_supplied": bool(a.key),
            "expect_head": a.expect_head,
            "state_supplied": bool(a.state),
            "strict": False,
        },
        "result": {
            "verdict": doc.get("result"),
            "trust_level": doc.get("trust_level"),
            "axes": axes_of(doc),
            "first_fail": next((c["id"] for c in doc.get("checks", []) if c["result"] == "FAIL"), None),
            "checks": {c["id"]: c["result"] for c in doc.get("checks", [])},
        },
        "anchors_present": anchors_of(a.package),
        "note": "bundle carries claims and inputs, not secrets; the owner key stays out of band",
    }
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(bundle, f, ensure_ascii=False, indent=2)
    print(f"built {a.out}: verdict={bundle['result']['verdict']} "
          f"axes={bundle['result']['axes']} files={bundle['artifact']['files']}")
    return 0


def cmd_verify(a):
    b = json.load(open(a.bundle, encoding="utf-8"))
    now = artifact_digest(a.package)
    if now["root"] != b["artifact"]["root"]:
        print(f"ARTIFACT CHANGED: bundle={b['artifact']['root']} now={now['root']}")
        return 2
    if a.key and key_fingerprint(a.key) != b["inputs"]["key_fingerprint"]:
        print("KEY DIFFERS: the key supplied is not the one the bundle was built with")
        return 1
    doc = run_verify(a.package, a.key, b["inputs"]["expect_head"], None)
    got = doc.get("result")
    want = b["result"]["verdict"]
    consistent = got == want
    print(f"artifact stable; verdict bundle={want} now={got}; "
          f"{'CONSISTENT' if consistent else 'DIVERGED'}; axes={axes_of(doc)}")
    return 0 if consistent else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--package", required=True)
    b.add_argument("--key")
    b.add_argument("--out", required=True)
    b.add_argument("--expect-head")
    b.add_argument("--state")
    v = sub.add_parser("verify")
    v.add_argument("--package", required=True)
    v.add_argument("--key")
    v.add_argument("--bundle", required=True)
    a = ap.parse_args()
    return cmd_build(a) if a.cmd == "build" else cmd_verify(a)


if __name__ == "__main__":
    sys.exit(main())
