"""Verification bundle: one file that carries every claim needed to re-check a package.

The owner key never goes in the bundle. What travels is what a stranger needs to
reproduce the verdict: the artifact digest, the verifier identity, the inputs that
were used (by fingerprint, not by value), the per-axis outcome and the anchors
already present in the package.

Why a digest and not the package: a bundle that embedded the artifact would make
"the bundle verified" and "this package verified" the same sentence. Keeping them
apart is the point - the reader supplies the artifact and the key; the bundle
supplies the claims and the inputs.
"""
import hashlib
import json
import os

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
            rows.append(rel + "\0" + hashlib.sha256(open(full, "rb").read()).hexdigest())
            total += os.path.getsize(full)
    rows.sort()
    return {"root": "sha256:" + hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest(),
            "files": len(rows), "bytes": total}


def key_fingerprint(seed_hex):
    return "sha256:" + hashlib.sha256(seed_hex.encode("utf-8")).hexdigest()


def axes_of(report):
    by_id = {c["id"]: c["result"] for c in report.get("checks", [])}
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
            if fn.lower().endswith((".ots", ".tsr")) or "nostr" in fn.lower():
                found.append(os.path.relpath(os.path.join(dirpath, fn), package))
    return sorted(found)


def build_bundle(report, package, seed_hex=None, expect_head=None, state_supplied=False):
    return {
        "v": "uibc-verify-bundle/1",
        "artifact": artifact_digest(package),
        "verifier": {"id": report.get("verifier_id"), "version": report.get("verifier_version"),
                     "spec_id": report.get("spec_id")},
        "inputs": {"key_fingerprint": key_fingerprint(seed_hex) if seed_hex else None,
                   "key_supplied": bool(seed_hex), "expect_head": expect_head,
                   "state_supplied": bool(state_supplied), "strict": False},
        "result": {"verdict": report.get("result"), "trust_level": report.get("trust_level"),
                   "axes": axes_of(report),
                   "first_fail": next((c["id"] for c in report.get("checks", [])
                                       if c["result"] == "FAIL"), None),
                   "checks": {c["id"]: c["result"] for c in report.get("checks", [])}},
        "anchors_present": anchors_of(package),
        "note": "carries claims and inputs, not secrets; the owner key stays out of band",
    }


def trust_ladder(report, seed_hex=None, trustlist_path=None):
    """well-formed / valid / trusted, after C2PA's three levels.

    Trust is an input of the reader, not a property of the bytes: the same package
    can be trusted for one reader and not for another. A key on the list never
    makes an invalid package trusted.
    """
    by_id = {c["id"]: c["result"] for c in report.get("checks", [])}
    well_formed = not any(by_id.get(i) == "FAIL" for i in AXES["structure"])
    valid = report.get("result") == "PASS"
    listed = False
    if trustlist_path and seed_hex:
        with open(trustlist_path, encoding="utf-8") as f:
            listed = key_fingerprint(seed_hex) in (json.load(f).get("keys") or [])
    trusted = bool(well_formed and valid and listed)
    level = "trusted" if trusted else ("valid" if (well_formed and valid) else
                                      ("well-formed" if well_formed else "not well-formed"))
    return {"level": level, "well_formed": well_formed, "valid": valid, "trusted": trusted,
            "key_on_list": listed,
            "key_fingerprint": key_fingerprint(seed_hex) if seed_hex else None}
