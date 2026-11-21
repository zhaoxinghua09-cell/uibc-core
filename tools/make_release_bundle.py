"""Publish a package so that someone who trusts nothing but a URL can check it.

The forgery experiment ended on a sentence nobody likes: in open mode a package
re-signed by a stranger verifies as PASS, because the only key the verifier sees
came out of the package itself. A signature proved *that key signed these bytes*
and nothing about who owns the key.

This tool closes that by producing the two things a publisher has to hand out
separately from the artifact:

    bundle/            the package (sealed with the publisher's Ed25519 key)
    bundle/anchor.json  public key, key_id, checkpoint head - the values a
                        verifier must obtain from somewhere the package cannot
                        reach

Whoever receives both can then run:

    python3 tools/anchor_check.py bundle

and get one of two answers. The point is that the bundle alone cannot earn the
stronger one.

A fixed seed reproduces the same bundle byte for byte, so the demo is checkable
rather than merely described. Pass --seed-hex to use your own; never publish a
bundle made from the demo seed.

Usage:
    python3 tools/make_release_bundle.py --out /tmp/bundle [--seed-hex HEX]
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import shutil
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASE = os.path.join(REPO, "fixtures", "clean.uibc")
sys.path.insert(0, REPO)

sys.path.insert(0, HERE)

from anchor_check import anchor_digest  # noqa: E402
from uibc_core.canonical import checkpoint_head, evidence_root  # noqa: E402
from uibc_core.canonical import index_metadata_digest, lifecycle_head  # noqa: E402
from uibc_core.signing import (ALGORITHM_ED25519, ed_generate_seed,  # noqa: E402
                               ed_key_id, ed_public_key, ed_seal_sign)

# A demo seed, published on purpose: the bundle it makes is reproducible and
# carries no authority. Anything meant to be believed must be signed with a seed
# kept off this repository.
DEMO_SEED = bytes.fromhex(
    "5e" * 32)


def _jload(path):
    return json.load(open(path, encoding="utf-8"))


def _jdump(path, doc):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def head_of(pkg):
    """The checkpoint head: the one value that commits to the whole package state."""
    index = _jload(os.path.join(pkg, "evidence", "index.json"))
    lc = _jload(os.path.join(pkg, "lifecycle.json"))
    hashes = [hashlib.sha256(open(os.path.join(pkg, "evidence", e["path"]), "rb").read())
              .hexdigest() for e in index["entries"]]
    return checkpoint_head(lifecycle_head(lc["events"]), evidence_root(hashes),
                           index_metadata_digest(index), len(index["entries"]))


def build(out_dir, seed, tsa_token=None, tsa_cabundle=None, prev_anchor=None):
    pkg = os.path.join(out_dir, "package")
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir)
    shutil.copytree(BASE, pkg)

    identity = _jload(os.path.join(pkg, "identity.json"))
    manifest = _jload(os.path.join(pkg, "manifest.json"))
    lifecycle = _jload(os.path.join(pkg, "lifecycle.json"))

    # The head goes into the manifest BEFORE signing: a signed manifest that is
    # edited afterwards is exactly the forgery row-B repairs and row-A fails on.
    head = head_of(pkg)
    manifest["checkpoint_head"] = head
    _jdump(os.path.join(pkg, "manifest.json"), manifest)

    sig, pub_b64 = ed_seal_sign(seed, identity, manifest, lifecycle)
    pub = ed_public_key(seed)
    _jdump(os.path.join(pkg, "signatures", "seal.json"),
           {"schema": "uibc-core/0.2.0-proposal",
            "algorithm": ALGORITHM_ED25519,
            "key_id": ed_key_id(pub),
            "public_key": pub_b64,
            "signed": "identity+manifest+lifecycle",
            "signature": sig,
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})

    anchor = {
        "schema": "uibc-anchor/0.1",
        "agent_id": manifest.get("agent_id"),
        "key_id": ed_key_id(pub),
        # The two values that must travel outside the package. Publishing them
        # is the whole job; a bundle carrying its own anchor proves nothing.
        "pubkey_b64": pub_b64,
        "checkpoint_head": head,
        "evidence_count": manifest.get("evidence_count"),
        "published_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        # Fill after stamping anchor_digest (printed below) with a public TSA;
        # an anchor without one pins a key and a head but not a moment.
        "tsa": None,
        # The position in the line, and the digest of whatever came before.
        # A seq with no predecessor is a first anchor; a seq that reuses one
        # is a replay. See docs/ANCHOR-CHAIN.md.
        "seq": (prev_anchor.get("seq", 0) + 1) if prev_anchor else 1,
        "prev_anchor_digest": (anchor_digest(prev_anchor) if prev_anchor else None),
        "note": ("Publish this file somewhere the package cannot reach: a release "
                 "asset, a DNS TXT record, a transparency log. A verifier that "
                 "reads it out of the bundle is back to trusting the bundle."),
    }
    if tsa_token and tsa_cabundle:
        anchor["tsa"] = {
            "authority": "RFC 3161 (see gen_time)",
            "covers": "anchor_digest",
            "token_b64": base64.b64encode(open(tsa_token, "rb").read()).decode("ascii"),
            "cabundle_b64": base64.b64encode(open(tsa_cabundle, "rb").read()).decode("ascii"),
        }
    _jdump(os.path.join(out_dir, "anchor.json"), anchor)
    return out_dir, anchor


def main():
    args = sys.argv[1:]
    out = "/tmp/uibc-anchor-bundle"
    seed = DEMO_SEED
    if "--out" in args:
        out = args[args.index("--out") + 1]
    prev_path = args[args.index("--prev-anchor") + 1] if "--prev-anchor" in args else None
    prev_anchor = json.load(open(prev_path, encoding="utf-8")) if prev_path else None
    tsa_token = args[args.index("--tsa-token") + 1] if "--tsa-token" in args else None
    tsa_cabundle = args[args.index("--tsa-cabundle") + 1] if "--tsa-cabundle" in args else None
    if "--seed-hex" in args:
        seed = bytes.fromhex(args[args.index("--seed-hex") + 1])
        if len(seed) != 32:
            raise SystemExit("--seed-hex must be 32 bytes (64 hex characters)")
    out, anchor = build(out, seed, tsa_token=tsa_token, tsa_cabundle=tsa_cabundle,
                         prev_anchor=prev_anchor)
    print("bundle   %s/package" % out)
    print("anchor   %s/anchor.json" % out)
    print("key_id   %s" % anchor["key_id"])
    print("head     %s" % anchor["checkpoint_head"])
    print("seq            %d%s" % (anchor["seq"], "" if anchor["prev_anchor_digest"] is None
                                     else "  (follows %s...)" % anchor["prev_anchor_digest"][:16]))
    print("anchor_digest  %s" % anchor_digest(anchor))
    if anchor.get("tsa"):
        print("timestamp      embedded (RFC 3161, covers anchor_digest)")
    else:
        print("timestamp      none - stamp anchor_digest with a public TSA, then")
        print("               pass --tsa-token/--tsa-cabundle to attach it")
    print("")
    print("hand the anchor out over a channel the package cannot reach, then:")
    print("  python3 tools/anchor_check.py %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
