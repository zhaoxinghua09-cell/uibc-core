"""uibc CLI (archive SS23): init / register / event / evidence / submit / verify / inspect."""

import argparse
import json
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone

from .canonical import hash_file
from .signing import ALGORITHM, generate_key, key_id, seal_sign
from .verify import verify
from . import SPEC_VERSION, __version__

REQUIRED = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]


def _now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
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


def cmd_keygen(args):
    out = os.path.abspath(args.out)
    if os.path.exists(out):
        sys.exit(f"error: {out} already exists (refusing to overwrite a key)")
    key = generate_key()
    with open(out, "w", encoding="ascii") as f:
        f.write(key.hex())
    print(f"seal key written to {out}")
    print(f"key_id (public, safe to share): {key_id(key)}")
    print("keep this file secret - anyone holding it can sign packages as you")


def cmd_submit(args):
    pkg = os.path.abspath(args.path)
    identity = _read(os.path.join(pkg, "identity.json"))
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
        key = _load_key(args.key)
        sig_dir = os.path.join(pkg, "signatures")
        os.makedirs(sig_dir, exist_ok=True)
        _write(os.path.join(sig_dir, "seal.json"), {
            "schema": SPEC_VERSION,
            "algorithm": ALGORITHM,
            "key_id": key_id(key),
            "signed": "identity+manifest",
            "signature": seal_sign(key, identity, manifest),
            "created_at": _now(),
        })
        msg += " | seal signed (key_id %s...)" % key_id(key)[:16]
    print(msg)


def cmd_verify(args):
    pkg = os.path.abspath(args.path)
    if not os.path.isdir(pkg):
        sys.exit(f"error: package dir not found: {pkg}")
    key = _load_key(args.key) if args.key else None
    report = verify(pkg, key=key)
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
                   help="hex key file: also write an HMAC-SHA256 seal signature")
    p.set_defaults(func=cmd_submit)

    p = sub.add_parser("verify", help="verify package (exit 0 = PASS)")
    p.add_argument("path")
    p.add_argument("--key", default=None, metavar="KEYFILE",
                   help="hex owner key: strict mode - unsigned/mismatched seal FAILS (S6)")
    p.set_defaults(func=cmd_verify)

    p = sub.add_parser("keygen", help="generate a 256-bit seal key (hex file)")
    p.add_argument("--out", required=True, metavar="KEYFILE")
    p.set_defaults(func=cmd_keygen)

    p = sub.add_parser("inspect", help="human-readable package summary")
    p.add_argument("path"); p.set_defaults(func=cmd_inspect)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
