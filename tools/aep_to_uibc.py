"""Turn an EATF .aep package into a UIBC package directory, so the two
verifiers can be pointed at the same *evidence*, not only at the same claim.

This is a mapping, not a compatibility layer, and the difference matters:

  * what transfers: the payload bytes and their recorded SHA-256 become a UIBC
    evidence file and its content hash, so a mangled payload is a mangled
    evidence file on both sides;
  * what does not transfer: signatures, RFC 3161 tokens and OVERT receipts.
    EATF signs a canonical byte string with RSA or ML-DSA; a UIBC seal signs
    identity+manifest+lifecycle with a symmetric or Ed25519 key. Re-signing
    during a conversion would destroy exactly the fault a bad-signature vector
    exists to carry. Those classes are therefore declined, not "failed".

Usage:
    python tools/aep_to_uibc.py <package.aep> <out-dir> [--fault NAME]
    python tools/aep_to_uibc.py --measure <test-vectors-dir> <work-dir>
"""

import json
import os
import shutil
import sys
import zipfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

import uibc_core.cli as ucli  # noqa: E402
from uibc_core.signing import generate_key  # noqa: E402

def NS(**kw):
    from types import SimpleNamespace
    return SimpleNamespace(**kw)

# Fault classes that survive a change of container: the fault is in the
# payload, or in the payload's recorded hash, and both containers carry those.
TRANSFERABLE = {
    "tampered-canonical-bin": "payload bytes changed after the hash was recorded",
    "missing-canonical-bin": "payload file absent while the index still lists it",
    "tampered-metadata": "metadata bytes changed after the hash was recorded",
}

# Fault classes that cannot be carried across without re-implementing the other
# project's crypto or its envelope formats.
NOT_TRANSFERABLE = {
    "bad-signature-classical": "signature is over EATF's canonical string; a UIBC seal signs a different tuple",
    "bad-signature-pqc": "ML-DSA-65 hybrid signature has no UIBC counterpart to carry",
    "untrusted-issuer": "the fault is in key trust; a converted package is signed by us, so nothing is untrusted",
    "bad-timestamp": "the token is DER bytes; UIBC's anchor slot expects a JSON envelope",
    "tampered-overt-receipt": "the receipt is an OVERT object; UIBC's receipt slot expects its own schema",
}


def _read(aep_path):
    with zipfile.ZipFile(aep_path) as z:
        meta = json.loads(z.read("metadata.json").decode("utf-8"))
        names = z.namelist()
        payload = z.read("canonical.bin") if "canonical.bin" in names else b""
        try:
            recorded = z.read("hash.sha256").decode("utf-8").strip()
        except KeyError:
            recorded = ""
    return meta, payload, recorded


def convert(aep_path, out_dir, fault=None):
    """Build a UIBC package carrying this .aep's payload; return (pkg, key_hex)."""
    if os.path.isdir(out_dir):
        try:
            shutil.rmtree(out_dir)
        except OSError:
            import time
            time.sleep(0.5)
            shutil.rmtree(out_dir, ignore_errors=True)
    meta, payload, recorded = _read(aep_path)

    agent_id = str(meta.get("agent_id") or "eatf-agent").replace(":", ".")[:120]

    ucli.cmd_init(NS(path=out_dir))
    ucli.cmd_register(NS(path=out_dir, agent_id=agent_id, owner="eatf",
                         agent_type="software-agent", version="1"))

    tmp = os.path.join(os.path.dirname(out_dir), os.path.basename(out_dir) + "-src")
    os.makedirs(tmp, exist_ok=True)
    p1 = os.path.join(tmp, "canonical.bin")
    with open(p1, "wb") as f:
        f.write(payload)
    ucli.cmd_evidence(NS(path=out_dir, type="ACTION", file=p1,
                         media_type="application/octet-stream",
                         note=str(meta.get("attestation_id") or "")))

    p2 = os.path.join(tmp, "metadata.json")
    with open(p2, "w", encoding="utf-8") as f:
        json.dump(meta, f, sort_keys=True)
    ucli.cmd_evidence(NS(path=out_dir, type="ACTION", file=p2,
                         media_type="application/json",
                         note="eatf metadata as recorded by the other side"))

    key = generate_key()
    kf = os.path.join(tmp, "seal.key")
    with open(kf, "w", encoding="ascii") as f:
        f.write(key.hex())
    ucli.cmd_submit(NS(path=out_dir, key=kf))

    if fault == "tampered-canonical-bin":
        with open(os.path.join(out_dir, "evidence", "files",
                               os.listdir(os.path.join(out_dir, "evidence", "files"))[0]),
                  "ab") as f:
            f.write(b"\nTAMPERED\n")
    elif fault == "missing-canonical-bin":
        target = os.path.join(out_dir, "evidence", "files",
                              os.listdir(os.path.join(out_dir, "evidence", "files"))[0])
        os.remove(target)
    elif fault == "tampered-metadata":
        # the metadata file is one of the two evidence files; find the JSON one
        for name in os.listdir(os.path.join(out_dir, "evidence", "files")):
            p = os.path.join(out_dir, "evidence", "files", name)
            try:
                json.load(open(p, encoding="utf-8"))
            except Exception:
                continue
            with open(p, "a", encoding="utf-8") as f:
                f.write(" ")
            break
    return out_dir, key.hex()


def measure(vectors_dir, work_dir):
    """Run both verifiers over every vector that converts, and print a table."""
    from independent_verifier.iverify import independent_verify
    from uibc_core.verify import verify as ref_verify
    os.makedirs(work_dir, exist_ok=True)
    rows = []
    for kind in ("valid", "invalid"):
        base = os.path.join(vectors_dir, kind)
        for name in sorted(os.listdir(base)):
            d = os.path.join(base, name)
            if not os.path.isdir(d):
                continue
            aep = os.path.join(d, "package.aep")
            if not os.path.isfile(aep):
                continue
            fault = name if name in TRANSFERABLE else None
            if kind == "invalid" and fault is None:
                rows.append((name, "declined", "", ""))
                continue
            pkg, hexkey = convert(aep, os.path.join(work_dir, name), fault)
            key = bytes.fromhex(hexkey)
            ref = ref_verify(pkg, key=key)
            ind = independent_verify(pkg, key=key)
            ref_r = ref.get("result") if isinstance(ref, dict) else ("PASS" if ref else "FAIL")
            rows.append((name, ref_r, ind["result"], ind.get("unjudged")))
    return rows


def main(argv):
    if "--measure" in argv:
        i = argv.index("--measure")
        vectors, work = argv[i + 1], argv[i + 2]
        rows = measure(vectors, work)
        print("%-28s %-12s %-12s %s" % ("vector", "reference", "independent", "note"))
        for name, ref, ind, note in rows:
            print("%-28s %-12s %-12s %s" % (name, ref, ind, (note or [])[:1]))
        return 0
    aep, out = argv[1], argv[2]
    fault = None
    if "--fault" in argv:
        fault = argv[argv.index("--fault") + 1]
    pkg, key = convert(aep, out, fault)
    print(json.dumps({"package": pkg, "key_hex": key, "fault": fault}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
