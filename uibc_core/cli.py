"""uibc CLI (archive SS23): init / register / event / evidence / submit / verify / inspect."""

import argparse
import itertools
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone

import hashlib
from . import locking
from . import ed25519 as _ed
from .canonical import evidence_root, hash_file
from .signing import (ALGORITHM, ALGORITHM_ED25519, ed_generate_seed,
                      ed_key_id, ed_public_key, ed_seal_sign, generate_key,
                      key_id, seal_sign)
from .verify import verify
from . import verify as verify_mod
from . import lifecycle
from . import did as did_mod
from . import SPEC_VERSION, __version__

REQUIRED = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]


def _now() -> str:
    """The time a package records.

    A wall clock makes a package irreproducible: re-running the same commands
    produces different bytes, so nobody else can check the published corpus by
    rebuilding it. `SOURCE_DATE_EPOCH` (the reproducible-builds convention, in
    seconds) pins the clock instead. Unset, this is the ordinary wall clock and
    nothing about the format changes.
    """
    epoch = os.environ.get("SOURCE_DATE_EPOCH")
    if epoch:
        try:
            stamp = datetime.fromtimestamp(int(epoch), timezone.utc)
        except (TypeError, ValueError, OSError) as exc:
            raise SystemExit(f"error: SOURCE_DATE_EPOCH={epoch!r} is not a unix timestamp: {exc}")
        return stamp.strftime("%Y-%m-%dT%H:%M:%SZ")
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


_repro_counter = itertools.count()


def _uuid() -> str:
    """An identifier a rebuild reproduces.

    Unset `UIBC_REPRO_SEED`, this is uuid4, as it always was. Set, the nth id a
    process asks for is uuid5 of the seed and n - so a second run asking in the
    same order gets the same ids. They stay unique inside a package because the
    counter never repeats; what they stop being is unpredictable.
    """
    seed = os.environ.get("UIBC_REPRO_SEED")
    if not seed:
        return str(uuid.uuid4())
    return str(uuid.uuid5(uuid.NAMESPACE_URL, "%s/%d" % (seed, next(_repro_counter))))


def _write(path, obj):
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def cmd_init(args):
    pkg = os.path.abspath(args.path)
    if os.path.exists(pkg):
        sys.exit(f"error: {pkg} already exists")
    os.makedirs(os.path.join(pkg, "evidence", "files"), exist_ok=True)
    for f in REQUIRED:
        _write(os.path.join(pkg, f), {"_note": f"TODO: run 'uibc register' / add evidence", "schema": SPEC_VERSION})
    _write(os.path.join(pkg, "evidence", "index.json"), {"entries": []})
    print(f"initialized package skeleton at {pkg}")
    print(f"next: uibc register {pkg} --agent-id <id> --owner <owner>")


MAX_AGENT_ID_LENGTH = 128

# Characters that make two different identifiers look the same, or take an
# identifier somewhere other than where it is displayed. Measured 2026-11-24
# (harness s07, G3): `register` accepted the empty string, a control character
# and a bidi override as agent ids, each of which then became the actor name in
# a signed lifecycle event.
_BIDI_CONTROLS = frozenset("\u200e\u200f\u202a\u202b\u202c\u202d\u202e"
                           "\u2066\u2067\u2068\u2069\ufeff")


def agent_id_error(agent_id):
    """Return a reason the id is unusable, or None.

    An identifier is written into identity.json, manifest.json and the first
    lifecycle event, and it is what a verifier compares against. A value that is
    invisible, empty or renders as a different string is not a stricter check
    that is missing -- it is a different object being named.
    """
    if not isinstance(agent_id, str):
        return "agent id must be a string, got %r" % (type(agent_id).__name__,)
    if not agent_id:
        return "agent id must not be empty"
    if len(agent_id) > MAX_AGENT_ID_LENGTH:
        return "agent id is %d characters, limit is %d" % (len(agent_id), MAX_AGENT_ID_LENGTH)
    for ch in agent_id:
        if ord(ch) < 0x20 or ord(ch) == 0x7f:
            return "agent id contains a control character U+%04X" % ord(ch)
        if 0x7f < ord(ch) < 0xa0:
            return "agent id contains a control character U+%04X" % ord(ch)
        if ch in _BIDI_CONTROLS:
            return "agent id contains a bidirection control U+%04X" % ord(ch)
        if ch.isspace() and ch != " ":
            return "agent id contains whitespace U+%04X" % ord(ch)
    if agent_id != agent_id.strip() or "  " in agent_id:
        return "agent id has leading, trailing or repeated spaces"
    return None


def cmd_register(args):
    pkg = os.path.abspath(args.path)
    agent_id = args.agent_id
    reason = agent_id_error(agent_id)
    if reason:
        raise SystemExit("error: %s" % reason)
    now = _now()
    reg_event = {
        "event_id": _uuid(),
        "sequence_number": 0,      # v1.1: contiguous from 0; a gap is a
                                   # suppression indicator (GAR -08 6.2)
        "event_type": "REGISTER",
        "agent_id": agent_id,
        "timestamp": now,
        "actor": args.owner,
        "payload_hash": None,
        "previous_event": None,
        "signature": None,   # signing not ratified in v0.1
    }
    # A DID that cannot be independently resolved is worse than no DID at all:
    # it looks like a claim about control that nobody can check. Refuse at
    # write time rather than let a typo become a verification failure later.
    if getattr(args, "did", None):
        method, _ = did_mod.parse(args.did)
        from . import did_cn
        if method not in did_mod.SUPPORTED_METHODS and method not in did_cn.METHODS:
            raise SystemExit(
                "error: did:%s has no public resolution rule in this build "
                "(supported: %s)"
                % (method, ", ".join(
                    "did:" + m for m in did_mod.SUPPORTED_METHODS + did_cn.METHODS)))
        if method in did_cn.METHODS:
            lvl = did_cn.level(args.did)
            if lvl != "registry":
                raise SystemExit(
                    "error: did:%s is validated but publishes no resolution channel "
                    "we can re-run (%s), so binding an identity to it would prove "
                    "nothing a third party can check. Bind did:key / did:web, or one "
                    "of did:cn / did:ioa / did:cndid / did:cndomain with --did-endpoint"
                    % (method, did_cn.SPECS[method][1]))
            if not getattr(args, "did_endpoint", None):
                raise SystemExit(
                    "error: did:%s resolves through a registry; pass --did-endpoint "
                    "<registry base url> (spec: %s)"
                    % (method, did_cn.SPECS[method][1]))
            # Write-time proof: a DID we cannot resolve here is a claim, not a
            # binding. Resolve now, so a typo fails at register, not at verify.
            try:
                did_mod.resolve(args.did, endpoint=args.did_endpoint)
            except (did_mod.DIDError, OSError, ValueError) as exc:
                raise SystemExit("error: cannot resolve %s: %s" % (args.did, exc))
    ident = {
        "schema": SPEC_VERSION,
        "agent_id": agent_id,
        "agent_type": args.agent_type,
        "owner": args.owner,
        "created_at": now,
        "status": "REGISTERED",
        "version": args.version,
    }
    # v1.1 optional fields, only written when supplied, so older packages
    # stay readable and unchanged.
    for field in ("principal_type", "logical_agent_id", "run_id", "key_custody",
                  "did"):
        value = getattr(args, field, None)
        if value:
            ident[field] = value
    # The manifest is what S2 and S5 read. `register` used to write only
    # identity and lifecycle, so a freshly built package verified S2=FAIL and
    # S5=FAIL while printing "registered agent ..." -- measured, and hidden by
    # every test that ran against a finished fixture. Write it here, under the
    # package lock, with the root the empty index actually has.
    with locking.package_lock(pkg):
        index = _read(os.path.join(pkg, "evidence", "index.json"))
        entries = index["entries"] if isinstance(index, dict) else index
        content_hashes = [e["content_hash"] for e in entries]
        manifest = {
            "schema": SPEC_VERSION,
            "agent_id": agent_id,
            "agent_version": args.version,
            "created_at": now,
            "evidence_count": len(entries),
            "evidence_root": evidence_root(content_hashes),
            "status": "REGISTERED",
        }
        _write(os.path.join(pkg, "identity.json"), ident)
        _write(os.path.join(pkg, "lifecycle.json"), {"schema": SPEC_VERSION, "events": [reg_event]})
        locking.atomic_write_json(os.path.join(pkg, "manifest.json"), manifest)
    print(f"registered agent '{agent_id}' (owner: {args.owner}) at {now}")


def cmd_event(args):
    pkg = os.path.abspath(args.path)
    lc = _read(os.path.join(pkg, "lifecycle.json"))
    events = lc["events"]
    # v1.1: default the actor to the identity owner instead of the literal
    # string "owner" - the verifier now checks actors against the recorded
    # principal set (L10), so a meaningless placeholder would be rejected.
    actor = args.actor
    if actor is None:
        identity = _read(os.path.join(pkg, "identity.json"))
        actor = identity.get("owner") or events[0].get("agent_id")
    events.append({
        "event_id": _uuid(),
        "sequence_number": len(events),
        "event_type": args.type,
        "agent_id": events[0]["agent_id"],
        "timestamp": _now(),
        "actor": actor,
        "payload_hash": None,
        "previous_event": events[-1]["event_id"],
        "signature": None,
    })
    _write(os.path.join(pkg, "lifecycle.json"), lc)
    print(f"appended event {args.type} ({events[-1]['event_id']})")


def cmd_evidence(args):
    pkg = os.path.abspath(args.path)
    src = os.path.abspath(args.file)
    if not os.path.isfile(src):
        sys.exit(f"error: file not found: {src}")
    # Read, copy, append and write as one critical section. Without this,
    # two concurrent records both read the same index and the later write
    # silently discards the earlier entry -- measured: 200 calls, 28 entries,
    # 69 decode errors, package no longer verifies. See docs/CONCURRENCY.md.
    with locking.package_lock(pkg):
        idx = _read(os.path.join(pkg, "evidence", "index.json"))
        entries = idx["entries"] if isinstance(idx, dict) else idx
        fname = os.path.basename(src)
        rel = os.path.join("files", fname)
        dst = os.path.join(pkg, "evidence", rel)
        while os.path.exists(dst):
            fname = f"{_uuid()[:8]}_{fname}"
            rel = os.path.join("files", fname)
            dst = os.path.join(pkg, "evidence", rel)
        shutil.copy2(src, dst)
        entries.append({
            "evidence_id": _uuid(),
            "type": args.type,
            "path": rel.replace("\\", "/"),
            "content_hash": hash_file(dst),
            "created_at": _now(),
            "media_type": args.media_type,
            "note": args.note or "",
        })
        if isinstance(idx, dict):
            idx["entries"] = entries
            locking.atomic_write_json(os.path.join(pkg, "evidence", "index.json"), idx)
        else:
            locking.atomic_write_json(os.path.join(pkg, "evidence", "index.json"), entries)
    print(f"evidence added: {args.type} {rel} (hash recorded)")


def _load_key(path):
    """Load a seal key from a hex text file (owner secret, never in package)."""
    if not os.path.isfile(path):
        sys.exit(f"error: key file not found: {path}")
    with open(path, "r", encoding="ascii") as f:
        raw = f.read().strip()
    try:
        return bytes.fromhex(raw)
    except ValueError:
        sys.exit(f"error: key file is not 64-char hex: {path}")


def _load_seal_key(path):
    """Load a seal key file: ("hmac", key) or ("ed25519", seed).

    HMAC files are the v0.2 bare 64-hex format; Ed25519 files start with
    "ed25519:" followed by the 64-hex seed (uibc keygen --ed25519).
    """
    if not os.path.isfile(path):
        sys.exit(f"error: key file not found: {path}")
    with open(path, "r", encoding="ascii") as f:
        raw = f.read().strip()
    if raw.startswith("ed25519:"):
        try:
            seed = bytes.fromhex(raw[len("ed25519:"):].strip())
        except ValueError:
            sys.exit(f"error: Ed25519 key file is not valid hex: {path}")
        if len(seed) != 32:
            sys.exit(f"error: Ed25519 seed must be 32 bytes: {path}")
        return "ed25519", seed
    return "hmac", _load_key(path)


def _pubkey_from_did(value, endpoint=None):
    """Resolve a DID to the Ed25519 key it publishes.

    This is the point of binding to a DID: the verifier checks the seal against
    the key the *DID* names, instead of being handed a key out of band and
    asked to trust whoever handed it over. `endpoint` is the registry base URL
    for the China-registry methods; it has no default on purpose.
    """
    try:
        public_key, _kid = did_mod.resolve_ed25519_key(value, endpoint=endpoint)
    except (did_mod.DIDError, OSError, ValueError) as exc:
        sys.exit("error: cannot resolve %s: %s" % (value, exc))
    return public_key


def _load_pubkey(path):
    """Load a pinned Ed25519 public key file (bare 64-hex of the key)."""
    if not os.path.isfile(path):
        sys.exit(f"error: pubkey file not found: {path}")
    with open(path, "r", encoding="ascii") as f:
        raw = f.read().strip()
    try:
        pub = bytes.fromhex(raw)
    except ValueError:
        sys.exit(f"error: pubkey file is not hex: {path}")
    if len(pub) != 32:
        sys.exit(f"error: Ed25519 public key must be 32 bytes: {path}")
    return pub


def cmd_keygen(args):
    out = os.path.abspath(args.out)
    if os.path.exists(out):
        sys.exit(f"error: {out} already exists (refusing to overwrite a key)")
    if getattr(args, "ed25519", False):
        seed = ed_generate_seed()
        with open(out, "w", encoding="ascii") as f:
            f.write("ed25519:" + seed.hex())
        pub = ed_public_key(seed)
        with open(out + ".pub", "w", encoding="ascii") as f:
            f.write(pub.hex())
        print(f"Ed25519 seal key written to {out}")
        print(f"public key written to {out}.pub")
        print(f"key_id (of the public key, safe to share): {ed_key_id(pub)}")
        print("keep the seed file secret - anyone holding it can sign as you; "
              "the .pub file is for verifiers and is safe to publish")
        return
    key = generate_key()
    with open(out, "w", encoding="ascii") as f:
        f.write(key.hex())
    print(f"seal key written to {out}")
    print(f"key_id (public, safe to share): {key_id(key)}")
    print("keep this file secret - anyone holding it can sign packages as you")


def cmd_submit(args):
    pkg = os.path.abspath(args.path)
    identity = _read(os.path.join(pkg, "identity.json"))
    if "_note" in identity and identity.get("agent_id") is None:
        sys.exit("error: package not registered yet. run: "
                 f"uibc register {args.path} --agent-id <id> --owner <owner>")
    idx = _read(os.path.join(pkg, "evidence", "index.json"))
    hashes = []
    for e in idx["entries"]:
        hashes.append(hash_file(os.path.join(pkg, "evidence", e["path"])))
    from .canonical import (checkpoint_head, evidence_root, index_metadata_digest,
                       lifecycle_head)
    root = evidence_root(hashes)
    manifest = {
        "schema": SPEC_VERSION,
        "agent_id": identity["agent_id"],
        "agent_version": identity.get("version"),
        "created_at": _now(),
        "evidence_count": len(idx["entries"]),
        "evidence_root": root,
        "status": "SUBMITTED",
    }
    # v1.1: optional policy identity. Maps to noa-00's reserved policyHash and
    # to GAR -08's cap_profile_hash, so one field serves both alignments.
    if getattr(args, "policy_hash", None):
        manifest["policy_hash"] = args.policy_hash
    # v1.1: bind the evidence INDEX METADATA, not just the file contents.
    # Without this, an entry's type/note/action_digest could be rewritten while
    # every content hash still matched and every check still passed (the gap
    # this repo's own mutation benchmark missed until M19 was added).
    manifest["evidence_index_digest"] = index_metadata_digest(idx)
    # v1.1: head commitment over the lifecycle log, so a silently shortened log
    # is visible even when the package is unsigned, and so a verifier can pin
    # the head out-of-band to catch whole-package rollback (check S9).
    lc_events = _read(os.path.join(pkg, "lifecycle.json")).get("events", [])
    lc_head = lifecycle_head(lc_events)
    manifest["lifecycle_head"] = lc_head
    manifest["checkpoint_head"] = checkpoint_head(
        lc_head, root, manifest["evidence_index_digest"], len(idx["entries"]))
    # Version floor (VERSIONING.md section 8): record the minimum verifier
    # version able to judge everything this builder wrote. Without it a consumer
    # cannot tell whether the PASS it just received came from a verifier that
    # could see all the fields in the package - 0.3.3 certified a key_custody
    # claim it never read (MIGRATION-RESULTS.md, M2c).
    from . import __version__ as _builder_version
    manifest["min_verifier_version"] = _builder_version
    # Format v2 declares what v1 left implicit: from v2 on, everything under
    # evidence/ is either promised by evidence/index.json or structural by the
    # format, and anything else fails S1 by default. v1 packages (no field) keep
    # the note-plus-warning behaviour, so a package sealed before this change is
    # judged by the rules that were in force when it was sealed. The number is
    # positive evidence from the producer, not a floor the verifier infers: a
    # verifier that guessed "this looks v2" would be tightening somebody else's
    # package on its own initiative (ERM family M06).
    manifest["format_version"] = 2
    # Optional: carry the verifier inside the package, so an archive can be
    # checked with nothing but Python - parity with AIVS, which ships verify.py
    # in the bundle. The builder records path + hash; verify.py binds it in S1,
    # so an embedded verifier cannot be swapped for one that always says PASS.
    embedded_src = getattr(args, "embed_verifier", None)
    if embedded_src:
        src = os.path.abspath(embedded_src)
        if not os.path.isfile(src):
            sys.exit(f"error: embedded verifier not found: {embedded_src}")
        dst_dir = os.path.join(pkg, "verify")
        os.makedirs(dst_dir, exist_ok=True)
        dst = os.path.join(dst_dir, "uibc_verify.py")
        shutil.copyfile(src, dst)
        manifest["embedded_verifier"] = {
            "path": "verify/uibc_verify.py",
            "sha256": hash_file(dst),
            "built_by_verifier_version": _builder_version,
            "note": "outside the evidence root; hash-bound by check S1",
        }
    _write(os.path.join(pkg, "manifest.json"), manifest)
    msg = f"submission sealed: agent={identity['agent_id']} evidence={len(idx['entries'])} root={root}"
    if getattr(args, "key", None):
        kind, secret = _load_seal_key(args.key)
        sig_dir = os.path.join(pkg, "signatures")
        os.makedirs(sig_dir, exist_ok=True)
        # v1.1: fold the lifecycle log into the signed payload so event
        # timestamps / actors / appended events cannot be rewritten without
        # breaking the seal (see tools/mutation_benchmark.py).
        lc_path = os.path.join(pkg, "lifecycle.json")
        lifecycle_payload = _read(lc_path) if os.path.isfile(lc_path) else None
        signed_label = ("identity+manifest+lifecycle" if lifecycle_payload is not None
                        else "identity+manifest")
        if kind == "ed25519":
            sig, pub_b64 = ed_seal_sign(secret, identity, manifest, lifecycle_payload)
            pub = ed_public_key(secret)
            _write(os.path.join(sig_dir, "seal.json"), {
                "schema": SPEC_VERSION,
                "algorithm": ALGORITHM_ED25519,
                "key_id": ed_key_id(pub),
                "public_key": pub_b64,
                "signed": signed_label,
                "signature": sig,
                "created_at": _now(),
            })
            msg += " | Ed25519 seal signed (key_id %s...; third-party verifiable)" % ed_key_id(pub)[:16]
        else:
            _write(os.path.join(sig_dir, "seal.json"), {
                "schema": SPEC_VERSION,
                "algorithm": ALGORITHM,
                "key_id": key_id(secret),
                "signed": signed_label,
                "signature": seal_sign(secret, identity, manifest, lifecycle_payload),
                "created_at": _now(),
            })
            msg += " | seal signed (key_id %s...)" % key_id(secret)[:16]
    print(msg)


def cmd_demo(args):
    """One-command end-to-end demo (v0.3): build -> public seal -> a stranger
    verifies -> tamper -> catch -> forge-and-reseal -> pinning catches it."""
    import tempfile
    from .verify import verify as _verify

    base = tempfile.mkdtemp(prefix="uibc-demo-")
    pkg = os.path.join(base, "demo")
    key_file = os.path.join(base, "owner.key")

    def _step(n, text):
        print(f"[{n}/8] {text}")

    _step(1, "init package")
    cmd_init(type("A", (), {"path": pkg})())
    _step(2, "register agent (Registry)")
    cmd_register(type("A", (), {"path": pkg, "agent_id": "demo-agent",
                                "owner": "alice", "agent_type": "software-agent",
                                "version": "0.1.0"})())
    ev = os.path.join(base, "report.txt")
    with open(ev, "w", encoding="utf-8", newline="\n") as f:
        f.write("demo evidence: agent action log\n")
    _step(3, "add evidence (Evidence)")
    cmd_evidence(type("A", (), {"path": pkg, "type": "ACTION", "file": ev,
                                "media_type": "text/plain", "note": ""})())
    _step(4, "generate an Ed25519 seal key + seal the package (Gates)")
    cmd_keygen(type("A", (), {"out": key_file, "ed25519": True})())
    cmd_submit(type("A", (), {"path": pkg, "key": key_file})())
    _step(5, "a STRANGER verifies - no key, no permission, public seal only")
    r = _verify(pkg)
    print(f"     -> result: {r['result']} (expected PASS; assurance: {r['assurance']})")
    _step(6, "tamper with the evidence behind the owner's back")
    ev_files = os.path.join(pkg, "evidence", "files")
    with open(os.path.join(ev_files, os.listdir(ev_files)[0]), "a",
              encoding="utf-8", newline="\n") as f:
        f.write("forged line added by attacker\n")
    r = _verify(pkg)
    print(f"     -> result: {r['result']} (expected FAIL: tampered content)")
    _step(7, "stronger attack: recompute every hash and re-seal with the "
             "attacker's OWN key, then verify unpinned")
    forge = os.path.join(base, "forged")
    shutil.copytree(pkg, forge)
    idx = _read(os.path.join(forge, "evidence", "index.json"))
    for e in idx["entries"]:
        e["content_hash"] = hash_file(os.path.join(forge, "evidence", e["path"]))
    _write(os.path.join(forge, "evidence", "index.json"), idx)
    from .canonical import (checkpoint_head, evidence_root, index_metadata_digest,
                       lifecycle_head)
    man = _read(os.path.join(forge, "manifest.json"))
    man["evidence_root"] = evidence_root([e["content_hash"] for e in idx["entries"]])
    _write(os.path.join(forge, "manifest.json"), man)
    atk_key = os.path.join(base, "attacker.key")
    cmd_keygen(type("A", (), {"out": atk_key, "ed25519": True})())
    cmd_submit(type("A", (), {"path": forge, "key": atk_key})())
    r = _verify(forge)
    print(f"     -> result: {r['result']} (the attacker's seal is valid against the "
          "attacker's key - a substituted key verifies against itself)")
    _step(8, "verify the same package PINNED to the owner's public key")
    r = _verify(forge, pubkey=_load_pubkey(key_file + ".pub"))
    print(f"     -> result: {r['result']} (expected FAIL: key substitution caught "
          "by pinning - publish your .pub where verifiers can pin it)")
    print("Try it yourself: python -m uibc_core.cli verify "
          + pkg + "   (no key needed - the seal is public)")
    print("                 python -m uibc_core.cli verify "
          + forge + " --pubkey " + key_file + ".pub")


def cmd_cert_issue(args):
    from .certificate import issue_certificate
    pkg = os.path.abspath(args.path)
    key = _load_key(args.key)
    identity = _read(os.path.join(pkg, "identity.json"))
    manifest = _read(os.path.join(pkg, "manifest.json"))
    expires_at = None
    if args.expires_days:
        import datetime
        expires_at = (datetime.datetime.now(datetime.timezone.utc)
                      + datetime.timedelta(days=args.expires_days))\
            .strftime("%Y-%m-%dT%H:%M:%SZ")
    cert = issue_certificate(key, identity, manifest, expires_at=expires_at)
    out = os.path.abspath(args.out) if args.out else pkg + ".cert.json"
    if os.path.exists(out):
        sys.exit(f"error: {out} already exists (refusing to overwrite a certificate)")
    _write(out, cert)
    print(f"certificate issued: {cert['certificate_id']} "
          f"subject={cert['subject_agent']} root={cert['evidence_root'][:16]}...")
    print(f"written to {out}")


def cmd_cert_verify(args):
    from .certificate import verify_certificate
    key = _load_key(args.key)
    cert = _read(os.path.abspath(args.cert))
    pkg = os.path.abspath(args.package) if args.package else None
    report = verify_certificate(key, cert, package_dir=pkg)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(0 if report["result"] == "PASS" else 1)


def cmd_revoke(args):
    """Write a signed revocation.json.

    The point of signing this file is to let somebody who never held the owner's
    secret decide whether the owner really voided the package. With an Ed25519
    seed the revocation is verifiable by any third party who has the public key;
    with an HMAC key only the owner can check it, and the gate will HOLD for
    everybody else - so the file says which one it is, and so does the gate.
    """
    import base64
    import hashlib
    import hmac
    import json
    import time as _time

    from .gate import _canonical_sig_payload

    pkg = os.path.abspath(args.path)
    man_path = os.path.join(pkg, "manifest.json")
    if not os.path.isfile(man_path):
        sys.exit(f"error: manifest.json not found in {pkg}")
    with open(man_path, encoding="utf-8") as f:
        manifest = json.load(f)
    root = manifest.get("evidence_root")
    if not root:
        sys.exit("error: manifest has no evidence_root; nothing to revoke")

    kind, secret = _load_seal_key(args.key)
    body = {
        "revocation_id": args.id or ("r-" + hashlib.sha256(
            (root + _time.strftime("%Y%m%d%H%M%S", _time.gmtime())).encode()
        ).hexdigest()[:16]),
        "target_root": root,
        "reason_code": args.reason_code,
        "revoked_at": _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime()),
    }
    # Everything except `signature` is signed - including algorithm and key_id.
    # Signing a subset and adding fields afterwards is how a valid signature
    # ends up failing verification (measured: first implementation signed only
    # the four base fields and the gate, which strips only `signature`, could
    # not reproduce the bytes).
    if kind == "ed25519":
        body["algorithm"] = "Ed25519"
        body["key_id"] = ed_key_id(_ed.publickey(secret))
        payload = _canonical_sig_payload(body)
        body["signature"] = base64.b64encode(_ed.sign(secret, payload)).decode("ascii")
    else:
        body["algorithm"] = "HMAC-SHA256"
        body["key_id"] = key_id(secret)
        payload = _canonical_sig_payload(body)
        body["signature"] = base64.b64encode(
            hmac.new(secret, payload, hashlib.sha256).digest()).decode("ascii")

    out = os.path.abspath(args.out)
    if os.path.exists(out):
        sys.exit(f"error: {out} already exists (refusing to overwrite a revocation)")
    with open(out, "w", encoding="utf-8", newline="\n") as f:
        json.dump(body, f, indent=2, sort_keys=True)
        f.write("\n")
    print(json.dumps({"written": out, "algorithm": body["algorithm"],
                      "target_root": root, "revocation_id": body["revocation_id"],
                      "key_id": body["key_id"]}, indent=2))


def cmd_gate(args):
    from .gate import gate
    pkg = os.path.abspath(args.path)
    if not os.path.isdir(pkg):
        sys.exit(f"error: package dir not found: {pkg}")
    key = _load_key(args.key) if args.key else None
    pubkey = _load_pubkey(args.pubkey) if getattr(args, "pubkey", None) else None
    if getattr(args, "did", None):
        if pubkey is not None:
            sys.exit("error: --did and --pubkey both pin a key; pass one of them")
        pubkey = _pubkey_from_did(args.did, getattr(args, "did_endpoint", None))
    report = gate(pkg, key=key, pubkey=pubkey,
                  revocation_path=args.revocation, dispute_path=args.dispute,
                  require_revocation_coverage=getattr(
                      args, "require_revocation_coverage", False),
                  coverage_path=getattr(args, "coverage", None),
                  coverage_max_age_s=getattr(args, "coverage_max_age", None),
                  coverage_state_path=getattr(args, "coverage_state", None),
                  coverage_url=getattr(args, "coverage_url", None),
                  coverage_channel_timeout_s=getattr(
                      args, "coverage_channel_timeout", None))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(report["exit_code"])


def cmd_revocation_digest(args):
    """Print the canonical body digest a decision receipt pins.

    A reader handed `revocation.json` can recompute this with the same command
    the receipt was written with - one canonicalization, called by the signer,
    the gate and the reader, instead of three copies that drift apart (#319).
    """
    from .gate import revocation_body_sha256
    path = os.path.abspath(args.file)
    if not os.path.isfile(path):
        sys.exit(f"error: revocation file not found: {path}")
    with open(path, encoding="utf-8") as f:
        body = json.load(f)
    out = {k: body.get(k) for k in
           ("revocation_id", "target_root", "reason_code", "revoked_at",
            "algorithm", "key_id")}
    out["body_sha256"] = revocation_body_sha256(body)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))


REPORT_FORMAT = "uibc-verify-report/1"


def _now_utc():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _failed_checks(report):
    return sorted({str(c.get("id")) for c in (report or {}).get("checks", [])
                   if str(c.get("result", "")).upper() == "FAIL"})


def _report_line(vector, report, exit_code, error=None):
    """One line per package, in a shape another harness can read.

    Section 3.6 of the draft keeps the verdict and the checks apart, so the line
    carries both: a consumer that only wants pass/fail reads `result`, and a
    consumer that wants to know *why* reads `checks_failed`. The verifier identity
    travels with every line, because a report whose producer is not named is a
    claim without a claimant.
    """
    line = {
        "format": REPORT_FORMAT,
        "vector": vector,
        "result": (report or {}).get("result") if error is None else "ERROR",
        "checks_failed": [] if error else _failed_checks(report),
        "verifier_id": (report or {}).get("verifier_id"),
        "verifier_version": (report or {}).get("verifier_version"),
        "when_utc": _now_utc(),
        "exit": exit_code,
    }
    if error is not None:
        line["error"] = str(error)[:300]
    return line


def _append_line(path, line):
    # Append, never rewrite: a harness that runs many packages must be able to
    # collect them in one file, and a line already written must not be lost when
    # a later package fails. Explicit newline so the file does not change shape
    # depending on the operating system that produced it.
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps(line, ensure_ascii=False, sort_keys=True) + "\n")


def cmd_verify(args):
    pkg = os.path.abspath(args.path)
    rpt = getattr(args, "report", None)
    vid = getattr(args, "vector_id", None) or os.path.basename(pkg) or pkg

    def _report_and_exit(code, report=None, error=None):
        # A caller that asked for a report gets a line even when we could not
        # read the input. "No line" is the one answer a harness cannot tell
        # apart from "this vector was silently dropped" - and it is exactly what
        # a foreign rail reported as external-output-absent when it handed us
        # single-statement vectors instead of package directories.
        if rpt:
            _append_line(rpt, _report_line(vid, report, code, error=error))
        sys.exit(code)

    if not os.path.isdir(pkg):
        print(f"error: package dir not found: {pkg}", file=sys.stderr)
        _report_and_exit(3, error="package dir not found: %s" % pkg)
    key = _load_key(args.key) if args.key else None
    pubkey = _load_pubkey(args.pubkey) if getattr(args, "pubkey", None) else None
    # A DID pins the key as a file would -- but the key travels with the DID
    # rather than with the message, so a third party needs nothing from us.
    if getattr(args, "did", None):
        if pubkey is not None:
            sys.exit("error: --did and --pubkey both pin a key; pass one of them")
        pubkey = _pubkey_from_did(args.did, getattr(args, "did_endpoint", None))
    try:
        report = verify(pkg, key=key, pubkey=pubkey,
                        expect_head=getattr(args, "expect_head", None),
                        strict=getattr(args, "strict", False),
                        state_file=getattr(args, "state_file", None))
    except SystemExit:
        raise
    except Exception as exc:                        # a package we cannot even read
        print(f"error: {exc}", file=sys.stderr)
        _report_and_exit(3, error=exc)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # Warnings are not failures, so they must not go into stdout and confuse a
    # parser -- but a PASS that ignored unjudged files must be visible to a
    # human reading the console. A machine caller gates on report["warnings"].
    for w in report.get("warnings", []):
        print(f"warning [{w['code']}]: {w['detail']}", file=sys.stderr)
    code = 0 if report["result"] == "PASS" else 1
    if rpt:
        _append_line(rpt, _report_line(vid, report, code))
    sys.exit(code)


def cmd_verify_dir(args):
    """Verify every immediate subdirectory, one report line per package.

    This is the shape a foreign harness needs: it hands over a directory whose
    children are its own vectors and gets back one line per vector, each naming
    the verifier that judged it. Nothing here assumes our case names.

    An empty directory is not a success: it exits 3 and writes no report, because
    "no packages were judged" must never read the same as "all packages passed".
    """
    root = os.path.abspath(args.dir)
    if not os.path.isdir(root):
        sys.exit(f"error: directory not found: {root}")
    names = sorted(d for d in os.listdir(root) if os.path.isdir(os.path.join(root, d)))
    if not names:
        print(f"error: no packages under {root}", file=sys.stderr)
        sys.exit(3)
    key = _load_key(args.key) if getattr(args, "key", None) else None
    pubkey = _load_pubkey(args.pubkey) if getattr(args, "pubkey", None) else None
    failed = []
    for name in names:
        pkg = os.path.join(root, name)
        try:
            report = verify(pkg, key=key, pubkey=pubkey,
                            strict=getattr(args, "strict", False))
        except Exception as exc:                      # a package we cannot even read
            line = _report_line(name, None, 3, error=exc)
            if getattr(args, "report", None):
                _append_line(args.report, line)
            failed.append(name)
            print(f"{name}: ERROR {str(exc)[:120]}", file=sys.stderr)
            continue
        code = 0 if report["result"] == "PASS" else 1
        if getattr(args, "report", None):
            _append_line(args.report, _report_line(name, report, code))
        if code:
            failed.append(name)
            print(f"{name}: {report['result']} failed {_failed_checks(report)}",
                  file=sys.stderr)
    print(f"{len(names) - len(failed)}/{len(names)} packages PASS")
    sys.exit(0 if not failed else 1)



def cmd_explain(args):
    """The same verifier, printed for a person.

    `verify` emits JSON because scripts parse it. A JSON verdict is a poor way
    to read a failure: the field that matters (`checks[].basis.citation`) sits
    four levels down. This prints one line per check with its class and - where
    one exists - the document that lets the rule claim anything at all.
    """
    from .basis import CLASS_LABEL
    pkg = os.path.abspath(args.path)
    if not os.path.isdir(pkg):
        sys.exit(f"error: package dir not found: {pkg}")
    key = _load_key(args.key) if getattr(args, "key", None) else None
    pubkey = _load_pubkey(args.pubkey) if getattr(args, "pubkey", None) else None
    report = verify(pkg, key=key, pubkey=pubkey,
                    expect_head=getattr(args, "expect_head", None))
    print(f"result: {report['result']}   verifier: {report['verifier_id']} "
          f"{report['verifier_version']}")
    print()
    for c in report["checks"]:
        b = c.get("basis") or {}
        mark = "PASS" if c["result"] == "PASS" else c["result"]
        cite = b.get("citation") or ""
        src = ("[%s] %s" % (CLASS_LABEL.get(b.get("class", "none"), "无"), cite)
               if cite else
               "[%s] 本项目自定" % CLASS_LABEL.get(b.get("class", "none"), "无"))
        print(f"{c['id']:<4} {mark:<12} {c['name']}")
        print(f"     {src}")
        if mark != "PASS":
            print(f"     -> {c['detail']}")
    print()
    out = report.get("statement") or ""
    if out:
        print(out)
    sys.exit(0 if report["result"] == "PASS" else 1)


def cmd_inspect(args):
    pkg = os.path.abspath(args.path)
    manifest = _read(os.path.join(pkg, "manifest.json"))
    identity = _read(os.path.join(pkg, "identity.json"))
    lc = _read(os.path.join(pkg, "lifecycle.json"))
    idx = _read(os.path.join(pkg, "evidence", "index.json"))
    print(f"agent:      {identity.get('agent_id')} (owner {identity.get('owner')})")
    print(f"status:     {identity.get('status')} / manifest: {manifest.get('status')}")
    print(f"events:     {' -> '.join(e['event_type'] for e in lc.get('events', []))}")
    print(f"evidence:   {len(idx.get('entries', []))} entries")
    print(f"root:       {manifest.get('evidence_root')}")


def _utf8_stdout():
    """Every command's output is UTF-8 JSON or UTF-8 text.

    A Windows console defaults to cp1252, and `print(json.dumps(..., ensure_ascii=False))`
    then raises UnicodeEncodeError on the first non-ASCII detail - so `verify` dies
    with a traceback on stderr and prints nothing, on a package it could describe.
    Reconfiguring the stream keeps the bytes the same on every platform; a console
    that cannot render them shows boxes rather than a crash.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass


def main():
    _utf8_stdout()
    ap = argparse.ArgumentParser(prog="uibc", description="UIBC Core CLI v%s [PROPOSAL]" % __version__)
    # --version exists so a bundled single-file build can state which version it
    # is without importing the package: the conformance runner reads it to label
    # a receipt correctly (run.py, 2026-11-20).
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create submission package skeleton")
    p.add_argument("path"); p.set_defaults(func=cmd_init)

    p = sub.add_parser("register", help="register agent (writes identity + REGISTER event)")
    p.add_argument("path"); p.add_argument("--agent-id", required=True)
    p.add_argument("--owner", required=True); p.add_argument("--agent-type", default="software-agent")
    p.add_argument("--version", default="0.1.0")
    # v1.1 identity fields (noa-00 compatible principal vocabulary, and the
    # long-term-identity / single-run separation)
    p.add_argument("--principal-type", dest="principal_type", default=None,
                   choices=["HUMAN", "SERVICE", "POLICY", "SANDBOX_SIM"])
    p.add_argument("--logical-agent-id", dest="logical_agent_id", default=None)
    p.add_argument("--run-id", dest="run_id", default=None)
    # 1F916 Section 3.1: custody disclosure travels with the signature, because
    # a signature proves exactly what its custody permits it to prove.
    p.add_argument("--key-custody", dest="key_custody", default=None,
                   choices=["self_held", "platform_held", "household_held",
                            "threshold", "kms", "hsm", "session_delegated"])
    # Optional DID binding. Only methods whose resolution rule is public
    # (did:key / did:web) are accepted: binding an identity to a DID nobody
    # can independently resolve proves nothing about who controls it.
    p.add_argument("--did", default=None,
                   help="bind this identity to a DID (did:key or did:web; the "
                        "China-registry methods need --did-endpoint and are "
                        "resolved once, now, before the binding is written)")
    p.add_argument("--did-endpoint", dest="did_endpoint", default=None, metavar="URL",
                   help="registry base URL for did:cn / did:ioa / did:cndid / "
                        "did:cndomain. No default: the specs name registries, not "
                        "public resolution URLs")
    p.set_defaults(func=cmd_register)

    p = sub.add_parser("event", help="append lifecycle event")
    p.add_argument("path")
    # choices, not free text: the verifier's L3 rejects any event_type outside this
    # vocabulary with a FAIL. Accepting the word here and rejecting it there made a
    # typo look like a bad package, so the writer refuses it first (see docs/ORACLE.md).
    p.add_argument("--type", required=True, choices=lifecycle.EVENTS)
    p.add_argument("--actor", default=None)
    p.set_defaults(func=cmd_event)

    p = sub.add_parser("evidence", help="add evidence file (hash recorded)")
    p.add_argument("path"); p.add_argument("--file", required=True)
    # Same reason: an unknown evidence type makes S4 return INCONCLUSIVE, which reads
    # to a user as "the verifier could not decide" when the real problem is a word.
    p.add_argument("--type", required=True, choices=sorted(verify_mod.EVIDENCE_TYPES))
    p.add_argument("--media-type", default="text/plain"); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("submit", help="seal package (compute evidence_root into manifest)")
    p.add_argument("path")
    p.add_argument("--key", default=None, metavar="KEYFILE",
                   help="key file: write a seal signature (HMAC hex key, or an "
                        "ed25519: key file for a third-party-verifiable seal)")
    p.add_argument("--embed-verifier", dest="embed_verifier", default=None,
                   metavar="SCRIPT",
                   help="copy a single-file verifier into the package as "
                        "verify/uibc_verify.py and bind its hash in the manifest, "
                        "so the package can be checked without this repository")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("verify", help="verify package (exit 0 = PASS)")
    p.add_argument("path")
    p.add_argument("--key", default=None, metavar="KEYFILE",
                   help="hex owner key: strict mode - unsigned/mismatched seal FAILS (S6)")
    p.add_argument("--pubkey", default=None, metavar="PUBFILE",
                   help="pinned Ed25519 public key (hex file): the seal's recorded "
                        "public key must match it, else S6 FAILS")
    p.add_argument("--did", default=None, metavar="DID",
                   help="pin the key by DID instead of a file (did:key resolves "
                        "offline; did:web over https; did:cn / did:ioa / did:cndid "
                        "/ did:cndomain with --did-endpoint)")
    p.add_argument("--did-endpoint", dest="did_endpoint", default=None, metavar="URL",
                   help="registry base URL for the China-registry DID methods")
    p.add_argument("--expect-head", dest="expect_head", default=None, metavar="HEAD",
                   help="pin the package checkpoint_head observed elsewhere: a "
                        "mismatch FAILS S9, which is the only way to catch a rollback "
                        "to an older but self-consistent package")
    p.add_argument("--strict", action="store_true",
                   help="fail any file under evidence/ that the index never declared "
                        "(the structural members the format places there are exempt)")
    p.add_argument("--state-file", dest="state_file", default=None, metavar="JSON",
                   help="remember the last accepted head here (S19). Compared on the "
                        "next run, so a rollback is refused without the caller "
                        "supplying --expect-head every time. First observation is "
                        "INCONCLUSIVE, not PASS")
    p.add_argument("--report", default=None, metavar="JSONL",
                   help="append one JSON line describing this run, in a shape another "
                        "harness can read: vector, result, checks_failed, verifier "
                        "identity, exit code. Appending rather than rewriting lets a "
                        "caller collect many runs in one file")
    p.add_argument("--vector-id", dest="vector_id", default=None, metavar="ID",
                   help="name this package in the report line; default is its path")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("verify-dir", help="verify every immediate subdirectory, "
                                          "one report line per package")
    p.add_argument("dir")
    p.add_argument("--key", default=None, metavar="KEYFILE")
    p.add_argument("--pubkey", default=None, metavar="PUBFILE")
    p.add_argument("--strict", action="store_true")
    p.add_argument("--report", default=None, metavar="JSONL")
    p.set_defaults(func=cmd_verify_dir)

    p = sub.add_parser("explain", help="verify and print why, one check per line")
    p.add_argument("path")
    p.add_argument("--key", default=None, metavar="KEYFILE")
    p.add_argument("--pubkey", default=None, metavar="PUBFILE")
    p.add_argument("--expect-head", dest="expect_head", default=None, metavar="HEAD")
    p.set_defaults(func=cmd_explain)

    p = sub.add_parser("keygen", help="generate a 256-bit seal key (hex file)")
    p.add_argument("--out", required=True, metavar="KEYFILE")
    p.add_argument("--ed25519", action="store_true",
                   help="generate an Ed25519 seal key instead: writes an ed25519: "
                        "seed file plus a publishable .pub file (v0.3)")
    p.set_defaults(func=cmd_keygen)

    p = sub.add_parser("cert-issue", help="issue a certificate for a verified package")
    p.add_argument("path")
    p.add_argument("--key", required=True, metavar="KEYFILE")
    p.add_argument("--out", default=None, metavar="FILE")
    p.add_argument("--expires-days", type=int, default=None, metavar="N")
    p.set_defaults(func=cmd_cert_issue)

    p = sub.add_parser("cert-verify", help="verify a certificate (exit 0 = PASS)")
    p.add_argument("cert", metavar="CERTFILE")
    p.add_argument("--key", required=True, metavar="KEYFILE")
    p.add_argument("--package", default=None, metavar="PKG",
                   help="also check the certificate is bound to this package")
    p.set_defaults(func=cmd_cert_verify)

    p = sub.add_parser("gate", help="governed decision: ALLOW(0)/DENY(2)/HOLD(3)")
    p.add_argument("path")
    p.add_argument("--key", default=None, metavar="KEYFILE",
                   help="hex owner key: strict verify + revocation signature check")
    p.add_argument("--pubkey", default=None, metavar="PUBFILE",
                   help="pinned Ed25519 public key (hex file) for the verify step")
    p.add_argument("--did", default=None, metavar="DID",
                   help="pin the key by DID instead of a file (did:key / did:web; "
                        "China-registry methods need --did-endpoint)")
    p.add_argument("--did-endpoint", dest="did_endpoint", default=None, metavar="URL",
                   help="registry base URL for the China-registry DID methods")
    p.add_argument("--revocation", default=None, metavar="FILE",
                   help="revocation.json overlay (governance.md section 3)")
    p.add_argument("--dispute", default=None, metavar="FILE",
                   help="dispute.json overlay (governance.md section 1)")
    p.add_argument("--require-revocation-coverage", action="store_true",
                   help="fail-closed: with no --revocation overlay return HOLD(3) "
                        "instead of ALLOW(0) - absence is not a clean state")
    p.add_argument("--coverage", default=None, metavar="FILE",
                   help="signed revocation-coverage.json ('as of issued_at, no "
                        "revocation for this evidence_root')")
    p.add_argument("--coverage-max-age", default=None, type=float, metavar="SECONDS",
                   help="refuse a coverage statement older than this (HOLD, exit 3)")
    p.add_argument("--coverage-state", default=None, metavar="FILE",
                   help="remember the last accepted coverage sequence; a lower "
                        "sequence is refused as a rollback (HOLD, exit 3)")
    p.add_argument("--coverage-url", default=None, metavar="URL",
                   help="pull the coverage statement over HTTP instead of reading "
                        "a file; an unreachable feed is HOLD(3), never ALLOW(0)")
    p.add_argument("--coverage-channel-timeout", default=None, type=float,
                   metavar="SECONDS", help="per-GET timeout for --coverage-url")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("revoke", help="issue a revocation.json for a package (governance 3)")
    p.add_argument("path", help="package to revoke (reads its manifest evidence_root)")
    p.add_argument("--key", required=True, metavar="KEYFILE",
                   help="owner key: ed25519: seed file (asymmetric) or 64-hex (HMAC)")
    p.add_argument("--out", required=True, metavar="FILE", help="where to write revocation.json")
    p.add_argument("--reason-code", default="OWNER_REQUEST",
                   choices=["KEY_COMPROMISED", "EVIDENCE_INVALID", "OWNER_REQUEST"])
    p.add_argument("--id", default=None, metavar="REVOCATION_ID")
    p.set_defaults(func=cmd_revoke)

    p = sub.add_parser("revocation-digest",
                       help="canonical body digest of a revocation.json (what a receipt pins)")
    p.add_argument("file", metavar="FILE")
    p.set_defaults(func=cmd_revocation_digest)

    p = sub.add_parser("demo", help="one-command end-to-end demo (build/seal/verify/tamper/catch)")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("inspect", help="human-readable package summary")
    p.add_argument("path"); p.set_defaults(func=cmd_inspect)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

