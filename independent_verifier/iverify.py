"""Independent verifier - second implementation of the UIBC spec (route step 9).

Independence discipline:
  - ZERO imports from uibc_core. Written from the SPEC (canonical-json root,
    lifecycle rules L1-L7, S1-S6 semantics), not from the reference code.
  - Read-only. Same evidence boundary as the reference verifier.
  - Different internal naming/structure on purpose: agreement between two
    differently-structured implementations is the spec-determinism signal.

If this implementation and uibc_core.verify() ever disagree on a fixture,
that is a SPEC BUG (ambiguous spec), not merely a code bug.
"""

import base64
import hashlib
import hmac
import json
import os

REQUIRED = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]
KNOWN_EVENTS = {"REGISTER", "ACTIVATE", "UPDATE", "TRANSFER", "DELEGATE",
                "MIGRATE", "SUSPEND", "RESUME", "REVOKE", "RETIRE"}
TERMINAL_EVENTS = {"REVOKE", "RETIRE"}
KNOWN_EVIDENCE_TYPES = {
    "IDENTITY", "LIFECYCLE", "INPUT", "ACTION", "TOOL", "MEMORY", "OUTPUT",
    "EVALUATION", "HUMAN_DECISION", "VERIFICATION", "INCIDENT", "RETIREMENT",
}


def canon_bytes(obj) -> bytes:
    """Canonical serialization (provisional): sorted keys, tight separators."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def root_from_hashes(content_hashes) -> str:
    return hashlib.sha256(canon_bytes(sorted(content_hashes))).hexdigest()


def lifecycle_violations(events) -> list:
    """L1-L7 reimplemented from the spec rule list."""
    problems, seen, prev_ref, prev_kind, registered = [], set(), None, None, False
    for pos, ev in enumerate(events):
        kind, ref = ev.get("event_type"), ev.get("event_id")
        if kind not in KNOWN_EVENTS:
            problems.append(f"L3@{pos}")
        if ref in seen:
            problems.append(f"L5@{pos}")
        seen.add(ref)
        if ev.get("previous_event") != prev_ref:
            problems.append(f"L4@{pos}")
        if pos == 0 and kind != "REGISTER":
            problems.append(f"L1@{pos}")
        if pos > 0 and not registered:
            problems.append(f"L1@{pos}")
        if pos > 0 and kind == "REGISTER":
            problems.append(f"L2@{pos}")
        if kind == "REGISTER":
            registered = True
        if kind == "RESUME" and prev_kind != "SUSPEND":
            problems.append(f"L6@{pos}")
        if pos > 0 and prev_kind in TERMINAL_EVENTS:
            problems.append(f"L7@{pos}")
        prev_ref, prev_kind = ref, kind
    return problems


def check_seal(key: bytes, package_dir: str) -> str:
    """S6 equivalent: PASS / FAIL / INCONCLUSIVE / SKIP."""
    seal_path = os.path.join(package_dir, "signatures", "seal.json")
    if not os.path.isfile(seal_path):
        return "SKIP" if key is None else "FAIL"
    with open(seal_path, "r", encoding="utf-8") as f:
        seal = json.load(f)
    if key is None:
        return "INCONCLUSIVE"
    if seal.get("algorithm") != "HMAC-SHA256":
        return "FAIL"
    with open(os.path.join(package_dir, "identity.json"), encoding="utf-8") as f:
        identity = json.load(f)
    with open(os.path.join(package_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    if seal.get("key_id") != hashlib.sha256(key).hexdigest():
        return "FAIL"
    try:
        sig = base64.b64decode(seal.get("signature", ""), validate=True)
    except Exception:
        return "FAIL"
    payload = canon_bytes({"identity": identity, "manifest": manifest})
    expected = hmac.new(key, payload, hashlib.sha256).digest()
    return "PASS" if hmac.compare_digest(expected, sig) else "FAIL"


def independent_verify(package_dir: str, key: bytes = None) -> dict:
    """Return {'result': PASS/FAIL, 'checks': {V1..V6: result}}."""
    outcomes = {}

    outcomes["V1"] = "PASS" if all(
        os.path.isfile(os.path.join(package_dir, rel)) for rel in REQUIRED) else "FAIL"

    def load(rel):
        p = os.path.join(package_dir, rel)
        if not os.path.isfile(p):
            return {}
        with open(p, encoding="utf-8") as f:
            return json.load(f)

    manifest = load("manifest.json")
    identity = load("identity.json")
    events = load("lifecycle.json").get("events", [])
    index = load("evidence/index.json").get("entries", [])

    outcomes["V2"] = "PASS" if (identity.get("agent_id")
                                and manifest.get("agent_id") == identity.get("agent_id")) else "FAIL"

    outcomes["V3"] = "PASS" if not lifecycle_violations(events) else "FAIL"

    hashes, bad = [], False
    for e in index:
        p = os.path.join(package_dir, "evidence", e.get("path", ""))
        if not os.path.isfile(p):
            bad = True
            continue
        actual = sha256_file(p)
        hashes.append(actual)
        if actual != e.get("content_hash") or e.get("type") not in KNOWN_EVIDENCE_TYPES:
            bad = True
    outcomes["V4"] = "FAIL" if bad else "PASS"

    if index and not bad:
        outcomes["V5"] = "PASS" if root_from_hashes(hashes) == manifest.get("evidence_root") else "FAIL"
    else:
        outcomes["V5"] = "INCONCLUSIVE"

    outcomes["V6"] = check_seal(key, package_dir)

    # overall: V6 handled like S6 (strict FAIL, open INCONCLUSIVE is not fatal)
    blocking = [vid for vid in ("V1", "V2", "V3", "V4", "V5") if outcomes[vid] != "PASS"]
    if outcomes["V6"] == "FAIL":
        blocking.append("V6")
    return {"implementer": "independent_verifier/0.1.0",
            "result": "FAIL" if blocking else "PASS",
            "checks": outcomes}
