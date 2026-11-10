"""Independent verifier - second implementation of the UIBC spec (route step 9).

Independence discipline:
  - ZERO imports from uibc_core. Written from the SPEC (canonical-json root,
    lifecycle rules L1-L7, S1-S6 semantics), not from the reference code.
  - Read-only. Same evidence boundary as the reference verifier.
  - Different internal naming/structure on purpose: agreement between two
    differently-structured implementations is the spec-determinism signal.

NOTE (P1-1): "Independent" here means code-independent from the reference
implementation (zero shared imports, written from the spec). It is NOT an
independent third-party audit: this file is authored by the same maintainer
as uibc_core and shares the same trust root. It cross-checks spec determinism,
not organizational independence.

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


# --- Ed25519 verification, reimplemented from RFC 8032 5.1.7 --------------
# Affine-coordinate formulation on purpose: the reference implementation
# uses extended coordinates. Two encodings of the same equations agreeing
# is the determinism signal this file exists to provide.
_P = 2 ** 255 - 19
_DP = (-121665 * pow(121666, _P - 2, _P)) % _P
_GRP = 2 ** 252 + 27742317777372353535851937790883648493


def _pt_add(p1, p2):
    x1, y1 = p1
    x2, y2 = p2
    t = _DP * x1 * x2 * y1 * y2 % _P
    return ((x1 * y2 + x2 * y1) * pow(1 + t, _P - 2, _P) % _P,
            (y1 * y2 + x1 * x2) * pow(1 - t, _P - 2, _P) % _P)


def _pt_mul(p, n):
    q = (0, 1)
    while n:
        if n & 1:
            q = _pt_add(q, p)
        p = _pt_add(p, p)
        n >>= 1
    return q


def _pt_decode(data: bytes):
    y = int.from_bytes(data, "little") & ((1 << 255) - 1)
    sign = data[31] >> 7
    u = (y * y - 1) % _P
    v = (_DP * y * y + 1) % _P
    x = u * pow(v, _P - 2, _P) % _P
    x = pow(x, (_P + 3) // 8, _P)
    if (x * x - u * pow(v, _P - 2, _P)) % _P != 0:
        x = x * pow(2, (_P - 1) // 4, _P) % _P
    if (x * x - u * pow(v, _P - 2, _P)) % _P != 0:
        raise ValueError("not on curve")
    if (x & 1) != sign:
        x = _P - x
    return (x, y)


_BASE_Y = 4 * pow(5, _P - 2, _P) % _P
_BASE = _pt_decode(_BASE_Y.to_bytes(32, "little"))


def _ed25519_verify(pub: bytes, msg: bytes, sig: bytes) -> bool:
    try:
        if len(pub) != 32 or len(sig) != 64:
            return False
        r_bytes, s = sig[:32], int.from_bytes(sig[32:], "little")
        if s >= _GRP:
            return False
        a_pt = _pt_decode(pub)
        r_pt = _pt_decode(r_bytes)
        h = int.from_bytes(hashlib.sha512(r_bytes + pub + msg).digest(),
                           "little") % _GRP
        return _pt_mul(_BASE, s) == _pt_add(r_pt, _pt_mul(a_pt, h))
    except Exception:
        return False


def check_seal(key: bytes, package_dir: str) -> str:
    """S6 equivalent: PASS / FAIL / INCONCLUSIVE (seal v0.3 semantics).

    - Ed25519 seal: verified publicly with the recorded public key, in
      every mode; key_id must equal SHA-256 of that public key.
    - HMAC seal: checked only when the owner key is provided; without it
      INCONCLUSIVE (symmetric seals cannot be checked publicly).
    - No seal: FAIL when a key is demanded, otherwise INCONCLUSIVE
      (internally consistent, provenance unattested).
    """
    seal_path = os.path.join(package_dir, "signatures", "seal.json")
    if not os.path.isfile(seal_path):
        return "FAIL" if key is not None else "INCONCLUSIVE"
    with open(seal_path, "r", encoding="utf-8") as f:
        seal = json.load(f)
    with open(os.path.join(package_dir, "identity.json"), encoding="utf-8") as f:
        identity = json.load(f)
    with open(os.path.join(package_dir, "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
    if seal.get("algorithm") == "Ed25519":
        if key is not None:
            return "FAIL"  # an HMAC owner key cannot check a public seal
        try:
            pub = base64.b64decode(seal.get("public_key", ""), validate=True)
            sig = base64.b64decode(seal.get("signature", ""), validate=True)
        except Exception:
            return "FAIL"
        if len(pub) != 32 or seal.get("key_id") != hashlib.sha256(pub).hexdigest():
            return "FAIL"
        payload = canon_bytes({"identity": identity, "manifest": manifest})
        return "PASS" if _ed25519_verify(pub, payload, sig) else "FAIL"
    if key is None:
        return "INCONCLUSIVE"
    if seal.get("algorithm") != "HMAC-SHA256":
        return "FAIL"
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
    """Return {'result': PASS/FAIL/INCONCLUSIVE, 'checks': {V1..V6: result}}."""
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

    # overall (seal v0.3 three-valued rule, same as the reference):
    # FAIL anywhere -> FAIL; unresolved INCONCLUSIVE anywhere -> INCONCLUSIVE.
    vals = list(outcomes.values())
    if "FAIL" in vals:
        overall = "FAIL"
    elif "INCONCLUSIVE" in vals:
        overall = "INCONCLUSIVE"
    else:
        overall = "PASS"
    return {"implementer": "independent_verifier/0.1.0",
            "result": overall,
            "checks": outcomes}
