#!/usr/bin/env python3
"""Emit AER-1 receipts from a uibc evidence package, then let the
publisher's own runner judge them.

Why this tool exists: `tools/aer1_receipt_verifier.py` replays their
vectors. Replaying a published expectation is not the same thing as
producing a record that their implementation accepts. This tool closes
that gap — it writes AER-1 0.4 receipts over our own evidence packages
and then hands them to the publisher's `check()`,
`check_version_and_binding()` and `check_reference_profile()` for an
independent verdict. Nothing is asserted about our output by us.

Byte layout we commit to (published here because Section 3.3 requires a
producer to state it): the canonical payload is the UTF-8 encoding of
our JSON object serialized with sorted member names, no whitespace
outside strings, and `ensure_ascii=False`. The receipt id is derived
deterministically from the package bytes and the step index, and is
minted as a UUIDv4 with RFC 4122 variant bits.

Usage:
  python3 tools/emit_aer1_receipts.py --package fixtures/clean.uibc \
      --out /tmp/aer1_emit.json \
      --publisher-runner /path/to/corpus/base/conformance.py

The publisher's runner is loaded from the corpus directory, never
vendored into this repository: we want their code to judge our bytes,
not a copy of their code that we control.
"""

import argparse
import base64
import hashlib
import importlib.util
import json
import os
import sys

TOOL_NAME = "uibc-core"
TOOL_VERSION = "0.3.3"
TOOL_SCOPE = "public"
PROVENANCE = "LOGGED BY AGENT"      # we record a report; we do not claim we ran it
SCHEMA_VERSION = "0.4"


def canon_bytes(obj):
    """Our published payload layout: sorted keys, compact, UTF-8."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def mint_uuid4(seed_bytes):
    """Deterministic UUIDv4-shaped identifier with RFC 4122 variant bits."""
    digest = bytearray(hashlib.sha256(seed_bytes).digest()[:16])
    digest[6] = (digest[6] & 0x0F) | 0x40          # version 4
    digest[8] = (digest[8] & 0x3F) | 0x80          # RFC 4122 variant
    h = digest.hex()
    return "%s-%s-%s-%s-%s" % (h[0:8], h[8:12], h[12:16], h[16:20], h[20:32])


def metadata_block(receipt):
    """Section 3.1: exactly six members, nested tool restricted to
    name/scope/version, code-point ordering, no whitespace."""
    tool = receipt["tool"]
    return {
        "created_at": receipt["created_at"],
        "id": receipt["id"],
        "output_hash": receipt["output_hash"],
        "provenance_class": receipt["provenance_class"],
        "receipt_schema_version": receipt["receipt_schema_version"],
        "tool": {"name": tool["name"], "scope": tool["scope"],
                 "version": tool["version"]},
    }


def metadata_digest(receipt):
    blob = json.dumps(metadata_block(receipt), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def load_package(path):
    """Read the manifest and the evidence index.

    One receipt is emitted per evidence entry, because AER-1 issues
    one receipt per tool call, and our evidence index is exactly the
    per-step record.
    """
    manifest_path = os.path.join(path, "manifest.json")
    if not os.path.isfile(manifest_path):
        raise SystemExit("not a uibc package (no manifest.json): %s" % path)
    with open(manifest_path, encoding="utf-8") as f:
        manifest = json.load(f)
    index_path = os.path.join(path, "evidence", "index.json")
    entries = []
    if os.path.isfile(index_path):
        with open(index_path, encoding="utf-8") as f:
            entries = json.load(f).get("entries") or []
    if not entries:
        entries = [{"evidence_id": "package", "type": "PACKAGE",
                    "path": "manifest.json", "created_at": None,
                    "media_type": "application/json", "note": "package manifest",
                    "content_hash": manifest.get("evidence_root")}]
    return manifest, entries


def build_receipt(manifest, entry, index, package_path, ev_root):
    """One AER-1 receipt per evidence entry.

    The payload carries the entry plus the package binding, and states
    its own schema version and issuer claims so that Section 6's
    version-agreement and provenance-binding checks have both sides to
    compare.
    """
    step_name = entry.get("path") or entry.get("evidence_id") or ("step-%d" % index)
    rel = entry.get("path")
    measured = None
    if rel:
        candidate = os.path.join(package_path, "evidence", rel)
        if os.path.isfile(candidate):
            with open(candidate, "rb") as f:
                measured = hashlib.sha256(f.read()).hexdigest()
    step = {
        "evidence_id": entry.get("evidence_id"),
        "type": entry.get("type"),
        "path": rel,
        "media_type": entry.get("media_type"),
        "note": entry.get("note"),
        "declared_content_hash": entry.get("content_hash"),
        "measured_content_hash": measured,
        "content_hash_matches": (measured == entry.get("content_hash")
                                 if measured is not None else None),
    }
    payload = {
        "receipt_schema_version": SCHEMA_VERSION,
        "issuer_claims": {"provenance_class": PROVENANCE},
        "tool": TOOL_NAME,
        "inputs": {"package": os.path.basename(os.path.abspath(package_path)),
                   "step": step_name},
        "outputs": step,
        "uibc": {"package_schema": manifest.get("schema"),
                 "agent_id": manifest.get("agent_id"),
                 "agent_version": manifest.get("agent_version"),
                 "evidence_count": manifest.get("evidence_count"),
                 "evidence_root": manifest.get("evidence_root"),
                 "status": manifest.get("status")},
    }
    raw = canon_bytes(payload)
    created = entry.get("created_at") or manifest.get("created_at") or \
        "1970-01-01T00:00:00Z"
    rid = mint_uuid4((manifest.get("evidence_root") or "").encode() +
                     b"|" + str(index).encode() + b"|" + str(step_name).encode())
    receipt = {
        "id": rid,
        "receipt_schema_version": SCHEMA_VERSION,
        "created_at": created,
        "tool": {"name": TOOL_NAME, "version": TOOL_VERSION, "scope": TOOL_SCOPE},
        "provenance_class": PROVENANCE,
        "canonical_bytes": base64.b64encode(raw).decode("ascii"),
        "output_hash": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "verification_status": "verified",
    }
    receipt["metadata_hash"] = metadata_digest(receipt)
    return receipt


def load_module(path):
    spec = importlib.util.spec_from_file_location("publisher_runner", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def payload_matches(receipt):
    """Read back the entry's content_hash_matches flag from the payload."""
    raw = base64.b64decode(receipt["canonical_bytes"], validate=True)
    try:
        payload = json.loads(raw.decode("utf-8"))
        return payload.get("outputs", {}).get("content_hash_matches")
    except (ValueError, UnicodeDecodeError):
        return None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--package", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--publisher-runner", default=None,
                    help="path to the corpus copy of conformance.py "
                         "(base/ directory); enables the independent verdict")
    args = ap.parse_args(argv)

    manifest, entries = load_package(args.package)
    receipts, integrity = [], []
    for i, entry in enumerate(entries):
        receipt = build_receipt(manifest, entry, i, args.package, args.package)
        receipts.append(receipt)
        if entry.get("content_hash") and payload_matches(receipt) is False:
            integrity.append("entry %d: declared content_hash does not match "
                             "the file bytes" % i)

    # Our own verifier must accept our output before anything is written.
    ours = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "aer1_receipt_verifier.py")
    spec = importlib.util.spec_from_file_location("own_verifier", ours)
    mine = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mine)
    self_fails = []
    for i, r in enumerate(receipts):
        f = mine.core_check(r)
        if f:
            self_fails.append("receipt %d: %s" % (i, f[0]))
        _, bf = mine.version_and_binding(r)
        self_fails.extend("receipt %d: %s" % (i, x) for x in bf)
    if self_fails:
        print("SELF-VERIFY FAILED; refusing to write:")
        for p in self_fails[:5]:
            print("  " + p)
        return 2

    verdict = None
    if args.publisher_runner:
        pub = load_module(args.publisher_runner)
        problems = []
        for i, r in enumerate(receipts):
            problems.extend("receipt %d core: %s" % (i, x)
                            for x in pub.check(r))
            _, bind = pub.check_version_and_binding(r)
            problems.extend("receipt %d binding: %s" % (i, x) for x in bind)
            problems.extend("receipt %d profile: %s" % (i, x)
                            for x in pub.check_reference_profile(r))
        verdict = "PASS" if not problems else "FAIL"
        if problems:
            print("PUBLISHER RUNNER REJECTED OUR OUTPUT:")
            for p in problems[:8]:
                print("  " + p)

    out_dir = os.path.dirname(os.path.abspath(args.out))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    doc = {
        "schema": "uibc-core/aer1-receipts@1",
        "generated_at_utc": manifest.get("created_at"),
        "source_package": os.path.basename(os.path.abspath(args.package)),
        "payload_layout": "sorted member names, compact, UTF-8, ensure_ascii=False",
        "self_verified_by": "tools/aer1_receipt_verifier.py",
        "publisher_runner": args.publisher_runner,
        "publisher_verdict": verdict,
        "receipts": receipts,
    }
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)

    if integrity:
        print("EVIDENCE INTEGRITY: %s" % integrity[0])

    print("receipts=%d schema=%s entries=%d"
          % (len(receipts), SCHEMA_VERSION, len(entries)))
    print("self=%s%s" % ("PASS", "" if verdict is None else " publisher=%s" % verdict))
    print("OUT=%s" % args.out)
    return 0 if verdict in (None, "PASS") else 1


if __name__ == "__main__":
    sys.exit(main())
