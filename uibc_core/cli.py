"""uibc CLI (archive SS23): init / register / event / evidence / submit / verify / inspect."""

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone

from .canonical import hash_file
from .signing import (ALGORITHM, ALGORITHM_ED25519, ed_generate_seed,
                      ed_key_id, ed_public_key, ed_seal_sign, generate_key,
                      key_id, seal_sign)
from .verify import verify
from . import SPEC_VERSION, __version__

REQUIRED = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


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


def cmd_register(args):
    pkg = os.path.abspath(args.path)
    agent_id = args.agent_id
    now = _now()
    reg_event = {
        "event_id": str(uuid.uuid4()),
        "event_type": "REGISTER",
        "agent_id": agent_id,
        "timestamp": now,
        "actor": args.owner,
        "payload_hash": None,
        "previous_event": None,
        "signature": None,   # signing not ratified in v0.1
    }
    _write(os.path.join(pkg, "identity.json"), {
        "schema": SPEC_VERSION,
        "agent_id": agent_id,
        "agent_type": args.agent_type,
        "owner": args.owner,
        "created_at": now,
        "status": "REGISTERED",
        "version": args.version,
    })
    _write(os.path.join(pkg, "lifecycle.json"), {"schema": SPEC_VERSION, "events": [reg_event]})
    print(f"registered agent '{agent_id}' (owner: {args.owner}) at {now}")


def cmd_event(args):
    pkg = os.path.abspath(args.path)
    lc = _read(os.path.join(pkg, "lifecycle.json"))
    events = lc["events"]
    events.append({
        "event_id": str(uuid.uuid4()),
        "event_type": args.type,
        "agent_id": events[0]["agent_id"],
        "timestamp": _now(),
        "actor": args.actor,
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
    idx = _read(os.path.join(pkg, "evidence", "index.json"))
    fname = os.path.basename(src)
    rel = os.path.join("files", fname)
    dst = os.path.join(pkg, "evidence", rel)
    if os.path.exists(dst):
        fname = f"{uuid.uuid4().hex[:8]}_{fname}"
        rel = os.path.join("files", fname)
        dst = os.path.join(pkg, "evidence", rel)
    shutil.copy2(src, dst)
    idx["entries"].append({
        "evidence_id": str(uuid.uuid4()),
        "type": args.type,
        "path": rel.replace("\\", "/"),
        "content_hash": hash_file(dst),
        "created_at": _now(),
        "media_type": args.media_type,
        "note": args.note or "",
    })
    _write(os.path.join(pkg, "evidence", "index.json"), idx)
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
    from .canonical import evidence_root
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
    _write(os.path.join(pkg, "manifest.json"), manifest)
    msg = f"submission sealed: agent={identity['agent_id']} evidence={len(idx['entries'])} root={root}"
    if getattr(args, "key", None):
        kind, secret = _load_seal_key(args.key)
        sig_dir = os.path.join(pkg, "signatures")
        os.makedirs(sig_dir, exist_ok=True)
        if kind == "ed25519":
            sig, pub_b64 = ed_seal_sign(secret, identity, manifest)
            pub = ed_public_key(secret)
            _write(os.path.join(sig_dir, "seal.json"), {
                "schema": SPEC_VERSION,
                "algorithm": ALGORITHM_ED25519,
                "key_id": ed_key_id(pub),
                "public_key": pub_b64,
                "signed": "identity+manifest",
                "signature": sig,
                "created_at": _now(),
            })
            msg += " | Ed25519 seal signed (key_id %s...; third-party verifiable)" % ed_key_id(pub)[:16]
        else:
            _write(os.path.join(sig_dir, "seal.json"), {
                "schema": SPEC_VERSION,
                "algorithm": ALGORITHM,
                "key_id": key_id(secret),
                "signed": "identity+manifest",
                "signature": seal_sign(secret, identity, manifest),
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
    from .canonical import evidence_root
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


def cmd_gate(args):
    from .gate import gate
    pkg = os.path.abspath(args.path)
    if not os.path.isdir(pkg):
        sys.exit(f"error: package dir not found: {pkg}")
    key = _load_key(args.key) if args.key else None
    pubkey = _load_pubkey(args.pubkey) if getattr(args, "pubkey", None) else None
    report = gate(pkg, key=key, pubkey=pubkey,
                  revocation_path=args.revocation, dispute_path=args.dispute)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    sys.exit(report["exit_code"])


def cmd_verify(args):
    pkg = os.path.abspath(args.path)
    if not os.path.isdir(pkg):
        sys.exit(f"error: package dir not found: {pkg}")
    key = _load_key(args.key) if args.key else None
    pubkey = _load_pubkey(args.pubkey) if getattr(args, "pubkey", None) else None
    report = verify(pkg, key=key, pubkey=pubkey)
    print(json.dumps(report, ensure_ascii=False, indent=2))
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


def main():
    ap = argparse.ArgumentParser(prog="uibc", description="UIBC Core CLI v%s [PROPOSAL]" % __version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="create submission package skeleton")
    p.add_argument("path"); p.set_defaults(func=cmd_init)

    p = sub.add_parser("register", help="register agent (writes identity + REGISTER event)")
    p.add_argument("path"); p.add_argument("--agent-id", required=True)
    p.add_argument("--owner", required=True); p.add_argument("--agent-type", default="software-agent")
    p.add_argument("--version", default="0.1.0"); p.set_defaults(func=cmd_register)

    p = sub.add_parser("event", help="append lifecycle event")
    p.add_argument("path"); p.add_argument("--type", required=True); p.add_argument("--actor", default="owner")
    p.set_defaults(func=cmd_event)

    p = sub.add_parser("evidence", help="add evidence file (hash recorded)")
    p.add_argument("path"); p.add_argument("--type", required=True); p.add_argument("--file", required=True)
    p.add_argument("--media-type", default="text/plain"); p.add_argument("--note", default="")
    p.set_defaults(func=cmd_evidence)

    p = sub.add_parser("submit", help="seal package (compute evidence_root into manifest)")
    p.add_argument("path")
    p.add_argument("--key", default=None, metavar="KEYFILE",
                   help="key file: write a seal signature (HMAC hex key, or an "
                        "ed25519: key file for a third-party-verifiable seal)")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("verify", help="verify package (exit 0 = PASS)")
    p.add_argument("path")
    p.add_argument("--key", default=None, metavar="KEYFILE",
                   help="hex owner key: strict mode - unsigned/mismatched seal FAILS (S6)")
    p.add_argument("--pubkey", default=None, metavar="PUBFILE",
                   help="pinned Ed25519 public key (hex file): the seal's recorded "
                        "public key must match it, else S6 FAILS")
    p.set_defaults(func=cmd_verify)

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
    p.add_argument("--revocation", default=None, metavar="FILE",
                   help="revocation.json overlay (governance.md section 3)")
    p.add_argument("--dispute", default=None, metavar="FILE",
                   help="dispute.json overlay (governance.md section 1)")
    p.set_defaults(func=cmd_gate)

    p = sub.add_parser("demo", help="one-command end-to-end demo (build/seal/verify/tamper/catch)")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("inspect", help="human-readable package summary")
    p.add_argument("path"); p.set_defaults(func=cmd_inspect)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
