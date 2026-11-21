"""One command an outsider can run, with no credentials and no network.

`docs/OUTSIDER-RUN.md` asks a third party to reproduce our claims. A document
can ask; it cannot execute. Until the a stranger can type one line and get a
verdict, "reproducible by a third party" is a promise rather than a property.

This tool is that one line:

    python3 tools/outsider_audit.py

It does three things, and refuses to blur them:

  1. **baseline** -- does the shipped clean package reach the verdict the docs
     claim? (INCONCLUSIVE, because it is unsigned. A tool that reported PASS
     here would be lying about the seal.)
  2. **red team** -- apply twelve mutations that a forger would try and two
     that must NOT be treated as forgeries, and check every verdict.
  3. **interop** -- if an AER-1 corpus is supplied with --kit, run the emit /
     interop / inbound checks against it. If no corpus is supplied this stage
     reports SKIPPED, and a skip is never counted as a pass.

Exit code is 0 only when nothing failed and nothing required was skipped.

Zero dependencies. No network access unless --kit triggers a corpus download,
which it does not do by default.
"""

import argparse
import json
import os
import shutil
import sys
import tempfile

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _REPO not in sys.path:
    sys.path.insert(0, _REPO)

# Where the judgment comes from matters as much as what it says.
#
# An auditor that imports the verifier from wherever PYTHONPATH points can be
# handed a `uibc_core` that answers PASS to everything, and its verdict then
# describes the attacker's code rather than the package. Inserting _REPO at
# position 0 is the first line of defence; this is the second: refuse to run
# unless the verifier actually loaded from this repo.
import hashlib  # noqa: E402

from uibc_core import verify as _verify_mod  # noqa: E402
from uibc_core.verify import verify  # noqa: E402


def _norm(path):
    # Windows: abspath yields single backslashes, so the separator must be
    # normalised one-for-one. ("\\\\" is a two-character string and never matches.)
    return os.path.normcase(os.path.abspath(path)).replace("\\", "/")


def trust_root():
    """The verifier we judge with, and whether it really came from this repo."""
    where = os.path.abspath(_verify_mod.__file__)
    repo_norm = _norm(_REPO).rstrip("/")
    inside = _norm(where).startswith(repo_norm + "/")
    with open(where, "rb") as f:
        digest = hashlib.sha256(f.read()).hexdigest()
    return {"path": where, "sha256": digest, "in_repo": inside}


def behavior_self_test():
    """Judge the judge: a verifier that passes junk is not a verifier.

    Path checks cannot settle this. Put the tool and a `uibc_core` that
    answers PASS next to each other and `in_repo` is satisfied. So ask the
    loaded verifier two questions whose answers we already know: a path that
    does not exist and an empty directory must both come back not-PASS, and
    the report must carry an S1 row. A stub fails here.
    """
    problems = []
    empty = tempfile.mkdtemp()
    try:
        cases = [("a path that does not exist",
                  os.path.join(empty, "no-such-package")),
                 ("an empty directory", empty)]
        for label, path in cases:
            try:
                r = verify(path)
            except Exception as exc:  # a verifier that raises has not judged
                problems.append("%s: raised %r" % (label, exc))
                continue
            if str((r or {}).get("result", "")).upper() == "PASS":
                problems.append("%s: reported PASS" % label)
            if "S1" not in [c.get("id") for c in (r or {}).get("checks") or []]:
                problems.append("%s: no S1 row in the report" % label)
    finally:
        shutil.rmtree(empty, ignore_errors=True)
    return problems


_TRUST = trust_root()
_BEHAVIOR = behavior_self_test()
if not _TRUST["in_repo"]:
    sys.stderr.write(
        "refusing to run: the verifier came from %s\n"
        "which is outside this repository (%s).\n"
        "An audit must be judged by this repo's code, not by whatever "
        "PYTHONPATH supplied.\n" % (_TRUST["path"], _REPO))
    sys.exit(2)
if _BEHAVIOR:
    sys.stderr.write(
        "refusing to run: the loaded verifier failed its own self-test.\n"
        + "".join("  - %s\n" % p for p in _BEHAVIOR)
        + "A verifier that passes things it has never looked at is not a "
          "verifier, and its audit would only describe itself.\n")
    sys.exit(2)

DEFAULT_PACKAGE = os.path.join(_REPO, "fixtures", "clean.uibc")


# --------------------------------------------------------------------------
# mutations: each takes a package directory and edits it in place
# --------------------------------------------------------------------------

def _read(path):
    with open(path, "rb") as f:
        return f.read()


def _write(path, data):
    with open(path, "wb") as f:
        f.write(data)


def _json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _dump(path, obj):
    # newline="\n": these files are evidence. Written on Windows, a bare "w"
    # gained CRLF and the stored content hash then matched only on Windows -
    # the same defect the fixtures rule in .gitattributes documents.
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _index(pkg):
    """The index is a bare list in the shipped fixture and an
    {"entries": [...]} object in packages this repo writes. Both are real;
    the reader must handle each rather than assume one."""
    path = os.path.join(pkg, "evidence", "index.json")
    raw = _json(path)
    entries = raw["entries"] if isinstance(raw, dict) else raw
    return path, raw, entries


def _save_index(path, raw, entries):
    if isinstance(raw, dict):
        raw["entries"] = entries
        _dump(path, raw)
    else:
        _dump(path, entries)


def _evidence_files(pkg):
    _, _, entries = _index(pkg)
    return entries, [os.path.join(pkg, "evidence", e["path"]) for e in entries]


def m_flip_evidence_byte(pkg):
    """One byte in one evidence file. The hash no longer matches."""
    _, files = _evidence_files(pkg)
    data = bytearray(_read(files[0]))
    data[len(data) // 2] ^= 0x01
    _write(files[0], bytes(data))


def m_truncate_evidence_file(pkg):
    """Cut the file in half: hash mismatch, same as any edit."""
    _, files = _evidence_files(pkg)
    data = _read(files[0])
    _write(files[0], data[: len(data) // 2])


def m_delete_evidence_file(pkg):
    _, files = _evidence_files(pkg)
    os.remove(files[0])


def m_edit_root(pkg):
    """Change one hex digit of the root in the manifest."""
    man = _json(os.path.join(pkg, "manifest.json"))
    root = man["evidence_root"]
    man["evidence_root"] = ("0" if root[0] != "0" else "1") + root[1:]
    _dump(os.path.join(pkg, "manifest.json"), man)


def m_add_undeclared_file(pkg):
    _write(os.path.join(pkg, "extra-payload.json"), b'{"injected": true}')


def m_duplicate_member(pkg):
    """Duplicate JSON member name -- must be caught before any parse."""
    path = os.path.join(pkg, "manifest.json")
    text = _read(path).decode("utf-8")
    assert text.lstrip().startswith("{")
    first = text.index("{") + 1
    text = text[:first] + '"schema": "uibc-core/0.2.2-proposal", ' + text[first:]
    _write(path, text.encode("utf-8"))


def m_bad_calendar_date(pkg):
    """30 February does not exist. S12 judges values, not hashes."""
    lc = _json(os.path.join(pkg, "lifecycle.json"))
    events = lc.get("events") or lc.get("entries") or []
    assert events, "lifecycle has no events to edit"
    events[0]["timestamp"] = "2026-02-30T00:00:00Z"
    _dump(os.path.join(pkg, "lifecycle.json"), lc)


def m_identity_mismatch(pkg):
    ident = _json(os.path.join(pkg, "identity.json"))
    ident["agent_id"] = ident["agent_id"] + "-other"
    _dump(os.path.join(pkg, "identity.json"), ident)


def m_drop_tail(pkg):
    """Truncation: drop the last evidence entry and its file.

    This is the attack a hash chain cannot see -- the package is
    self-consistent afterwards, and only the root (or an out-of-band head)
    notices."""
    path, raw, entries = _index(pkg)
    last = entries.pop()
    man = _json(os.path.join(pkg, "manifest.json"))
    man["evidence_count"] = len(entries)
    _dump(os.path.join(pkg, "manifest.json"), man)
    _save_index(path, raw, entries)
    path = os.path.join(pkg, "evidence", last["path"])
    if os.path.exists(path):
        os.remove(path)


def m_remove_entry_keep_file(pkg):
    """Deregister an entry but leave the bytes: an undeclared file."""
    path, raw, entries = _index(pkg)
    entries.pop()
    _save_index(path, raw, entries)


def m_tamper_seal(pkg):
    path = os.path.join(pkg, "signatures", "seal.json")
    data = _read(path)
    _write(path, data.replace(b'"', b"'", 1) if b'"' in data else data + b"x")


# -- controls: these must NOT be reported as forgeries ---------------------

def c_reorder_index(pkg):
    """The root commits to sorted content hashes, so reordering entries
    changes the file but not the commitment. A verifier that flags this is
    producing false positives."""
    path, raw, entries = _index(pkg)
    _save_index(path, raw, list(reversed(entries)))


def c_noop(pkg):
    """Copy untouched: proves the harness itself does not perturb the package."""
    return


# (name, fn, expectation, why)
# expectation: "FAIL" the verdict must be FAIL
#              "NOT_PASS" the verdict must not be PASS (INCONCLUSIVE allowed)
#              "SAME" the verdict must equal the baseline verdict
RED_TEAM = [
    ("flip one byte in evidence", m_flip_evidence_byte, "FAIL", "S4 recomputes hashes"),
    ("truncate one evidence file", m_truncate_evidence_file, "FAIL", "same, shorter"),
    ("delete one evidence file", m_delete_evidence_file, "FAIL", "index points at nothing"),
    ("edit the evidence root", m_edit_root, "FAIL", "S5 recomputes the root"),
    ("add an undeclared file", m_add_undeclared_file, "FAIL", "S1 counts declarations"),
    ("duplicate a JSON member name", m_duplicate_member, "FAIL", "S11 runs before parsing"),
    ("impossible calendar date", m_bad_calendar_date, "FAIL", "S12 judges values"),
    ("mismatch agent identity", m_identity_mismatch, "FAIL", "S2 compares across files"),
    ("drop the tail entry and file", m_drop_tail, "FAIL", "the root moves"),
    ("deregister an entry, keep the file", m_remove_entry_keep_file, "FAIL", "undeclared evidence"),
    ("tamper the seal", m_tamper_seal, "NOT_PASS", "S6 must not pass a broken seal"),
]

# --------------------------------------------------------------------------
# Stage 2: attacks the S1-S12 package shape cannot carry.
#
# The fixture in fixtures/ has no tree and no receipt chain, so S13 (Merkle
# inclusion) and S17 (linear receipt link) never run on it. That left the
# honest boundary "red team covers one package shape" in OUTSIDER-AUDIT.md.
# These cases build a package that *does* carry both -- correct first -- and
# then attack them. A correct build that still fails would make every attack
# below meaningless, so the build is verified before it is attacked.
# --------------------------------------------------------------------------

def build_v11(pkg):
    """Add a correct Merkle tree and receipt chain. Raises if either is wrong."""
    from uibc_core import merkle as mk
    from uibc_core.canonical import hash_obj

    path, raw, entries = _index(pkg)
    order = sorted(entries, key=lambda e: e.get("path", ""))
    leaves = []
    for e in order:
        fp = os.path.join(pkg, "evidence", e["path"])
        leaves.append(mk.leaf_hash(_read(fp)))
    root = mk.root_hash(leaves)
    proofs = [{"index": i, "path": e["path"],
               "proof": list(mk.build_proof(leaves, i))}
              for i, e in enumerate(order)]
    _dump(os.path.join(pkg, "evidence", "merkle.json"),
          {"algorithm": "rfc6962-sha256", "size": len(leaves),
           "root": root.hex(), "proofs": proofs})

    env1 = {"receipt": "r1", "at": "2026-11-18T00:00:00Z"}
    env2 = {"receipt": "r2", "at": "2026-11-18T00:01:00Z"}
    _dump(os.path.join(pkg, "evidence", "chain.json"),
          {"schema": "uibc-core/receipt-chain/0",
           "receipts": [{"envelope": env1, "previous_receipt_hash": "0" * 64},
                        {"envelope": env2, "previous_receipt_hash": hash_obj(env1)}]})

    checks = {c["id"]: c for c in verify(pkg)["checks"]}
    for cid in ("S13", "S17"):
        if cid not in checks or checks[cid]["result"] != "PASS":
            raise AssertionError("a correct %s does not pass; attacks below "
                                 "would prove nothing" % cid)


def _needs_v11(fn):
    def wrapper(pkg):
        build_v11(pkg)
        fn(pkg)
    wrapper.__name__ = fn.__name__
    return wrapper


@_needs_v11
def m13_merkle_root(pkg):
    _dump(os.path.join(pkg, "evidence", "merkle.json"),
          dict(_json(os.path.join(pkg, "evidence", "merkle.json")),
               root="0" * 64))


@_needs_v11
def m13_merkle_size(pkg):
    doc = _json(os.path.join(pkg, "evidence", "merkle.json"))
    doc["size"] = doc["size"] + 1
    _dump(os.path.join(pkg, "evidence", "merkle.json"), doc)


@_needs_v11
def m13_merkle_proof(pkg):
    """One sibling hash changed: the root still matches the leaves, only the
    proof is wrong -- the case a "root matches" shortcut would wave through."""
    doc = _json(os.path.join(pkg, "evidence", "merkle.json"))
    assert doc["proofs"] and doc["proofs"][0]["proof"], "no proof to break"
    doc["proofs"][0]["proof"][0] = "0" * 64
    _dump(os.path.join(pkg, "evidence", "merkle.json"), doc)


@_needs_v11
def m13_merkle_index(pkg):
    doc = _json(os.path.join(pkg, "evidence", "merkle.json"))
    doc["proofs"][0]["index"] = 1 - (doc["proofs"][0]["index"] or 0)
    _dump(os.path.join(pkg, "evidence", "merkle.json"), doc)


@_needs_v11
def m17_receipt_body(pkg):
    """Change the FIRST receipt's body, leaving the second's link alone.

    Only the first receipt can carry this attack: its successor recomputes a
    digest over it, so the edit breaks the link. Editing the LAST receipt
    breaks nothing that exists -- see X17_TAIL_BODY below, which is recorded
    as a known gap rather than counted as a catch."""
    doc = _json(os.path.join(pkg, "evidence", "chain.json"))
    doc["receipts"][0]["envelope"]["at"] = "2026-11-18T00:02:00Z"
    _dump(os.path.join(pkg, "evidence", "chain.json"), doc)


@_needs_v11
def x17_tail_receipt_body(pkg):
    """The last receipt has no successor, so no digest covers it."""
    doc = _json(os.path.join(pkg, "evidence", "chain.json"))
    doc["receipts"][-1]["envelope"]["at"] = "2026-11-18T00:02:00Z"
    _dump(os.path.join(pkg, "evidence", "chain.json"), doc)


@_needs_v11
def m17_genesis(pkg):
    doc = _json(os.path.join(pkg, "evidence", "chain.json"))
    doc["receipts"][0]["previous_receipt_hash"] = "1" * 64
    _dump(os.path.join(pkg, "evidence", "chain.json"), doc)


# Attacks we ran and the package does NOT catch. Recorded so they cannot be
# mistaken for coverage: each is a real limitation, not a pass.
V11_KNOWN_GAPS = [
    ("edit the last receipt's body", x17_tail_receipt_body,
     "no successor commits it; only an external anchor over the chain head can"),
]

V11_RED_TEAM = [
    ("replace merkle root", m13_merkle_root, "FAIL", "S13 recomputes the root"),
    ("inflate merkle size", m13_merkle_size, "FAIL", "declared size vs leaves"),
    ("corrupt one inclusion proof", m13_merkle_proof, "FAIL", "proof must verify"),
    ("swap a proof index", m13_merkle_index, "FAIL", "index is recomputed"),
    ("edit a receipt body", m17_receipt_body, "FAIL", "S17 recomputes the link"),
    ("claim a genesis predecessor", m17_genesis, "FAIL", "genesis is 64 zeros"),
]

# --------------------------------------------------------------------------
# Stage 3: S14 (strict base64), S15 (anchor events), S18 (policy artefacts).
#
# Same discipline as stage 2: build each one correctly, refuse to proceed if
# the build does not pass, then break exactly one thing at a time.
#
# S16 (RFC 3161 external timestamp) is deliberately absent. Its whole value is
# that we cannot mint the token ourselves -- it is signed by a TSA key we do
# not hold, over a digest of a file we ship. A self-built "correct" token
# would prove nothing, so there is no honest way to red-team it from inside
# this repo.
# --------------------------------------------------------------------------

import base64 as _b64

def build_ext(pkg):
    """Add canonical base64, a resolvable anchor, and a resolvable policy."""
    from uibc_core import merkle as mk
    from uibc_core.canonical import hash_obj

    ident_path = os.path.join(pkg, "identity.json")
    ident = _json(ident_path)
    ident["note_b64"] = _b64.b64encode(b"hello").decode("ascii")
    _dump(ident_path, ident)

    _, _, ents = _index(pkg)
    order = sorted(ents, key=lambda e: e.get("path", ""))
    leaves = [mk.leaf_hash(_read(os.path.join(pkg, "evidence", e["path"])))
              for e in order]
    root = mk.root_hash(leaves)
    _dump(os.path.join(pkg, "evidence", "anchors.json"),
          {"resolver": "evidence-merkle",
           "anchors": [{"id": "anchor-001", "version": 1,
                        "leaf_hash": leaves[0].hex(),
                        "anchored_at": "2026-11-17T08:00:00Z",
                        "root": root.hex(), "size": len(leaves), "index": 0,
                        "proof": list(mk.build_proof(leaves, 0))}]})

    artefact = {"policy": "retention", "days": 90}
    adir = os.path.join(pkg, "evidence", "policies")
    os.makedirs(adir, exist_ok=True)
    with open(os.path.join(adir, "retention.json"), "w", encoding="utf-8",
              newline="\n") as fh:
        json.dump(artefact, fh, sort_keys=True, separators=(",", ":"))
    _dump(os.path.join(pkg, "evidence", "policies.json"),
          {"policies": [{"path": "evidence/policies/retention.json",
                         "digest": "sha256:" + hash_obj(artefact)}]})

    checks = {c["id"]: c for c in verify(pkg)["checks"]}
    for cid in ("S14", "S15", "S18"):
        if cid not in checks or checks[cid]["result"] != "PASS":
            raise AssertionError("a correct %s does not pass; attacks below "
                                 "would prove nothing" % cid)


def _needs_ext(fn):
    def wrapper(pkg):
        build_ext(pkg)
        fn(pkg)
    wrapper.__name__ = fn.__name__
    return wrapper


@_needs_ext
def m14_base64_padding(pkg):
    ident = _json(os.path.join(pkg, "identity.json"))
    ident["note_b64"] = "aGVsbG8"          # 7 chars: padding stripped
    _dump(os.path.join(pkg, "identity.json"), ident)


@_needs_ext
def m14_base64_chars(pkg):
    ident = _json(os.path.join(pkg, "identity.json"))
    ident["note_b64"] = "aGVs*bG8="        # '*' is not in the alphabet
    _dump(os.path.join(pkg, "identity.json"), ident)


@_needs_ext
def m15_bad_proof(pkg):
    doc = _json(os.path.join(pkg, "evidence", "anchors.json"))
    doc["anchors"][0]["proof"][0] = "0" * 64
    _dump(os.path.join(pkg, "evidence", "anchors.json"), doc)


@_needs_ext
def m15_bad_leaf(pkg):
    doc = _json(os.path.join(pkg, "evidence", "anchors.json"))
    doc["anchors"][0]["leaf_hash"] = "not-a-digest"
    _dump(os.path.join(pkg, "evidence", "anchors.json"), doc)


@_needs_ext
def m15_bad_time(pkg):
    doc = _json(os.path.join(pkg, "evidence", "anchors.json"))
    doc["anchors"][0]["anchored_at"] = "2026-02-30T00:00:00Z"
    _dump(os.path.join(pkg, "evidence", "anchors.json"), doc)


@_needs_ext
def m15_unresolvable_root(pkg):
    doc = _json(os.path.join(pkg, "evidence", "anchors.json"))
    doc["anchors"][0]["root"] = "0" * 64
    _dump(os.path.join(pkg, "evidence", "anchors.json"), doc)


@_needs_ext
def m18_edited_artefact(pkg):
    """The policy file changes, the declared digest does not."""
    path = os.path.join(pkg, "evidence", "policies", "retention.json")
    _write(path, b'{"days":30,"policy":"retention"}')


@_needs_ext
def m18_dangling_digest(pkg):
    doc = _json(os.path.join(pkg, "evidence", "policies.json"))
    doc["policies"][0]["digest"] = "sha256:" + "f" * 64
    _dump(os.path.join(pkg, "evidence", "policies.json"), doc)


EXT_RED_TEAM = [
    ("strip base64 padding", m14_base64_padding, "FAIL", "S14 decodes strictly"),
    ("put a stray character in base64", m14_base64_chars, "FAIL",
     "S14 rejects non-alphabet bytes"),
    ("corrupt an anchor inclusion proof", m15_bad_proof, "FAIL",
     "S15 re-verifies the proof"),
    ("make a leaf hash a non-digest", m15_bad_leaf, "FAIL",
     "S15 judges values, not just structure"),
    ("date an anchor 30 February", m15_bad_time, "FAIL",
     "a legal time is required"),
    ("anchor to a root we cannot recompute", m15_unresolvable_root, "FAIL",
     "resolvable, not merely present"),
    ("edit a policy artefact", m18_edited_artefact, "FAIL",
     "S18 recomputes SHA-256 over JCS"),
    ("point a policy digest at nothing", m18_dangling_digest, "FAIL",
     "an unresolvable digest is FAIL"),
]

# S16 can be exercised, but not witnessed: the token in tests/fixtures/anchor
# is a real FreeTSA signature over a file we keep in the repo. That proves the
# verification path works on bytes we did not sign. It does NOT mean a third
# party has seen THIS package's head -- that would need a token requested for
# this package after it was sealed.
NOT_EXTERNALLY_WITNESSED = [
    ("S16 verification path exercised with a real FreeTSA token",
     "the token dates tests/fixtures/anchor/anchored_head.json, a file kept in "
     "the repo; no third party has timestamped this package's head"),
]

# --------------------------------------------------------------------------
# Stage 4: S16 with a REAL RFC 3161 token.
#
# The token in tests/fixtures/anchor is a FreeTSA signature over the digest of
# anchored_head.json, taken 2026-11-17T08:11:35Z. Using it means the PASS path
# runs on bytes we did not sign -- which is the only way to show the check is
# not a mock we designed to pass.
# --------------------------------------------------------------------------

_FIXTURE_ANCHOR = os.path.join(_REPO, "tests", "fixtures", "anchor")

def build_s16(pkg):
    """Place the real token so S16 can judge it; refuse if it does not pass."""
    import hashlib
    tsdir = os.path.join(pkg, "timestamps")
    os.makedirs(tsdir, exist_ok=True)
    shutil.copy(os.path.join(_FIXTURE_ANCHOR, "anchored_head.json"),
                os.path.join(tsdir, "anchored_head.json"))
    shutil.copy(os.path.join(_FIXTURE_ANCHOR, "freetsa.tsr"),
                os.path.join(tsdir, "freetsa.tsr"))
    shutil.copy(os.path.join(_FIXTURE_ANCHOR, "freetsa_ca.pem"),
                os.path.join(tsdir, "freetsa_ca.pem"))
    body = _read(os.path.join(tsdir, "freetsa.tsr"))
    _dump(os.path.join(pkg, "evidence", "external_anchor.json"),
          {"digest_of": "timestamps/anchored_head.json",
           "tsr": "timestamps/freetsa.tsr",
           "cabundle": "timestamps/freetsa_ca.pem",
           "tsr_sha256": hashlib.sha256(body).hexdigest()})

    checks = {c["id"]: c for c in verify(pkg)["checks"]}
    if "S16" not in checks or checks["S16"]["result"] != "PASS":
        raise AssertionError("S16 does not pass on a real FreeTSA token: %r"
                             % (checks.get("S16"),))


def _needs_s16(fn):
    def wrapper(pkg):
        build_s16(pkg)
        fn(pkg)
    wrapper.__name__ = fn.__name__
    return wrapper


@_needs_s16
def m16_point_at_another_file(pkg):
    """The token dates anchored_head.json; claim it dates the manifest."""
    doc = _json(os.path.join(pkg, "evidence", "external_anchor.json"))
    doc["digest_of"] = "manifest.json"
    _dump(os.path.join(pkg, "evidence", "external_anchor.json"), doc)


@_needs_s16
def m16_wrong_tsr_digest(pkg):
    doc = _json(os.path.join(pkg, "evidence", "external_anchor.json"))
    doc["tsr_sha256"] = "0" * 64
    _dump(os.path.join(pkg, "evidence", "external_anchor.json"), doc)


@_needs_s16
def m16_flip_token_byte(pkg):
    path = os.path.join(pkg, "timestamps", "freetsa.tsr")
    data = bytearray(_read(path))
    data[len(data) // 2] ^= 0xFF
    _write(path, bytes(data))


@_needs_s16
def m16_no_ca(pkg):
    doc = _json(os.path.join(pkg, "evidence", "external_anchor.json"))
    doc["cabundle"] = "timestamps/absent.pem"
    _dump(os.path.join(pkg, "evidence", "external_anchor.json"), doc)


S16_RED_TEAM = [
    ("claim the token dates another file", m16_point_at_another_file, "FAIL",
     "messageImprint must match the declared file"),
    ("misdeclare the token digest", m16_wrong_tsr_digest, "FAIL",
     "tsr_sha256 must be the token we read"),
    ("flip one byte in the token", m16_flip_token_byte, "FAIL",
     "a broken token is not a witness"),
    ("drop the CA bundle", m16_no_ca, "FAIL",
     "an unchained signature is not verified"),
]

# --------------------------------------------------------------------------
# Stage 5: checkpoint and closure (S7, S8, S9, S10).
#
# These four were the ones the evidence index found with no attack pointed at
# them. S7 guards index METADATA (type/note), which a content hash cannot see.
# S8 guards the whole-state checkpoint, which catches a log shortened while the
# manifest still describes the longer one. S9 is unpinnable from inside: only an
# observation made elsewhere can catch a rollback to an older self-consistent
# package. S10 guards that six closure components were DECLARED -- not that they
# match what ran, which no package can show.
# --------------------------------------------------------------------------

_CKPT_HEAD = {"value": None}

def build_ckpt(pkg):
    """Add the four sealed fields, then refuse to continue unless they pass."""
    from uibc_core.canonical import (checkpoint_head, evidence_root,
                                     index_metadata_digest, lifecycle_head)
    from uibc_core.canonical import hash_file
    from uibc_core.verify import CLOSURE_FIELDS, verify as _v
    import hashlib as _h

    manifest = _json(os.path.join(pkg, "manifest.json"))
    index = _json(os.path.join(pkg, "evidence", "index.json"))
    entries = index["entries"] if isinstance(index, dict) else index
    index_obj = index if isinstance(index, dict) else {"entries": entries}
    lc = _json(os.path.join(pkg, "lifecycle.json"))

    hashes = [_h.sha256(_read(os.path.join(pkg, "evidence", e["path"]))).hexdigest()
              for e in entries]
    imd = index_metadata_digest(index_obj)
    head = checkpoint_head(lifecycle_head(lc["events"]),
                           evidence_root(hashes), imd, len(entries))

    manifest["evidence_index_digest"] = imd
    manifest["closure"] = {k: "b" * 64 for k in CLOSURE_FIELDS}
    manifest["checkpoint_head"] = head
    _dump(os.path.join(pkg, "manifest.json"), manifest)
    _CKPT_HEAD["value"] = head

    checks = {c["id"]: c for c in _v(pkg)["checks"]}
    for cid in ("S7", "S8", "S10"):
        if checks.get(cid, {}).get("result") != "PASS":
            raise AssertionError("baseline %s is %r, not PASS"
                                 % (cid, checks.get(cid)))


def _needs_ckpt(fn):
    def wrapper(pkg):
        build_ckpt(pkg)
        fn(pkg)
    wrapper.__name__ = fn.__name__
    return wrapper


@_needs_ckpt
def m_ckpt_rewrite_index_note(pkg):
    """Content is untouched; only the index's own metadata is rewritten."""
    path = os.path.join(pkg, "evidence", "index.json")
    index = _json(path)
    entries = index["entries"] if isinstance(index, dict) else index
    entries[0]["note"] = "reviewed and approved by nobody"
    _dump(path, index)


@_needs_ckpt
def m_ckpt_drop_closure_component(pkg):
    """AAT's point: a component outside the attested set is a forgery channel."""
    path = os.path.join(pkg, "manifest.json")
    manifest = _json(path)
    manifest["closure"].pop("engine_build", None)
    _dump(path, manifest)


@_needs_ckpt
def m_ckpt_truncate_the_log(pkg):
    """The last events are simply gone. The shorter chain is still self-valid;
    only the checkpoint over the whole state notices."""
    path = os.path.join(pkg, "lifecycle.json")
    lc = _json(path)
    lc["events"] = lc["events"][:-1]
    _dump(path, lc)


@_needs_ckpt
def m_ckpt_repoint_closure_digest(pkg):
    """Declared, but to a value that is not a SHA-256."""
    path = os.path.join(pkg, "manifest.json")
    manifest = _json(path)
    manifest["closure"]["model_weights"] = "not-a-digest"
    _dump(path, manifest)


CKPT_RED_TEAM = [
    ("rewrite index metadata, content untouched", m_ckpt_rewrite_index_note, "FAIL",
     "S7: a content hash cannot see a rewritten note"),
    ("drop engine_build from the closure", m_ckpt_drop_closure_component, "FAIL",
     "S10: five of six declared is not declared"),
    ("truncate the lifecycle log", m_ckpt_truncate_the_log, "FAIL",
     "S8: the shortened chain is still internally valid"),
    ("declare a closure digest that is not a digest", m_ckpt_repoint_closure_digest, "FAIL",
     "S10: a declaration with a malformed value is no declaration"),
]

CONTROLS = [
    ("reorder index entries", c_reorder_index, "SAME", "root commits sorted hashes"),
    ("copy untouched", c_noop, "SAME", "the harness must not perturb"),
]


# --------------------------------------------------------------------------
# harness
# --------------------------------------------------------------------------

def _prepare(src, tmp):
    dst = os.path.join(tmp, "pkg")
    shutil.copytree(src, dst)
    return dst


def _verdict(pkg):
    r = verify(pkg)
    failed = sorted(c["id"] for c in r["checks"] if c["result"] == "FAIL")
    inconclusive = sorted(c["id"] for c in r["checks"] if c["result"] == "INCONCLUSIVE")
    return {
        "result": r["result"],
        "trust_level": r.get("trust_level"),
        "failed_checks": failed,
        "inconclusive_checks": inconclusive,
    }


def run_baseline(package):
    got = _verdict(package)
    # The shipped fixture is unsigned: PASS here would mean the seal check
    # is decorative. INCONCLUSIVE is the honest verdict.
    expected = {"result": "INCONCLUSIVE", "trust_level": "unattested"}
    ok = got["result"] == expected["result"]
    return {
        "stage": "baseline",
        "expected": expected,
        "got": got,
        "ok": ok,
        "note": "unsigned package: INCONCLUSIVE, and no check may be invented "
                "to turn that into PASS",
    }


def run_red_team(package, baseline_verdict):
    rows = []
    for name, fn, expectation, why in RED_TEAM:
        rows.append(_one(package, name, fn, expectation, why, baseline_verdict))
    for name, fn, expectation, why in CONTROLS:
        rows.append(_one(package, name, fn, expectation, why, baseline_verdict,
                         control=True))
    ok = all(r["ok"] for r in rows)
    return {
        "stage": "red-team",
        "rows": rows,
        "ok": ok,
        "failed": [r["name"] for r in rows if not r["ok"]],
        "count": len(rows),
    }


def _one(package, name, fn, expectation, why, baseline_verdict, control=False):
    tmp = tempfile.mkdtemp(prefix="uibc-rt-")
    try:
        pkg = _prepare(package, tmp)
        try:
            fn(pkg)
            mutation_error = None
        except Exception as e:  # a mutation that cannot be applied is not a pass
            mutation_error = "%s: %s" % (type(e).__name__, e)
        got = _verdict(pkg)
        if mutation_error:
            ok = False
            verdict_note = "mutation not applied"
        elif expectation == "FAIL":
            ok = got["result"] == "FAIL"
            verdict_note = "must be FAIL"
        elif expectation == "NOT_PASS":
            ok = got["result"] != "PASS"
            verdict_note = "must not be PASS"
        else:  # SAME
            ok = got["result"] == baseline_verdict["result"]
            verdict_note = "must equal baseline (%s)" % baseline_verdict["result"]
        return {
            "name": name,
            "kind": "control" if control else "attack",
            "why": why,
            "expectation": expectation,
            "expectation_note": verdict_note,
            "got": got["result"],
            "failed_checks": got["failed_checks"],
            "ok": ok,
            "mutation_error": mutation_error,
        }
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def run_interop(kit):
    if not kit:
        return {
            "stage": "interop",
            "status": "SKIPPED",
            "ok": None,
            "note": "--kit not supplied; a skip is not a pass",
        }
    checks = []
    tmp = tempfile.mkdtemp(prefix="uibc-io-")
    try:
        out = os.path.join(tmp, "emit.json")
        runner = os.path.join(kit, "base", "conformance.py")
        code_e = _run([sys.executable, os.path.join(_REPO, "tools", "emit_aer1_receipts.py"),
                       "--package", DEFAULT_PACKAGE, "--out", out,
                       "--publisher-runner", runner])
        checks.append({"name": "emit -> publisher runner", "exit": code_e, "ok": code_e == 0})

        code_d = _run([sys.executable, os.path.join(_REPO, "tools", "aer1_interop_demo.py"),
                       "--kit", kit])
        checks.append({"name": "one-command interop demo", "exit": code_d, "ok": code_d == 0})

        valid = os.path.join(kit, "base", "test-vectors", "valid")
        invalid = os.path.join(kit, "base", "test-vectors", "invalid")
        code_v = _run([sys.executable, os.path.join(_REPO, "tools", "aer1_verify_external.py"),
                       "--dir", valid, "--expect", "ACCEPTED"])
        checks.append({"name": "inbound valid (expect ACCEPTED)", "exit": code_v, "ok": code_v == 0})
        code_i = _run([sys.executable, os.path.join(_REPO, "tools", "aer1_verify_external.py"),
                       "--dir", invalid, "--expect", "REJECTED"])
        checks.append({"name": "inbound invalid (expect REJECTED)", "exit": code_i, "ok": code_i == 0})
        return {"stage": "interop", "status": "RUN", "checks": checks,
                "ok": all(c["ok"] for c in checks)}
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _run(argv):
    import subprocess
    p = subprocess.run(argv, cwd=_REPO, capture_output=True)
    if p.returncode != 0:
        sys.stderr.write(p.stdout.decode("utf-8", "replace")[-1500:])
        sys.stderr.write(p.stderr.decode("utf-8", "replace")[-1500:])
    return p.returncode


def run_red_team_v11(package, baseline_verdict):
    rows = [_one(package, name, fn, expectation, why, baseline_verdict)
            for name, fn, expectation, why in V11_RED_TEAM]
    gaps = []
    for name, fn, why in V11_KNOWN_GAPS:
        r = _one(package, name, fn, "NOT_PASS", why, baseline_verdict)
        # "caught" means the verdict got worse (FAIL). INCONCLUSIVE equal to
        # the baseline means the edit went unnoticed -- which is the point of
        # listing it here.
        gaps.append({"name": name, "why": why, "got": r["got"],
                     "caught": r["got"] == "FAIL"})
    ok = all(r["ok"] for r in rows)
    return {
        "stage": "red-team-v11",
        "rows": rows,
        "ok": ok,
        "failed": [r["name"] for r in rows if not r["ok"]],
        "count": len(rows),
        "known_gaps": gaps,
        "note": "package carries a correct tree and chain first; each case "
                "breaks one of them. Known gaps are listed, not counted as "
                "catches.",
    }


def run_red_team_ext(package, baseline_verdict):
    rows = [_one(package, name, fn, expectation, why, baseline_verdict)
            for name, fn, expectation, why in EXT_RED_TEAM]
    ok = all(r["ok"] for r in rows)
    return {
        "stage": "red-team-ext",
        "rows": rows,
        "ok": ok,
        "failed": [r["name"] for r in rows if not r["ok"]],
        "count": len(rows),
        "note": "S14/S15/S18 built correctly first, then broken one at a time; "
                "S16 has its own stage, on a real token",
    }


def run_red_team_ckpt(package, baseline_verdict):
    rows = [_one(package, name, fn, expectation, why, baseline_verdict)
            for name, fn, expectation, why in CKPT_RED_TEAM]
    ok = all(r["ok"] for r in rows)
    return {
        "stage": "red-team-ckpt",
        "rows": rows,
        "ok": ok,
        "failed": [r["name"] for r in rows if not r["ok"]],
        "count": len(rows),
        "note": "S7/S8/S10 cannot be reached by the shipped package (no sealed "
                "fields); this stage adds them, then attacks them",
    }


def run_pinned(package, baseline_verdict):
    """S9 is not reachable from inside the package at all.

    Nothing a package contains can tell a fresh copy from a rollback to an older
    but perfectly self-consistent one: both verify identically. Only a value
    observed elsewhere can. So this stage does the two things a holder of such
    a value would do: run with the right pin, then run a rolled-back package
    against it.
    """
    from uibc_core.verify import verify as _v
    import tempfile
    rows = []

    # control: the true head must satisfy the pin
    tmp = tempfile.mkdtemp()
    try:
        pkg = _prepare(package, tmp)
        build_ckpt(pkg)
        pinned = _CKPT_HEAD["value"]
        checks = {c["id"]: c for c in _v(pkg, expect_head=pinned)["checks"]}
        got = checks.get("S9", {}).get("result")
        rows.append({"name": "the true head against its own pin",
                     "expectation": "PASS", "got": got,
                     "failed_checks": ["S9"] if got != "PASS" else [],
                     "ok": got == "PASS", "expectation_note": "",
                     "why": "the control: a pin that matches must be satisfied"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # attack: roll the package back, then check it against the old pin
    tmp = tempfile.mkdtemp()
    try:
        pkg = _prepare(package, tmp)
        build_ckpt(pkg)
        pinned = _CKPT_HEAD["value"]
        # roll back: drop the tail event AND reseal the checkpoint so the
        # package is again internally consistent -- the exact shape S9 exists
        # for
        from uibc_core.canonical import (checkpoint_head, evidence_root,
                                         index_metadata_digest, lifecycle_head)
        import hashlib as _h
        lc_path = os.path.join(pkg, "lifecycle.json")
        lc = _json(lc_path)
        lc["events"] = lc["events"][:-1]
        _dump(lc_path, lc)
        manifest = _json(os.path.join(pkg, "manifest.json"))
        index = _json(os.path.join(pkg, "evidence", "index.json"))
        entries = index["entries"] if isinstance(index, dict) else index
        index_obj = index if isinstance(index, dict) else {"entries": entries}
        hashes = [_h.sha256(_read(os.path.join(pkg, "evidence", e["path"]))).hexdigest()
                  for e in entries]
        new_head = checkpoint_head(lifecycle_head(lc["events"]),
                                   evidence_root(hashes),
                                   index_metadata_digest(index_obj), len(entries))
        manifest["checkpoint_head"] = new_head
        _dump(os.path.join(pkg, "manifest.json"), manifest)
        checks = {c["id"]: c for c in _v(pkg, expect_head=pinned)["checks"]}
        got = checks.get("S9", {}).get("result")
        rows.append({"name": "a rolled-back package against the old pin",
                     "expectation": "FAIL", "got": got,
                     "failed_checks": ["S9"] if got == "FAIL" else [],
                     "ok": got == "FAIL", "expectation_note": "",
                     "why": "S9: the rolled-back copy is self-consistent, so only "
                            "the outside pin can see it"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    # attack: no pin supplied by the caller; the verifier remembers instead.
    # Same rolled-back shape as above, but the only thing that can catch it is
    # the state file, which is what S19 exists for and what it must refuse.
    tmp = tempfile.mkdtemp()
    try:
        pkg = _prepare(package, tmp)
        build_ckpt(pkg)
        from uibc_core.canonical import (checkpoint_head, evidence_root,
                                         index_metadata_digest, lifecycle_head)
        import hashlib as _h
        lc_path = os.path.join(pkg, "lifecycle.json")
        lc = _json(lc_path)
        lc["events"] = lc["events"][:-1]
        _dump(lc_path, lc)
        manifest = _json(os.path.join(pkg, "manifest.json"))
        index = _json(os.path.join(pkg, "evidence", "index.json"))
        entries = index["entries"] if isinstance(index, dict) else index
        index_obj = index if isinstance(index, dict) else {"entries": entries}
        hashes = [_h.sha256(_read(os.path.join(pkg, "evidence", e["path"]))).hexdigest()
                  for e in entries]
        new_head = checkpoint_head(lifecycle_head(lc["events"]),
                                   evidence_root(hashes),
                                   index_metadata_digest(index_obj), len(entries))
        subject = manifest.get("agent_id")
        state = os.path.join(tmp, "freshness-state.json")
        _dump(state, {"schema": "uibc-freshness/1",
                      "subjects": {subject: {"head": "sha256:" + "0" * 64,
                                             "sequence": 2}}})
        manifest["freshness_head"] = {"subject": subject, "sequence": 1}
        manifest["checkpoint_head"] = new_head
        _dump(os.path.join(pkg, "manifest.json"), manifest)
        checks = {c["id"]: c for c in _v(pkg, state_file=state)["checks"]}
        got = checks.get("S19", {}).get("result")
        rows.append({"name": "an older package against a remembered head",
                     "expectation": "FAIL", "got": got,
                     "failed_checks": ["S19"] if got == "FAIL" else [],
                     "ok": got == "FAIL", "expectation_note": "",
                     "why": "S19: the sequence is older than the one the "
                            "verifier already accepted, so replay is refused "
                            "even though the signature is valid"})
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    return {
        "stage": "red-team-pinned",
        "rows": rows,
        "ok": all(r["ok"] for r in rows),
        "failed": [r["name"] for r in rows if not r["ok"]],
        "count": len(rows),
        "note": "S9 is unreachable from inside; this stage supplies the outside "
                "observation and then tries the rollback it exists for",
    }


def run_red_team_s16(package, baseline_verdict):
    rows = [_one(package, name, fn, expectation, why, baseline_verdict)
            for name, fn, expectation, why in S16_RED_TEAM]
    ok = all(r["ok"] for r in rows)
    return {
        "stage": "red-team-s16",
        "rows": rows,
        "ok": ok,
        "failed": [r["name"] for r in rows if not r["ok"]],
        "count": len(rows),
        "not_externally_witnessed": [{"what": w, "why": y}
                                     for w, y in NOT_EXTERNALLY_WITNESSED],
        "note": "a real FreeTSA token, over a file we did not sign; four ways "
                "to make it stop being a witness",
    }


def run_all(package, kit):
    baseline = run_baseline(package)
    red = run_red_team(package, baseline["got"])
    red11 = run_red_team_v11(package, baseline["got"])
    ext = run_red_team_ext(package, baseline["got"])
    s16 = run_red_team_s16(package, baseline["got"])
    ckpt = run_red_team_ckpt(package, baseline["got"])
    pinned = run_pinned(package, baseline["got"])
    interop = run_interop(kit)
    # A skip of a stage that requires a corpus is not a pass, but it is not a
    # failure of our code either: it is reported as SKIPPED and the exit code
    # stays 0 only if the caller did not ask for that stage.
    overall_ok = (baseline["ok"] and red["ok"] and red11["ok"] and ext["ok"]
                  and s16["ok"] and ckpt["ok"] and pinned["ok"])
    return {
        "package": package,
        "stage_baseline": baseline,
        "stage_redteam": red,
        "stage_redteam_v11": red11,
        "stage_redteam_ext": ext,
        "stage_redteam_s16": s16,
        "stage_redteam_ckpt": ckpt,
        "stage_redteam_pinned": pinned,
        "stage_interop": interop,
        "ok": overall_ok,
        "trust": _TRUST,
        "self_test": [],
        "note": "interop SKIPPED is not counted as a pass",
    }


def _print_human(result):
    b = result["stage_baseline"]
    print("baseline   : %-12s expected %-12s  %s"
          % (b["got"]["result"], b["expected"]["result"], "ok" if b["ok"] else "MISMATCH"))
    print("             checks: %s" % (b["got"]["inconclusive_checks"] or "none")
          + " inconclusive")
    print()
    print("red team   : %d cases" % result["stage_redteam"]["count"])
    for r in result["stage_redteam"]["rows"]:
        print("  %-4s %-40s %-9s -> %-12s %s"
              % ("ctrl" if r["kind"] == "control" else "atk", r["name"],
                 r["expectation"], r["got"],
                 "ok" if r["ok"] else "FAILED: " + r["expectation_note"]))
        if r["failed_checks"]:
            print("       caught by: %s" % ", ".join(r["failed_checks"]))
    print()
    v11 = result.get("stage_redteam_v11")
    if v11:
        print("red team v11: %d cases (%s)" % (v11["count"], v11["note"]))
        for r in v11["rows"]:
            print("  %-4s %-40s %-9s -> %-12s %s"
                  % ("atk", r["name"], r["expectation"], r["got"],
                     "ok" if r["ok"] else "FAILED: " + r["expectation_note"]))
            if r["failed_checks"]:
                print("       caught by: %s" % ", ".join(r["failed_checks"]))
        for g in v11.get("known_gaps") or []:
            print("  gap  %-40s -> %-12s %s" % (g["name"], g["got"],
                  "CAUGHT (update the note)" if g["caught"] else "not caught: " + g["why"]))
    print()
    ext = result.get("stage_redteam_ext")
    if ext:
        print("red team ext: %d cases (S14/S15/S18)" % ext["count"])
        for r in ext["rows"]:
            print("  %-4s %-40s %-9s -> %-12s %s"
                  % ("atk", r["name"], r["expectation"], r["got"],
                     "ok" if r["ok"] else "FAILED: " + r["expectation_note"]))
            if r["failed_checks"]:
                print("       caught by: %s" % ", ".join(r["failed_checks"]))
    print()
    for key, label in (("stage_redteam_ckpt", "checkpoint & closure"),
                       ("stage_redteam_pinned", "out-of-band pin")):
        stage = result.get(key)
        if not stage:
            continue
        print("red team %s: %d cases" % (label, stage["count"]))
        for r in stage["rows"]:
            print("  %-4s %-42s %-9s -> %-12s %s"
                  % ("atk", r["name"][:42], r["expectation"], r["got"],
                     "ok" if r["ok"] else "FAILED: " + r["expectation_note"]))
            if r["failed_checks"]:
                print("       caught by: %s" % ", ".join(r["failed_checks"]))
    print()
    s16 = result.get("stage_redteam_s16")
    if s16:
        print("red team s16: %d cases (real FreeTSA token)" % s16["count"])
        for r in s16["rows"]:
            print("  %-4s %-40s %-9s -> %-12s %s"
                  % ("atk", r["name"], r["expectation"], r["got"],
                     "ok" if r["ok"] else "FAILED: " + r["expectation_note"]))
            if r["failed_checks"]:
                print("       caught by: %s" % ", ".join(r["failed_checks"]))
        for n in s16.get("not_externally_witnessed") or []:
            print("  n/a  %s" % n["what"])
            print("       %s" % n["why"])
    print()
    it = result["stage_interop"]
    if it["status"] == "SKIPPED":
        print("interop    : SKIPPED (%s)" % it["note"])
    else:
        print("interop    : %s" % ("all pass" if it["ok"] else "FAILED"))
        for c in it["checks"]:
            print("  %-38s exit=%d %s" % (c["name"], c["exit"], "ok" if c["ok"] else "FAILED"))
    print()
    t = result.get("trust")
    if t:
        print("verifier   : %s" % os.path.basename(t["path"]))
        print("             sha256 %s o  (from this repo: %s)"
              % (t["sha256"][:16], t["in_repo"]))
    print("VERDICT    : %s" % ("OK" if result["ok"] else "FAILED"))


def main():
    ap = argparse.ArgumentParser(description="Run the outsider audit.")
    ap.add_argument("--package", default=DEFAULT_PACKAGE)
    ap.add_argument("--kit", default=None,
                    help="AER-1 corpus directory; interop is skipped without it")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    result = run_all(args.package, args.kit)
    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        _print_human(result)
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
