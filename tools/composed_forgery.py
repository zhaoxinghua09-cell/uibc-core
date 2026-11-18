"""A forgery that agrees with itself: what is left to catch it?

Sixteen checks are measured. Nineteen artefacts make each one fail. Every pair
and every triple of fourteen mutations cancels nowhere. None of that answers the
question an attacker actually asks: *can I rewrite the evidence and repair every
internal consistency the rewrite breaks?*

Repairing is arithmetic. Content hash, evidence root, index digest and checkpoint
head are all public functions of bytes the attacker owns. So the interesting
question is not whether the package can be made self-consistent - it can - but
**which check still has something to say after it is**.

Five attacks, run here:

  A  rewrite one evidence file, leave every declaration alone
  B  rewrite it and repair hash, root, index digest, checkpoint head
  C  B, plus re-sign with a freshly generated key of the attacker's own
  D  C, but the verifier pins the publisher's public key (--pubkey)
  E  C, but the verifier pins a checkpoint head published elsewhere (--expect-head)

The answer printed at the end is the point of the exercise, and it is deliberately
not flattering: with no pin, C passes. A package can be entirely rewritten by
someone who never had the publisher's key, and the verifier's own verdict says
PASS. What stops it is not a check inside the package - it is a value that came
from somewhere else.

Usage:  python3 tools/composed_forgery.py [--json]
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASE = os.path.join(REPO, "fixtures", "clean.uibc")
sys.path.insert(0, REPO)

from uibc_core.canonical import checkpoint_head, evidence_root  # noqa: E402
from uibc_core.canonical import index_metadata_digest, lifecycle_head  # noqa: E402
from uibc_core.signing import (ALGORITHM_ED25519, ed_generate_seed,  # noqa: E402
                               ed_key_id, ed_public_key, ed_seal_sign)
from uibc_core.verify import verify  # noqa: E402

VICTIM = "files/action-log.txt"
NEW_BYTES = b"the agent did something else entirely\n"


def _jload(path):
    return json.load(open(path, encoding="utf-8"))


def _jdump(path, doc):
    json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _rewrite_and_repair(pkg):
    """Replace one evidence file and repair every declaration that depends on it."""
    victim = os.path.join(pkg, "evidence", VICTIM)
    open(victim, "wb").write(NEW_BYTES)
    index_path = os.path.join(pkg, "evidence", "index.json")
    index = _jload(index_path)
    for e in index["entries"]:
        if e["path"] == VICTIM:
            e["content_hash"] = _sha(NEW_BYTES)
    _jdump(index_path, index)

    manifest_path = os.path.join(pkg, "manifest.json")
    manifest = _jload(manifest_path)
    hashes = [_sha(open(os.path.join(pkg, "evidence", e["path"]), "rb").read())
              for e in index["entries"]]
    manifest["evidence_root"] = evidence_root(hashes)
    if manifest.get("checkpoint_head"):
        lc = _jload(os.path.join(pkg, "lifecycle.json"))
        manifest["checkpoint_head"] = checkpoint_head(
            lifecycle_head(lc["events"]), manifest["evidence_root"],
            index_metadata_digest(index), len(index["entries"]))
    _jdump(manifest_path, manifest)
    return manifest


def _resign(pkg, seed):
    """Sign the whole package with a key the attacker owns."""
    identity = _jload(os.path.join(pkg, "identity.json"))
    manifest = _jload(os.path.join(pkg, "manifest.json"))
    lifecycle = _jload(os.path.join(pkg, "lifecycle.json"))
    pub = ed_public_key(seed)
    sig, pub_b64 = ed_seal_sign(seed, identity, manifest, lifecycle)
    seal_path = os.path.join(pkg, "signatures", "seal.json")
    _jdump(seal_path, {"schema": "uibc-core/0.2.0-proposal",
                       "algorithm": ALGORITHM_ED25519,
                       "key_id": ed_key_id(pub),
                       "public_key": pub_b64,
                       "signed": "identity+manifest+lifecycle",
                       "signature": sig,
                       "created_at": "forgery"})
    return pub


def _run(attack):
    """Build the attacked package, verify it, return (verdict, fails, detail)."""
    tmp = tempfile.mkdtemp()
    pkg = os.path.join(tmp, "pkg")
    try:
        shutil.copytree(BASE, pkg)
        kwargs = {}
        if attack == "A":
            open(os.path.join(pkg, "evidence", VICTIM), "wb").write(NEW_BYTES)
            publisher_pub = None
        elif attack == "B":
            _rewrite_and_repair(pkg)
            publisher_pub = None
        elif attack == "C":
            _rewrite_and_repair(pkg)
            _resign(pkg, ed_generate_seed())
            publisher_pub = None
        elif attack == "D":
            # the publisher signs its own package; the attacker re-signs with a
            # key of their own; the verifier pins the publisher
            _rewrite_and_repair(pkg)
            _resign(pkg, ed_generate_seed())
            publisher_pub = ed_public_key(ed_generate_seed())
            kwargs["pubkey"] = publisher_pub
        elif attack == "F":
            # the attacker does not re-sign and does not keep the old seal: just
            # drop it. A package cannot improve its standing by losing a signature.
            _rewrite_and_repair(pkg)
            os.remove(os.path.join(pkg, "signatures", "seal.json"))
        elif attack == "E":
            _rewrite_and_repair(pkg)
            _resign(pkg, ed_generate_seed())
            kwargs["expect_head"] = "sha256:" + "0" * 64
        else:
            raise ValueError(attack)
        v = verify(pkg, **kwargs)
        fails = sorted(c["id"] for c in v["checks"] if c["result"] == "FAIL")
        inc = sorted(c["id"] for c in v["checks"] if c["result"] == "INCONCLUSIVE")
        return v["result"], fails, inc, v["trust_level"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


ATTACKS = [
    ("A", "rewrite one evidence file, touch no declaration"),
    ("B", "rewrite it and repair hash, root, index digest, checkpoint head"),
    ("C", "B, then re-sign with the attacker's own fresh key"),
    ("D", "C, and the verifier pins the publisher's public key"),
    ("E", "C, and the verifier pins a checkpoint head published elsewhere"),
    ("F", "B, and the attacker simply deletes the seal"),
]


def probe():
    rows = []
    for key, what in ATTACKS:
        verdict, fails, inc, trust = _run(key)
        rows.append({"attack": key, "what": what, "verdict": verdict,
                     "fails": fails, "inconclusive": inc, "trust_level": trust})
    return rows


def main():
    rows = probe()
    if "--json" in sys.argv:
        json.dump(rows, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0
    w = print
    w("%-3s %-56s %-13s %-12s %s" % ("#", "attack", "verdict", "trust", "FAIL / INCONCLUSIVE"))
    for r in rows:
        w("%-3s %-56s %-13s %-12s %s" % (r["attack"], r["what"][:56], r["verdict"],
                                        r["trust_level"],
                                        ",".join(r["fails"]) + (" | inc " + ",".join(r["inconclusive"])
                                                                if r["inconclusive"] else "")))
    w("")
    by = {r["attack"]: r for r in rows}
    w("A fails on %s: the rewrite contradicts a declaration it did not touch."
      % (",".join(by["A"]["fails"]) or "nothing"))
    w("B verdict %s: repairing is arithmetic, and a self-consistent forgery is"
      % by["B"]["verdict"])
    w("  indistinguishable from the original by any check that reads the package alone.")
    w("C verdict %s: the attacker had no publisher key, only their own."
      % by["C"]["verdict"])
    w("  This is the honest boundary - in open mode PASS means 'this key signed these")
    w("  bytes', not 'the publisher wrote this'.")
    w("D fails on %s: pinning the publisher's key is what turns that sentence around."
      % (",".join(by["D"]["fails"]) or "nothing"))
    w("E fails on %s: a head published elsewhere catches the same substitution."
      % (",".join(by["E"]["fails"]) or "nothing"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
