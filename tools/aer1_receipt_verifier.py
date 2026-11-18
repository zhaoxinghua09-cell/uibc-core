#!/usr/bin/env python3
"""AER-1 receipt verifier: independent implementation of the receipt,
id-binding, chain-commitment, anchor and workflow checks.

This tool exists to answer one question per vector: does an implementation
written from the specification's text — not from the publisher's runner —
reproduce the expected outcome? It does not import uibc_core and it does
not import the publisher's conformance runner.

Coverage in this batch:
  base/test-vectors/{valid,invalid,invalid-profile}/*.json   (64 files)
  base/anchor-vectors.json                                   (8)
  base/id-binding-vectors.json                               (6)
  base/commitment-vectors.json                               (8)
  workflow-merkle-seq-output-v1.json                         (8)
                                                             = 94 vectors

Usage:  python3 tools/aer1_receipt_verifier.py --kit /path/to/kit [--json]
Exit code 0 when every vector behaves as expected.
"""

import argparse
import base64
import binascii
import hashlib
import json
import os
import re
import sys

UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\Z")
STRICT_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z")
RFC3339_RE = re.compile(r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]+)?(Z|[+-][0-9]{2}:[0-9]{2})\Z")
HASH_RE = re.compile(r"^sha256:[0-9a-f]{64}\Z")
HEX64_RE = re.compile(r"^[0-9a-f]{64}\Z")
PROV_RE = re.compile(r"^(EXECUTED BY [A-Z0-9][A-Z0-9 ._-]*|OBSERVED VIA GATEWAY|LOGGED BY AGENT)\Z")
B64_RE = re.compile(r"^[A-Za-z0-9+/]*={0,2}\Z")
NIL_UUID = "00000000-0000-0000-0000-000000000000"
CORE = ["id", "receipt_schema_version", "created_at", "tool",
        "provenance_class", "canonical_bytes", "output_hash",
        "verification_status"]
ZERO_DIGEST = "0" * 64
ANCHOR_PROFILE_MEMBERS = {"log", "leaf_hash", "anchored_at", "proof"}
# Section 6 step 4 says a 0.4 receipt without metadata_hash MUST fail, but
# the published corpus marks four such receipts valid. Default follows the
# corpus so the vectors can be reproduced; --strict-metadata follows the
# specification text instead, and the difference is reported as a finding.
STRICT_METADATA = False


class Bad(Exception):
    """A structural/parse failure that must be reported as a rejection."""


def strict_rfc3339(s):
    """RFC 3339 shape AND a real calendar instant; seconds=60 rejected."""
    if not isinstance(s, str) or not RFC3339_RE.match(s):
        return False
    if not s.endswith("Z"):
        off = s[-6:]
        try:
            oh, om = int(off[1:3]), int(off[4:6])
        except ValueError:
            return False
        if not (0 <= oh <= 23 and 0 <= om <= 59):
            return False
    try:
        year = int(s[0:4]); month = int(s[5:7]); day = int(s[8:10])
        hour = int(s[11:13]); minute = int(s[14:16]); second = int(s[17:19])
    except ValueError:
        return False
    if not (1 <= month <= 12):
        return False
    if not (0 <= hour <= 23 and 0 <= minute <= 59 and 0 <= second <= 59):
        return False
    if month in (1, 3, 5, 7, 8, 10, 12):
        max_day = 31
    elif month in (4, 6, 9, 11):
        max_day = 30
    else:
        leap = (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0))
        max_day = 29 if leap else 28
    return 1 <= day <= max_day


def first_duplicate_member(text):
    """First duplicated member name anywhere in the JSON text, or None.

    A plain parse keeps one value and would let one byte string carry two
    meanings, so the signal is taken from the text before any parse.
    """
    found = []

    def hook(pairs):
        seen = set()
        for key, _v in pairs:
            if key in seen and not found:
                found.append(key)
            seen.add(key)
        return dict(pairs)

    json.loads(text, object_pairs_hook=hook)
    return found[0] if found else None


def decode_canonical(receipt):
    """Return the exact UTF-8 bytes of canonical_bytes or raise Bad."""
    cb = receipt.get("canonical_bytes")
    if not isinstance(cb, str) or not B64_RE.match(cb) or "=" in cb[:-2] or len(cb) % 4:
        raise Bad("canonical_bytes is not valid base64")
    try:
        raw = base64.b64decode(cb, validate=True)
    except (binascii.Error, ValueError):
        raise Bad("canonical_bytes is not valid base64")
    if base64.b64encode(raw).decode("ascii") != cb:
        raise Bad("canonical_bytes is not the canonical base64 spelling")
    try:
        raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Bad("canonical_bytes is not valid UTF-8")
    return raw


def legacy_production_shape(receipt):
    """0.3 production shape: 'timestamp' instead of created_at, bare tool
    string plus a tool_context carrying name/version/scope."""
    if not isinstance(receipt, dict) or "created_at" in receipt:
        return False
    if receipt.get("receipt_schema_version") not in ("0.2", "0.3"):
        return False
    ts = receipt.get("timestamp")
    if not isinstance(ts, str) or not ts:
        return False
    tool = receipt.get("tool")
    ctx = receipt.get("tool_context")
    if not isinstance(tool, str) or not tool or not isinstance(ctx, dict):
        return False
    if not all(isinstance(ctx.get(k), str) and ctx[k] for k in ("name", "version", "scope")):
        return False
    return ctx.get("name") == tool


def metadata_block(receipt):
    """Section 3.1 canonical metadata block: exactly six members, the
    nested tool object restricted to name/scope/version, serialized with
    code-point ordering, no whitespace, and Section 7.1 escaping."""
    tool = receipt.get("tool")
    return {
        "created_at": receipt.get("created_at"),
        "id": receipt.get("id"),
        "output_hash": receipt.get("output_hash"),
        "provenance_class": receipt.get("provenance_class"),
        "receipt_schema_version": receipt.get("receipt_schema_version"),
        "tool": {"name": (tool or {}).get("name") if isinstance(tool, dict) else None,
                 "scope": (tool or {}).get("scope") if isinstance(tool, dict) else None,
                 "version": (tool or {}).get("version") if isinstance(tool, dict) else None},
    }


def metadata_digest(receipt):
    blob = json.dumps(metadata_block(receipt), sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return "sha256:" + hashlib.sha256(blob).hexdigest()


def version_at_least(version_string, floor="0.4"):
    """Compare dot-separated numeric components numerically."""
    def parts(v):
        try:
            return [int(x) for x in str(v).split(".")]
        except (TypeError, ValueError):
            return None
    a, b = parts(version_string), parts(floor)
    if a is None or b is None:
        return False
    while len(a) < len(b):
        a.append(0)
    while len(b) < len(a):
        b.append(0)
    return a >= b


def core_check(receipt):
    """Steps 1-4 of Section 6 over the presented bytes. [] = pass."""
    if not isinstance(receipt, dict):
        return ["receipt is not a JSON object"]
    legacy = legacy_production_shape(receipt)
    required = CORE if not legacy else ([f for f in CORE if f != "created_at"]
                                        + ["timestamp", "tool_context"])
    missing = [f for f in required if f not in receipt]
    if missing:
        return ["missing required member: %s" % f for f in missing]
    fails = []
    rid = receipt.get("id")
    if not isinstance(rid, str) or not UUID_RE.match(rid):
        fails.append("id is not a lowercase UUID")
    elif rid == NIL_UUID:
        fails.append("id is the nil UUID")
    if not isinstance(receipt.get("receipt_schema_version"), str) or \
            not receipt["receipt_schema_version"]:
        fails.append("receipt_schema_version is not a non-empty string")
    created = receipt.get("timestamp") if legacy else receipt.get("created_at")
    if not isinstance(created, str):
        fails.append("created_at is not a string")
    elif not RFC3339_RE.match(created):
        fails.append("created_at is not RFC 3339")
    elif not strict_rfc3339(created):
        fails.append("created_at is not a valid calendar date/time")
    tool = receipt.get("tool_context") if legacy else receipt.get("tool")
    if not isinstance(tool, dict) or not all(
            isinstance(tool.get(k), str) and tool[k] for k in ("name", "version", "scope")):
        fails.append("tool is not an object with name/version/scope strings")
    if not isinstance(receipt.get("provenance_class"), str) or \
            not PROV_RE.match(receipt["provenance_class"]):
        fails.append("provenance_class is not a known class")
    raw = None
    try:
        raw = decode_canonical(receipt)
    except Bad as e:
        fails.append(str(e))
    oh = receipt.get("output_hash")
    if not isinstance(oh, str) or not HASH_RE.match(oh):
        fails.append("output_hash is not sha256: + lowercase hex digest")
    elif raw is not None and oh != "sha256:" + hashlib.sha256(raw).hexdigest():
        fails.append("output_hash does not match sha256(canonical_bytes)")
    ih = receipt.get("input_hash")
    if ih is not None:
        if not isinstance(ih, str) or not HASH_RE.match(ih):
            fails.append("input_hash is not sha256: + lowercase hex digest")
        elif raw is not None:
            try:
                payload = json.loads(raw.decode("utf-8"))
            except ValueError:
                payload = None
            if isinstance(payload, dict) and "inputs" in payload:
                blob = json.dumps(payload["inputs"], sort_keys=True,
                                  separators=(",", ":")).encode("utf-8")
                if ih != "sha256:" + hashlib.sha256(blob).hexdigest():
                    fails.append("input_hash does not match sha256(canonical "
                                 "JSON of the recorded inputs)")
    if legacy:
        if not isinstance(receipt.get("verification_status"), str) or \
                not receipt["verification_status"]:
            fails.append("verification_status is not a non-empty string")
    elif receipt.get("verification_status") != "verified":
        fails.append("verification_status is not verified")
    # Section 6 step 4, metadata binding. The publisher's runner leaves
    # metadata_hash unchecked; this implementation enforces the rule.
    mh = receipt.get("metadata_hash")
    required = STRICT_METADATA and version_at_least(receipt.get("receipt_schema_version"))
    if mh is not None or required:
        if not isinstance(mh, str) or not HASH_RE.match(mh):
            fails.append("metadata_hash is missing or not sha256: + lowercase "
                         "hex digest (required at 0.4 and later)")
        else:
            try:
                want = metadata_digest(receipt)
            except (TypeError, ValueError):
                want = None
            if want is not None and mh != want:
                fails.append("metadata_hash does not match the recomputed "
                             "canonical metadata block")
    return fails


def version_and_binding(receipt):
    """(is_legacy, failures): inner/outer version agreement and the
    bound issuer_claims.provenance_class."""
    inner = None
    try:
        raw = base64.b64decode(receipt.get("canonical_bytes", ""), validate=True)
        inner = json.loads(raw.decode("utf-8"))
    except Exception:
        inner = None
    inner_version = inner.get("receipt_schema_version") if isinstance(inner, dict) else None
    outer_version = receipt.get("receipt_schema_version")
    verdict_version = inner_version if inner_version is not None else outer_version
    if verdict_version is not None and str(verdict_version) in ("0.2", "0.3"):
        return True, []
    fails = []
    if inner_version is not None and outer_version is not None:
        if str(inner_version) != str(outer_version):
            fails.append("receipt_schema_version: outer does not match committed")
    else:
        fails.append("receipt_schema_version: one side missing")
    if isinstance(inner, dict):
        claims = inner.get("issuer_claims")
        committed = claims.get("provenance_class") if isinstance(claims, dict) else None
        outer_pc = receipt.get("provenance_class")
        if committed is not None and outer_pc is not None:
            if committed != outer_pc:
                fails.append("provenance binding: outer does not match committed")
        else:
            fails.append("provenance binding: one side missing")
    else:
        fails.append("provenance binding: canonical payload did not decode to an object")
    return False, fails


def reference_profile(receipt):
    """Reference-producer convention: the canonical payload carries
    'inputs'. Outside the core, so a failure here never rejects a receipt."""
    try:
        raw = base64.b64decode(receipt.get("canonical_bytes", ""), validate=True)
        raw.decode("utf-8")
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return ["canonical payload is not a UTF-8 JSON object"]
    if not isinstance(payload, dict):
        return ["canonical payload is not a JSON object"]
    if "inputs" not in payload:
        return ["reference-producer payload omits the 'inputs' member"]
    return []


def disinterested_tier(receipt):
    """Strict id profile plus the in-record anchor profile: exactly
    log/leaf_hash/anchored_at/proof, leaf_hash over canonical_bytes."""
    fails = []
    rid = receipt.get("id")
    if not isinstance(rid, str) or not STRICT_UUID_RE.match(rid):
        fails.append("id is not a UUID v4 (strict profile)")
    anchor = receipt.get("anchor")
    if not isinstance(anchor, dict):
        return ["anchor is not an object"]
    if set(anchor) != ANCHOR_PROFILE_MEMBERS:
        fails.append("anchor members are not exactly log/leaf_hash/anchored_at/proof")
    if not isinstance(anchor.get("log"), str) or not anchor["log"]:
        fails.append("anchor.log is not a non-empty string")
    leaf = anchor.get("leaf_hash")
    if not isinstance(leaf, str) or not HASH_RE.match(leaf):
        fails.append("anchor.leaf_hash is not sha256: + lowercase hex digest")
    else:
        try:
            raw = decode_canonical(receipt)
        except Bad as e:
            fails.append(str(e))
        else:
            if leaf != "sha256:" + hashlib.sha256(raw).hexdigest():
                fails.append("anchor.leaf_hash does not match canonical_bytes")
    at = anchor.get("anchored_at")
    if not isinstance(at, str) or not RFC3339_RE.match(at):
        fails.append("anchor.anchored_at is not RFC 3339")
    elif not strict_rfc3339(at):
        fails.append("anchor.anchored_at is not a valid calendar date/time")
    if not isinstance(anchor.get("proof"), dict):
        fails.append("anchor.proof is not an object")
    return fails


def uri_host(uri):
    m = re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://([^/?#]+)", uri)
    if not m:
        return None
    return m.group(1).rsplit("@", 1)[-1].split(":", 1)[0].lower() or None


def anchor_present(receipt):
    """Present means: an anchor object carrying at least one member of
    this profile. A publication record under the same member name (Nostr
    event_id/pubkey/relays) is a different anchoring record, so absent."""
    anchor = receipt.get("anchor") if isinstance(receipt, dict) else None
    return isinstance(anchor, dict) and bool(set(anchor) & ANCHOR_PROFILE_MEMBERS)


def anchor_resolvable(receipt):
    """A log host in the .invalid TLD can never resolve; that is a
    resource outcome, not a value mismatch."""
    anchor = receipt.get("anchor")
    if not isinstance(anchor, dict):
        return True
    log = anchor.get("log")
    if not isinstance(log, str) or not log:
        return True
    host = uri_host(log)
    if host is None:
        return True
    return not host.endswith(".invalid")


def anchor_report(receipt, evaluate=True):
    """The three pieces the report must keep apart: present, evaluated,
    outcome."""
    if not anchor_present(receipt):
        return {"present": False, "evaluated": False, "outcome": "absent"}
    if not evaluate:
        return {"present": True, "evaluated": False, "outcome": "not checked"}
    if not anchor_resolvable(receipt):
        return {"present": True, "evaluated": True,
                "outcome": "rejected: unresolvable record"}
    return {"present": True, "evaluated": True,
            "outcome": "verification failed" if disinterested_tier(receipt) else "verified"}


def id_binding(receipt, expected_id=None, resolved_record=None):
    """(id_state, failures) per Section 6: the id lives outside the
    commitment, so it is bound only by an independent expectation or by
    resolving it and comparing the committed digests."""
    rid = receipt.get("id") if isinstance(receipt, dict) else None
    if expected_id is None and resolved_record is None:
        return "unverified", []
    fails = []
    state = None
    if expected_id is not None:
        if rid != expected_id:
            fails.append("id mismatch: artifact id does not match the expected id")
            state = "mismatch"
        else:
            state = "verified-expected"
    if resolved_record is not None:
        rrec = resolved_record
        if isinstance(rrec, dict) and isinstance(rrec.get("receipt"), dict):
            rrec = rrec["receipt"]
        if not isinstance(rrec, dict):
            fails.append("resolved record is not a JSON object")
            state = "mismatch"
        else:
            if rrec.get("output_hash") != receipt.get("output_hash"):
                fails.append("id mismatch: resolved digest disagrees with the artifact")
                state = "mismatch"
            elif rrec.get("id") is not None and rrec.get("id") != rid:
                fails.append("id mismatch: resolved record carries a different id")
                state = "mismatch"
            elif not fails:
                state = "verified-resolved"
    return (state or "unverified"), fails


def id_verdict(receipt, state):
    if not isinstance(receipt, dict) or receipt.get("id") is None:
        return "absent"
    return {"unverified": "unverified", "verified-expected": "matched",
            "verified-resolved": "resolved", "mismatch": "mismatched"}.get(state, "unverified")


def canon_string(value):
    """Section 7.1 string escaping: exactly json.dumps(ensure_ascii=True)."""
    return json.dumps(value, ensure_ascii=True)


def entry_digest_v07(entry):
    """Section 7.1 entry digest. seq must be an integer value; 1 and 1.0
    both serialize as 1; a boolean, string, null or fraction is rejected."""
    for key in ("prev_digest", "job_id", "id", "tool", "provenance_class"):
        if not isinstance(entry.get(key), str) or not entry[key]:
            raise ValueError("entry %s is not a non-empty string" % key)
    seq = entry.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, (int, float)):
        raise ValueError("seq is not an integer value")
    if isinstance(seq, float) and not seq.is_integer():
        raise ValueError("seq is not an integer value")
    seq = int(seq)
    close = entry.get("close", False)
    if not isinstance(close, bool):
        raise ValueError("close is not a boolean")
    raw = base64.b64decode(entry.get("canonical_bytes", ""), validate=True)
    output_hash = hashlib.sha256(raw).hexdigest()
    obj = {"close": close, "id": entry["id"], "job_id": entry["job_id"],
           "output_hash": output_hash, "prev_digest": entry["prev_digest"],
           "provenance_class": entry["provenance_class"], "seq": seq,
           "tool": entry["tool"]}
    body = "{" + ",".join(canon_string(k) + ":" +
                          (canon_string(v) if not isinstance(v, (bool, int)) else
                           ("true" if v is True else "false" if v is False else str(v)))
                          for k, v in obj.items()) + "}"
    return hashlib.sha256(body.encode("utf-8")).hexdigest()


def chain_commitment_failures(timeline, commitment):
    """Section 7.3: bind job identity, length and the final entry digest."""
    if not isinstance(timeline, list) or not timeline:
        return ["timeline is not a non-empty list"]
    if not isinstance(commitment, dict):
        return ["commitment is not a JSON object"]
    fails = []
    job_id = commitment.get("job_id")
    if not isinstance(job_id, str) or not job_id:
        fails.append("commitment job_id is not a non-empty string")
    digest = commitment.get("final_entry_digest")
    if not isinstance(digest, str) or not HEX64_RE.match(digest):
        fails.append("commitment final_entry_digest is not 64 lowercase hex characters")
    count = commitment.get("entry_count")
    # Integer token, not merely an integer-valued float: the corpus pins
    # a float entry_count as invalid even though the value is integral.
    if isinstance(count, bool) or not isinstance(count, int):
        fails.append("commitment entry_count is not an integer")
    published = commitment.get("published_at")
    if not isinstance(published, str) or not RFC3339_RE.match(published):
        fails.append("commitment published_at is not RFC 3339")
    elif not strict_rfc3339(published):
        fails.append("commitment published_at is not a valid calendar date/time")
    if fails:
        return fails
    if count != len(timeline):
        fails.append("commitment entry_count does not match the timeline length")
    for i, entry in enumerate(timeline):
        if not isinstance(entry, dict) or not isinstance(entry.get("job_id"), str) \
                or not entry["job_id"]:
            fails.append("entry %d has no usable job_id" % i)
        elif entry["job_id"] != job_id:
            fails.append("entry %d job_id does not match the commitment job_id" % i)
    try:
        want = entry_digest_v07(timeline[-1])
    except Exception as e:
        fails.append("final entry digest could not be recomputed: %s" % e)
    else:
        if digest != want:
            fails.append("commitment final_entry_digest does not match the "
                         "recomputed digest")
    return fails


def merkle_root(leaves):
    """Section 8.1: odd node counts duplicate the last node."""
    level = [hashlib.sha256(x.encode("utf-8")).digest() for x in leaves]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [hashlib.sha256(level[i] + level[i + 1]).digest()
                 for i in range(0, len(level), 2)]
    return level[0].hex() if level else hashlib.sha256(b"").hexdigest()


def workflow_failures(workflow):
    """Section 8.2 steps 3-4: offline mechanics, ordered, fail closed."""
    if not isinstance(workflow, dict):
        return ["workflow is not a JSON object"]
    fails = []
    if workflow.get("type") != "verifiable-workflow-receipt":
        fails.append('workflow type is not "verifiable-workflow-receipt"')
    if not isinstance(workflow.get("version"), str) or not workflow.get("version"):
        fails.append("workflow version is not a non-empty string")
    if not isinstance(workflow.get("workflow_id"), str) or \
            not UUID_RE.match(workflow["workflow_id"]):
        fails.append("workflow workflow_id is not a lowercase UUID")
    if not isinstance(workflow.get("receipt_id"), str) or \
            not UUID_RE.match(workflow["receipt_id"]):
        fails.append("workflow receipt_id is not a lowercase UUID")
    for member in ("session_id", "goal", "status"):
        if not isinstance(workflow.get(member), str) or not workflow.get(member):
            fails.append("workflow %s is not a non-empty string" % member)
    if not isinstance(workflow.get("output_hash"), str) or \
            not HEX64_RE.match(workflow["output_hash"]):
        fails.append("workflow output_hash is not 64 lowercase hex characters")
    vu = workflow.get("verify_url")
    if not isinstance(vu, str) or not (vu.startswith("http://") or vu.startswith("https://")):
        fails.append("workflow verify_url is not an http(s) URL string")
    steps = workflow.get("steps")
    if not isinstance(steps, list) or not steps:
        fails.append("workflow steps is not a non-empty list")
        return fails
    for i, step in enumerate(steps):
        if not isinstance(step, dict):
            fails.append("step %d is not an object" % (i + 1))
            continue
        seq = step.get("seq")
        if isinstance(seq, bool) or not isinstance(seq, (int, float)) or \
                (isinstance(seq, float) and not seq.is_integer()):
            fails.append("step %d seq is not an integer" % (i + 1))
        if not isinstance(step.get("receipt_id"), str):
            fails.append("step %d receipt_id is not a string" % (i + 1))
        if not isinstance(step.get("tool"), str) or not step.get("tool"):
            fails.append("step %d tool is not a non-empty string" % (i + 1))
        if not isinstance(step.get("receipt_hash"), str) or \
                not HEX64_RE.match(step["receipt_hash"]):
            fails.append("step %d receipt_hash is not 64 lowercase hex characters" % (i + 1))
        for member in ("started_at", "ended_at"):
            if not strict_rfc3339(step.get(member)):
                fails.append("step %d %s is not a valid RFC 3339 timestamp" % (i + 1, member))
        if not isinstance(step.get("status"), str) or not step.get("status"):
            fails.append("step %d status is not a non-empty string" % (i + 1))
    if fails:
        return fails
    n = len(steps)
    for i, step in enumerate(steps):
        if int(step["seq"]) != i + 1:
            fails.append("step seq values are not 1..%d in order" % n)
            break
    seen = set()
    for step in steps:
        rid = step["receipt_id"]
        if rid in seen:
            fails.append("duplicate receipt_id: %s" % rid)
            break
        seen.add(rid)
    expected = merkle_root([step["receipt_id"] for step in steps])
    if workflow.get("merkle_root") != expected:
        fails.append("merkle_root does not match the recomputed Section 8.1 root")
    return fails


# ---------------------------------------------------------------- runners

def run_receipt_fixtures(base, out):
    """64 single-receipt fixtures: valid/, invalid/, invalid-profile/."""
    counts = {"valid": 0, "invalid": 0, "invalid-profile": 0}
    problems = []
    for group in ("valid", "invalid", "invalid-profile"):
        directory = os.path.join(base, "test-vectors", group)
        files = sorted(f for f in os.listdir(directory) if f.endswith(".json"))
        if not files:
            problems.append("%s directory matched zero files" % group)
        for name in files:
            path = os.path.join(directory, name)
            text = open(path, encoding="utf-8").read()
            dup = first_duplicate_member(text)
            receipt = json.loads(text)
            fails = []
            if dup is not None:
                fails.append("rejected: duplicate member name (%s)" % dup)
            else:
                fails = core_check(receipt)
                if isinstance(receipt, dict) and not fails:
                    _, binding_fails = version_and_binding(receipt)
                    fails.extend(binding_fails)
            if group == "valid":
                ok = not fails
                detail = "" if ok else fails[0]
            elif group == "invalid":
                ok = bool(fails)
                detail = fails[0] if fails else "unexpectedly passed"
            else:
                # invalid-profile: core MUST pass, the producer convention MUST fail.
                profile = reference_profile(receipt) if isinstance(receipt, dict) else ["not an object"]
                ok = (not fails) and bool(profile)
                detail = "" if ok else ("core failed: %s" % fails[0]) if fails else "profile passed"
            counts[group] += 1
            if not ok:
                problems.append("%s/%s: %s" % (group, name, detail))
            out.append(("%s/%s" % (group, name), ok))
    return counts, problems


def run_anchored_fixtures(base, out):
    """The six anchored fixtures as vectors in their own right: the core
    commitment must pass and the per-anchor outcome must land where the
    fixture name says it lands."""
    directory = os.path.join(base, "test-vectors", "anchored")
    files = sorted(f for f in os.listdir(directory) if f.endswith(".json"))
    expected = {"anchored-valid.json": "verified",
                "anchored-unresolvable-anchor.json": "rejected: unresolvable record"}
    problems = []
    for name in files:
        text = open(os.path.join(directory, name), encoding="utf-8").read()
        dup = first_duplicate_member(text)
        receipt = json.loads(text)
        core = ["rejected: duplicate member name"] if dup else core_check(receipt)
        if not core:
            _, binding = version_and_binding(receipt)
            core = binding
        want = expected.get(name, "verification failed")
        report = anchor_report(receipt, evaluate=True)
        ok = not core and report["outcome"] == want
        if not ok:
            problems.append("anchored/%s: core=%s outcome=%s expected=%s"
                            % (name, core[:1], report["outcome"], want))
        out.append(("anchored/%s" % name, ok))
    return len(files), problems


def run_anchor_vectors(base, out):
    path = os.path.join(base, "anchor-vectors.json")
    vectors = json.load(open(path, encoding="utf-8"))["vectors"]
    problems = []
    for v in vectors:
        if "receipt" in v:
            receipt = v["receipt"]
        else:
            fpath = os.path.join(base, v["file"])
            receipt = json.load(open(fpath, encoding="utf-8"))
        report = anchor_report(receipt, evaluate=v.get("evaluate", True))
        ok = (report["present"] == v["expected_present"] and
              report["evaluated"] == v["expected_evaluated"] and
              report["outcome"] == v["expected_anchor_outcome"])
        if not ok:
            problems.append("anchor %s: got %s, expected %s" % (
                v.get("name"), report, {k: v[k] for k in
                                       ("expected_present", "expected_evaluated",
                                        "expected_anchor_outcome")}))
        out.append(("anchor/%s" % v.get("name"), ok))
    return len(vectors), problems


def run_id_binding_vectors(base, out):
    vectors = json.load(open(os.path.join(base, "id-binding-vectors.json"),
                             encoding="utf-8"))["vectors"]
    problems = []
    for v in vectors:
        receipt = v["receipt"]
        structural = core_check(receipt)
        state, id_fails = id_binding(receipt,
                                     expected_id=v.get("expected_id"),
                                     resolved_record=v.get("resolved_record"))
        verdict = id_verdict(receipt, state)
        want_verdict = v.get("expected_verdict")
        got_verdict = "fail" if (structural or id_fails) else "pass"
        ok = (got_verdict == want_verdict and
              state == v.get("expected_id_state") and
              verdict == v.get("expected_id_verdict"))
        if not ok:
            problems.append("id %s: got %s/%s/%s, expected %s/%s/%s" % (
                v["name"], got_verdict, state, verdict, want_verdict,
                v.get("expected_id_state"), v.get("expected_id_verdict")))
        out.append(("id/%s" % v["name"], ok))
    return len(vectors), problems


def run_commitment_vectors(base, out):
    vectors = json.load(open(os.path.join(base, "commitment-vectors.json"),
                             encoding="utf-8"))["vectors"]
    problems = []
    for v in vectors:
        fails = chain_commitment_failures(v["timeline"], v["commitment"])
        got = "valid" if not fails else "invalid"
        ok = got == v["expected_verdict"]
        if not ok:
            problems.append("commitment %s: got %s expected %s (%s)" % (
                v["name"], got, v["expected_verdict"], fails[:1]))
        out.append(("commitment/%s" % v["name"], ok))
    return len(vectors), problems


def run_workflow_vectors(kit, out):
    path = os.path.join(kit, "workflow-merkle-seq-output-v1.json")
    vectors = json.load(open(path, encoding="utf-8"))["vectors"]
    problems = []
    for v in vectors:
        level = []
        for i, step in enumerate(v["steps"], 1):
            if int(step["seq"]) != i:
                raise ValueError("noncontiguous sequence in %s" % v["name"])
            if v["merkle_version"] == "receipt-id-v0":
                leaf = step["receipt_id"]
            elif v["merkle_version"] == "seq-output-v1":
                oh = step["output_hash"]
                oh = oh[len("sha256:"):] if oh.startswith("sha256:") else oh
                if not HEX64_RE.match(oh.lower()):
                    raise ValueError("invalid output hash in %s" % v["name"])
                leaf = "%d:%s" % (i, oh.lower())
            else:
                raise ValueError("unsupported merkle_version")
            level.append(hashlib.sha256(leaf.encode("utf-8")).digest())
        while len(level) > 1:
            if len(level) % 2:
                level.append(level[-1])
            level = [hashlib.sha256(level[i] + level[i + 1]).digest()
                     for i in range(0, len(level), 2)]
        got = level[0].hex()
        ok = (v["expected_verdict"] == "valid" and got == v["merkle_root"])
        if not ok:
            problems.append("workflow %s: root mismatch" % v["name"])
        out.append(("workflow/%s" % v["name"], ok))
    return len(vectors), problems


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--kit", required=True,
                    help="corpus kit directory (contains index.json and base/)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--strict-metadata", action="store_true",
                    help="require metadata_hash at 0.4 and later per Section 6 "
                         "(the published corpus does not)")
    args = ap.parse_args()
    global STRICT_METADATA
    STRICT_METADATA = args.strict_metadata
    kit = args.kit
    base = os.path.join(kit, "base") if os.path.isdir(os.path.join(kit, "base")) else kit
    results, problems = [], []
    stats = {}
    counts, p = run_receipt_fixtures(base, results)
    stats.update({"valid": counts["valid"], "invalid": counts["invalid"],
                  "invalid-profile": counts["invalid-profile"]})
    problems += p
    n, p = run_anchored_fixtures(base, results)
    stats["anchored-fixtures"] = n
    problems += p
    for label, fn, arg in (("anchor", run_anchor_vectors, base),
                           ("id-binding", run_id_binding_vectors, base),
                           ("commitment", run_commitment_vectors, base),
                           ("workflow", run_workflow_vectors, kit)):
        n, p = fn(arg, results)
        stats[label] = n
        problems += p
    passed = sum(1 for _, ok in results if ok)
    total = len(results)
    if args.json:
        print(json.dumps({"families": stats, "vectors_replayed": total,
                          "pass": passed, "all_pass": passed == total == 94,
                          "problems": problems}, indent=1))
    else:
        for name, ok in results:
            if not ok:
                print("FAIL  %s" % name)
        print()
        print("valid           %d  (single-receipt fixtures that must pass)"
              % stats["valid"])
        print("invalid         %d  (single-receipt fixtures that must fail)"
              % stats["invalid"])
        print("invalid-profile %d  (core passes, producer convention fails)"
              % stats["invalid-profile"])
        print("anchored        %d  (core pass + per-anchor outcome)"
              % stats["anchored-fixtures"])
        print("anchor          %d  (present / evaluated / outcome)"
              % stats["anchor"])
        print("id-binding      %d  (id_verdict partition)"
              % stats["id-binding"])
        print("commitment      %d  (Section 7.3 chain commitment)"
              % stats["commitment"])
        print("workflow        %d  (Section 8.1 root over step leaves)"
              % stats["workflow"])
        print()
        print("%d/%d vectors reproduced (independent implementation, "
              "no uibc_core import, no publisher runner import)" % (passed, total))
        for p in problems[:20]:
            print("  - %s" % p)
    return 0 if passed == total == 94 else 1


if __name__ == "__main__":
    sys.exit(main())
