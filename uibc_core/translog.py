"""An append-only log we operate ourselves, with checkpoints and witness cosignatures.

Why this exists (2026-11-24): every transparency claim this repository makes is
somebody else's log. We append into Rekor (`tools/anchor_rekor.py`), we timestamp
with OpenTSA and FreeTSA, we cite Zenodo and Software Heritage. All of those prove
"a third party saw this". None of them proves **we operate a log of our own** whose
history a stranger can walk, and none of them gives us a place to publish a head
that gossip can compare. That is the gap a competitor with an actual log
(Rekor/Trillian) closes trivially and we did not close at all.

What it is:
  * leaves are SHA-256 of a canonical record; the tree is RFC 6962 (`uibc_core.merkle`)
  * an append is one leaf; the log is the list of leaf digests, in order
  * a **checkpoint** commits (tree_size, root) and is signed by the log operator
  * a **cosignature** is a witness signing the checkpoint hash under a separate
    domain string - a witness signing the same bytes as the operator would be
    signing whatever the operator signs, which is not witnessing
  * inclusion and consistency proofs come from `uibc_core.merkle`

What it deliberately does not do:
  * no network, no server, no database. A log is a list; publishing it is a git
    commit or a file drop. Anything more would be infrastructure we cannot keep up.
  * a cosignature here proves **a key signed a head**, not that the holder is
    independent of us. Independence is a statement about people, and this file
    cannot make it. `docs/TRANSPARENCY_LOG.md` says which cosignatures exist and
    whose keys they are, and says plainly when there are none.
"""
from __future__ import annotations

import base64
import json as _json
import time
from typing import Iterable, Sequence

from . import canonical, ed25519, merkle

FORMAT = "uibc-translog-v1"
CHECKPOINT_DOMAIN = b"uibc-translog-checkpoint-v1\x00"
WITNESS_DOMAIN = b"uibc-translog-witness-v1\x00"


# --------------------------------------------------------------------------- leaves

def record_digest(record: dict) -> str:
    """The leaf value: SHA-256 of the canonical form of the record.

    The record is whatever the caller wants logged; this function does not
    interpret it beyond canonicalising it. Interpretation belongs to whoever
    writes the checkpoint note.
    """
    return canonical.sha256_hex(canonical.canonicalize(record))


def new_log() -> dict:
    return {"format": FORMAT, "entries": []}


def append(log: dict, record: dict) -> tuple:
    """Append one record. Returns (log, index). The log is mutated and returned
    so callers cannot accidentally keep using a stale head."""
    if log.get("format") != FORMAT:
        raise ValueError("not a %s log: %r" % (FORMAT, log.get("format")))
    h = record_digest(record)
    log["entries"].append(h)
    return log, len(log["entries"]) - 1


def _leaves(log: dict) -> list:
    return [merkle.leaf_hash(bytes.fromhex(h)) for h in log["entries"]]


def tree_size(log: dict) -> int:
    return len(log["entries"])


def root_hex(log: dict) -> str:
    if not log["entries"]:
        return merkle.root_hash([]).hex()
    return merkle.root_hash(_leaves(log)).hex()


# ----------------------------------------------------------------------- checkpoints

def checkpoint(log: dict, seed: bytes = None, note: str = "") -> dict:
    """Commit the current (size, root). Signed when a seed is given.

    Signing is optional on purpose: an unsigned checkpoint is still useful for
    comparing heads between two copies of the same log (gossip), and forcing a
    signature would tempt callers to log a key they do not control.
    """
    cp = {
        "format": FORMAT,
        "tree_size": tree_size(log),
        "root": root_hex(log),
        "created_at": int(time.time()),
    }
    if note:
        cp["note"] = note
    if seed is not None:
        cp["key"] = ed25519_key_id(seed)
        cp["sig"] = base64.b64encode(_sign_checkpoint(seed, cp)).decode("ascii")
    return cp


def ed25519_key_id(seed: bytes) -> str:
    pub = ed25519.publickey(seed)
    return "ed25519:" + base64.b16encode(pub).decode("ascii").lower()


def _cp_bytes(cp: dict) -> bytes:
    """The signed bytes: domain string + canonical checkpoint with no signature field."""
    body = {k: v for k, v in cp.items() if k not in ("sig",)}
    return CHECKPOINT_DOMAIN + canonical.canonicalize(body)


def _sign_checkpoint(seed: bytes, cp: dict) -> bytes:
    return ed25519.sign(seed, _cp_bytes(cp))


def verify_checkpoint(cp: dict, public_key: bytes) -> bool:
    """Does this checkpoint carry a valid operator signature under public_key?"""
    sig = cp.get("sig")
    if not sig:
        return False
    try:
        raw = base64.b64decode(sig, validate=True)
    except Exception:
        return False
    return ed25519.verify(public_key, _cp_bytes(cp), raw)


def checkpoint_hash(cp: dict) -> str:
    """A stable name for a head, so gossip can compare heads without shipping them."""
    return canonical.sha256_hex(canonical.canonicalize(
        {"format": cp["format"], "tree_size": cp["tree_size"], "root": cp["root"]}))


# -------------------------------------------------------------------------- witnesses

def cosign(cp: dict, witness_seed: bytes) -> dict:
    """A witness signs the checkpoint **hash** under its own domain string.

    Separate domain matters: if the witness signed the same bytes the operator
    signs, a compromised operator key could produce a "cosigned" checkpoint by
    itself, and the cosignature would prove nothing.
    """
    msg = WITNESS_DOMAIN + bytes.fromhex(checkpoint_hash(cp))
    return {
        "witness": ed25519_key_id(witness_seed),
        "sig": base64.b64encode(ed25519.sign(witness_seed, msg)).decode("ascii"),
        "tree_size": cp["tree_size"],
        "root": cp["root"],
    }


def verify_cosignature(cp: dict, cosig: dict, witness_public_key: bytes) -> bool:
    if cosig.get("tree_size") != cp["tree_size"] or cosig.get("root") != cp["root"]:
        return False          # a cosignature for a different head is not a cosignature
    try:
        raw = base64.b64decode(cosig.get("sig"), validate=True)
    except Exception:
        return False
    msg = WITNESS_DOMAIN + bytes.fromhex(checkpoint_hash(cp))
    return ed25519.verify(witness_public_key, msg, raw)


def witness_summary(cp: dict, cosigs: Sequence[dict], witness_keys: Iterable[bytes]) -> dict:
    """How much independent signing this head actually carries — counted, not assumed."""
    ok, bad = [], []
    for cosig, pub in zip(cosigs, witness_keys):
        (ok if verify_cosignature(cp, cosig, pub) else bad).append(cosig.get("witness"))
    return {"valid": len(ok), "invalid": len(bad), "witnesses": ok}


# ------------------------------------------------------------------------------ proofs

def inclusion_proof(log: dict, index: int) -> list:
    return [bytes.fromhex(h) for h in merkle.build_proof(_leaves(log), index)]


def verify_inclusion(log: dict, index: int, proof: Sequence[bytes]) -> bool:
    leaves = _leaves(log)
    if not 0 <= index < len(leaves):
        return False
    return merkle.verify_inclusion(leaves[index], index, len(leaves), list(proof),
                                   merkle.root_hash(leaves))


def consistency_proof(old: dict, new: dict) -> list:
    if tree_size(old) > tree_size(new):
        raise ValueError("old log is longer than new log; that is not a consistency proof")
    return [bytes.fromhex(h) for h in merkle.build_consistency_proof(_leaves(new), tree_size(old))]


def verify_consistency(old: dict, new_cp: dict, proof: Sequence[bytes]) -> bool:
    if tree_size(old) == 0:
        return True
    return merkle.verify_consistency(
        root_hash_bytes(old), tree_size(old),
        bytes.fromhex(new_cp["root"]), new_cp["tree_size"], list(proof))


def root_hash_bytes(log: dict) -> bytes:
    return bytes.fromhex(root_hex(log))


# ------------------------------------------------------------------------------ journal

def to_jsonl(log: dict, note: str = "") -> str:
    """One entry per line, so a log published as a file is diffable and appendable."""
    lines = []
    for i, h in enumerate(log["entries"]):
        lines.append(canonical.canonicalize({"index": i, "digest": h}).decode("utf-8"))
    return "\n".join(lines) + ("\n" if lines else "")


def from_jsonl(text: str) -> dict:
    log = new_log()
    for n, line in enumerate(text.splitlines()):
        line = line.strip()
        if not line:
            continue
        rec = _json.loads(line)
        if rec.get("index") != n:
            raise ValueError("journal is not contiguous at line %d (index=%r)" % (n + 1, rec.get("index")))
        log["entries"].append(rec["digest"])
    return log
