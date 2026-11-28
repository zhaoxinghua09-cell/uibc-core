"""Build conformance/profile/ -- the tier's cases as bytes, with expected verdicts.

The tier used to be checkable only by reading the selftest and trusting it. This
writes the cases to disk instead: each case is a receipt file plus a package
directory, and `cases.json` says what the profile must conclude about it. An
outsider can replay them with `tools/run_profile_vectors.py`, or implement the
profile in another language and replay the same bytes (the Node reader does this
in `tools/verify-js/profile.mjs`).

Determinism: receipts are built from fixed seeds, so rebuilding this directory
must reproduce the same bytes. `tests/test_profile_vectors.py` holds that.

    python tools/build_profile_vectors.py [--check]
"""

import argparse
import io
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import profile, cose_min, ed25519  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "conformance", "profile")
BASE = os.path.join(ROOT, "examples", "demo.uibc")
SEED = b"\x11" * 32          # the issuer
FOREIGN = b"\x22" * 32       # a stranger with a key of their own


def _attached(value: bytes, seed: bytes) -> bytes:
    """COSE_Sign1 that carries the registered value in the payload field."""
    pub = ed25519.publickey(seed)
    hdr = {1: cose_min.ALG_EDDSA, 4: pub, profile.LBL_VDS: 1, profile.LBL_VDP: b"\x00"}
    protected = cose_min.encode(hdr)
    body = cose_min._sig_structure(protected, value)
    return cose_min.encode([protected, {}, value, ed25519.sign(seed, body)])


def _package_copy(name: str, mutate) -> str:
    dst = os.path.join(OUT, "packages", name)
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    shutil.copytree(BASE, dst)
    mutate(dst)
    return dst


def build():
    os.makedirs(os.path.join(OUT, "cases"), exist_ok=True)
    root, count, agent, problems = profile.package_facts(BASE)
    if problems:
        raise SystemExit("base package does not verify: %r" % (problems,))
    value = profile.registered_value(root, count, agent)
    other = profile.registered_value("0" * 64, count, agent)
    pub = ed25519.publickey(SEED).hex()

    changed = _package_copy("changed-byte", lambda d: open(
        os.path.join(d, "evidence", "files", "action-log.txt"), "a").write("x"))
    undeclared = _package_copy("undeclared-file", lambda d: open(
        os.path.join(d, "evidence", "files", "extra.txt"), "w").write("x"))

    cases = []

    def add(cid, change, receipt: bytes, package: str, trust=None, size=None, why=""):
        rel = "cases/%s.cose" % cid
        with io.open(os.path.join(OUT, rel), "wb") as fh:
            fh.write(receipt)
        cases.append({
            "id": cid,
            "change": change,
            "receipt": rel,
            "package": package,
            "trusted_issuers": trust,
            "trusted_size": size,
            "why": why,
        })

    add("good", "a well-formed receipt for this package",
        profile.make_receipt(value, SEED), "examples/demo.uibc",
        why="the best this code can say without a vdp encoding: partial, never OK")
    add("good-trusted", "the same receipt, with the issuer key supplied out of band",
        profile.make_receipt(value, SEED), "examples/demo.uibc", trust=[pub],
        why="issuer TRUSTED; the verdict does not move, the issuer field does")
    add("wrong-value", "a receipt issued for different bytes",
        profile.make_receipt(other, SEED), "examples/demo.uibc",
        why="the package does not reproduce the value the receipt covers")
    add("other-key", "the same value, signed by a key outside the trusted set",
        profile.make_receipt(value, FOREIGN), "examples/demo.uibc", trust=[pub],
        why="self-consistent is not authentic: refused as untrusted issuer")
    add("unknown-vds", "a receipt from a tree this profile does not implement",
        profile.make_receipt(value, SEED, vds=9999), "examples/demo.uibc",
        why="refusal, not a finding that the package is false")
    add("no-vdp", "a receipt with no inclusion proof in the header",
        profile.make_receipt(value, SEED, vdp=None), "examples/demo.uibc")
    add("corrupt", "bytes that are not a COSE_Sign1 at all",
        b"\xff\x00not-a-cose", "examples/demo.uibc")
    add("attached-ok", "a receipt that carries the value in its payload field",
        _attached(value, SEED), "examples/demo.uibc")
    add("attached-wrong", "an attached receipt carrying different bytes",
        _attached(other, SEED), "examples/demo.uibc")
    add("pkg-changed", "the package, with one evidence byte appended",
        profile.make_receipt(value, SEED), os.path.relpath(changed, ROOT).replace("\\", "/"),
        why="step 1 recomputes and refuses; the receipt is irrelevant")
    add("pkg-undeclared", "the package, with a file under evidence/ that the index omits",
        profile.make_receipt(value, SEED), os.path.relpath(undeclared, ROOT).replace("\\", "/"))
    add("trusted-size", "a well-formed receipt plus a trusted tree size",
        profile.make_receipt(value, SEED), "examples/demo.uibc", size=count,
        why="step 5 becomes checked instead of skipped")

    # expected verdicts come from the code, not from this file's author
    for c in cases:
        res = profile.verify(os.path.join(ROOT, c["package"]),
                             open(os.path.join(OUT, c["receipt"]), "rb").read(),
                             trusted_size=c.get("trusted_size"),
                             trusted_issuers=c.get("trusted_issuers"))
        c["expected"] = {"verdict": res["verdict"], "issuer": res["issuer"]}

    doc = {
        "profile": profile.PROFILE_ID,
        "package_base_root": root,
        "as_of": "2026-11-28",
        "note": "verdicts are recorded, not chosen: rebuild regenerates them from "
                "uibc_core/profile.py, and the tests fail if a recorded verdict and a "
                "fresh replay disagree",
        "cases": cases,
    }
    return doc


def write(doc) -> None:
    with io.open(os.path.join(OUT, "cases.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="rebuild in memory and compare with what is on disk")
    a = ap.parse_args()
    if a.check:
        doc = build()
        on_disk = json.load(io.open(os.path.join(OUT, "cases.json"), encoding="utf-8"))
        if json.dumps(doc, sort_keys=True) != json.dumps(on_disk, sort_keys=True):
            print("cases.json on disk is stale -- rerun without --check")
            return 1
        print("cases.json matches a fresh build (%d cases)" % len(doc["cases"]))
        return 0
    doc = build()
    write(doc)
    print("wrote %s (%d cases)" % (os.path.join(OUT, "cases.json"), len(doc["cases"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
