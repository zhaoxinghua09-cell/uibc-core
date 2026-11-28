"""Build conformance/profile2/ -- the bytes behind the `uibc-scitt/2` claims.

Three of the cases are positive: `OK` on a one-leaf tree, and `OK` on the middle
and last leaf of a three-leaf tree. If `OK` were unreachable the vectors would be
just another negative suite, so the generator refuses to write anything when the
positive cases do not come out `OK`.

The three-file package is generated here from fixed bytes, never copied from a
hand-made directory, so rebuilding reproduces the same root and receipts.

    python tools/build_profile2_vectors.py [--check]
"""

import argparse
import hashlib
import io
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import canonical, cose_min, ed25519, merkle, profile, profile2  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = os.path.join(ROOT, "examples", "demo.uibc")
OUT = os.path.join(ROOT, "conformance", "profile2")
SEED = b"\x11" * 32
FOREIGN = b"\x22" * 32

THREE = {
    "evidence/files/plan.md": b"plan: one step\n",
    "evidence/files/result.txt": b"result: verified\n",
    "evidence/files/note.txt": b"note: reviewed\n",
}


def build_three_files() -> str:
    """A deterministic three-evidence package, written by this script."""
    dst = os.path.join(OUT, "packages", "three-files")
    if os.path.isdir(dst):
        shutil.rmtree(dst)
    os.makedirs(os.path.join(dst, "evidence", "files"))
    entries = []
    for i, (rel, content) in enumerate(sorted(THREE.items())):
        full = os.path.join(dst, rel)
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with io.open(full, "wb") as fh:
            fh.write(content)
        entries.append({
            "evidence_id": "3f%02d-0000-4000-8000-000000000000" % (i + 1),
            "type": "ACTION",
            "path": rel.split("/", 1)[1],
            "content_hash": hashlib.sha256(content).hexdigest(),
            "created_at": "2026-11-29T00:00:0%d Z".replace(" Z", "Z") % i,
            "media_type": "text/plain",
        })
    hashes = [e["content_hash"] for e in entries]
    idx = {"entries": entries}
    with io.open(os.path.join(dst, "evidence", "index.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(idx, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    man = {
        "schema": "uibc-core/0.1.0-proposal",
        "agent_id": "three-file-agent",
        "agent_version": "0.1.0",
        "created_at": "2026-11-29T00:00:00Z",
        "evidence_count": len(entries),
        "evidence_root": merkle.root_hash(
            [merkle.leaf_hash(bytes.fromhex(h)) for h in sorted(hashes)]).hex(),
        "status": "SUBMITTED",
    }
    with io.open(os.path.join(dst, "manifest.json"), "w",
                 encoding="utf-8", newline="\n") as fh:
        json.dump(man, fh, ensure_ascii=False, indent=1)
        fh.write("\n")
    return dst


def build() -> dict:
    os.makedirs(os.path.join(OUT, "cases"), exist_ok=True)
    three = build_three_files()

    demo_hash = profile.package_facts(BASE)
    demo = profile2.package_facts(BASE)
    tri = profile2.package_facts(three)
    for name, facts in (("demo", demo), ("three-files", tri)):
        if facts[4]:
            raise SystemExit("%s does not verify: %r" % (name, facts[4]))

    demo_val = profile2.registered_value(demo[0], demo[1], demo[2])
    tri_val = profile2.registered_value(tri[0], tri[1], tri[2])
    pub = ed25519.publickey(SEED).hex()

    d_hashes, t_hashes = demo[3], tri[3]
    d_sorted = sorted(d_hashes)
    t_sorted = sorted(t_hashes)
    vdp_demo = profile2.vdp_for_hash(d_hashes, d_sorted[0])
    vdp_t0 = profile2.vdp_for_hash(t_hashes, t_sorted[0])
    vdp_t1 = profile2.vdp_for_hash(t_hashes, t_sorted[1])
    vdp_t2 = profile2.vdp_for_hash(t_hashes, t_sorted[2])

    # a path taken from one leaf and labelled with another index
    leaf1, _i, _s, path1, _why = profile2.read_vdp(vdp_t1)
    wrong_index = cose_min.encode([leaf1, 2, 3, path1])
    # a genuine leaf that is not in this tree
    wrong_leaf = cose_min.encode([merkle.leaf_hash(b"\x00" * 32), 1, 3, path1])
    too_big = cose_min.encode([leaf1, 1, 4, path1])
    five_elems = cose_min.encode([leaf1, 1, 3, path1, b"extra"])

    changed = os.path.join(OUT, "packages", "changed-byte")
    if os.path.isdir(changed):
        shutil.rmtree(changed)
    shutil.copytree(BASE, changed)
    with io.open(os.path.join(changed, "evidence", "files", "action-log.txt"), "a") as fh:
        fh.write("x")

    v1_value = profile.registered_value(demo_hash[0], demo_hash[1], demo_hash[2])

    cases = []

    def add(cid, change, receipt, package, trust=None, size=None, why=""):
        rel = "cases/%s.cose" % cid
        with io.open(os.path.join(OUT, rel), "wb") as fh:
            fh.write(receipt)
        cases.append({"id": cid, "change": change, "receipt": rel, "package": package,
                      "trusted_issuers": trust, "trusted_size": size, "why": why})

    add("ok-one-leaf", "a one-leaf tree whose only leaf the proof names",
        profile2.make_receipt(demo_val, SEED, vdp=vdp_demo), "examples/demo.uibc",
        trust=[pub], why="the first case where the profile can say OK, not partial")
    add("ok-three-first", "the first leaf of a three-leaf tree",
        profile2.make_receipt(tri_val, SEED, vdp=vdp_t0),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("ok-three-middle", "the middle leaf: a non-empty sibling path",
        profile2.make_receipt(tri_val, SEED, vdp=vdp_t1),
        "conformance/profile2/packages/three-files", trust=[pub],
        why="the path has two siblings; a one-leaf case would never exercise it")
    add("ok-three-last", "the last leaf, whose path is built bottom-up around the tail",
        profile2.make_receipt(tri_val, SEED, vdp=vdp_t2),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("partial-unchecked", "a valid proof, with no issuer list supplied",
        profile2.make_receipt(tri_val, SEED, vdp=vdp_t0),
        "conformance/profile2/packages/three-files",
        why="inclusion verified is not issuer verified; the verdict says so separately")
    add("wrong-index", "a genuine sibling path labelled with the wrong index",
        profile2.make_receipt(tri_val, SEED, vdp=wrong_index),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("wrong-leaf", "a well-formed leaf that is not in this tree",
        profile2.make_receipt(tri_val, SEED, vdp=wrong_leaf),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("size-mismatch", "tree_size larger than the registered count",
        profile2.make_receipt(tri_val, SEED, vdp=too_big),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("vdp-five-elements", "a proof array with a fifth element the profile does not define",
        profile2.make_receipt(tri_val, SEED, vdp=five_elems),
        "conformance/profile2/packages/three-files", trust=[pub],
        why="extension points are refused, not guessed")
    add("vdp-not-cbor", "bytes where the proof should be",
        profile2.make_receipt(tri_val, SEED, vdp=b"\x00"),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("no-vdp", "a receipt with no proof label",
        profile2.make_receipt(tri_val, SEED, vdp=None),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("unknown-vds", "a tree this profile does not implement",
        profile2.make_receipt(tri_val, SEED, vdp=vdp_t0, vds=9999),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("other-key", "the same value signed by a key outside the trusted set",
        profile2.make_receipt(tri_val, FOREIGN, vdp=vdp_t0),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("wrong-value", "a receipt issued for a different root",
        profile2.make_receipt(profile2.registered_value("0" * 64, tri[1], tri[2]), SEED,
                              vdp=vdp_t0),
        "conformance/profile2/packages/three-files", trust=[pub])
    add("pkg-changed", "the demo package with one evidence byte appended",
        profile2.make_receipt(demo_val, SEED, vdp=vdp_demo),
        "conformance/profile2/packages/changed-byte", trust=[pub])
    add("v1-receipt", "a valid /1 receipt for the same package, offered to /2",
        profile.make_receipt(v1_value, SEED), "examples/demo.uibc", trust=[pub],
        why="profile ids are not interchangeable: /1 registers a flat root")

    for c in cases:
        res = profile2.verify(os.path.join(ROOT, c["package"]),
                              open(os.path.join(OUT, c["receipt"]), "rb").read(),
                              trusted_issuers=c.get("trusted_issuers"),
                              trusted_size=c.get("trusted_size"))
        c["expected"] = {"verdict": res["verdict"], "issuer": res["issuer"]}

    oks = [c["id"] for c in cases if c["expected"]["verdict"] == "OK"]
    if len(oks) != 4:
        raise SystemExit("expected exactly four OK cases, got %r" % (oks,))

    return {
        "schema": "uibc-profile2-vectors/1",
        "profile": profile2.PROFILE_ID_2,
        "as_of": "2026-11-29",
        "tree": "RFC 6962 MTH over leaves = SHA-256(0x00 || ascending content digest)",
        "vdp": "[leaf_hash bstr32, index uint, tree_size uint, path [bstr32]]",
        "ok_cases": oks,
        "note": "verdicts are recorded, not chosen: rebuild regenerates them from "
                "uibc_core/profile2.py, and tests fail if a recorded verdict and a "
                "fresh replay disagree",
        "cases": cases,
    }


def write(doc) -> None:
    with io.open(os.path.join(OUT, "cases.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    doc = build()
    if a.check:
        on_disk = json.load(io.open(os.path.join(OUT, "cases.json"), encoding="utf-8"))
        if json.dumps(doc, sort_keys=True) != json.dumps(on_disk, sort_keys=True):
            print("conformance/profile2 on disk is stale -- rerun without --check")
            return 1
        print("profile2 vectors match a fresh build (%d cases, %d OK)"
              % (len(doc["cases"]), len(doc["ok_cases"])))
        return 0
    write(doc)
    print("wrote %s (%d cases, %d OK)"
          % (os.path.join(OUT, "cases.json"), len(doc["cases"]), len(doc["ok_cases"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
