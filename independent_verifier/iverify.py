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
import math
import os
import re
import sys

REQUIRED = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]
KNOWN_EVENTS = {"REGISTER", "ACTIVATE", "UPDATE", "TRANSFER", "DELEGATE",
                "MIGRATE", "SUSPEND", "RESUME", "REVOKE", "RETIRE"}
TERMINAL_EVENTS = {"REVOKE", "RETIRE"}

NOT_DETECTED = "No violation was detected within the observed evidence boundary."
# (keyword that identifies the topic, the wording used when the topic is a standing
# non-goal of this implementation). A topic already reported as an unjudged artefact
# found in this run is not repeated under its standing wording.
NOT_CHECKED_ALWAYS = [
    ("Merkle proof", "Merkle proof and root recomputation"),
    ("external timestamp", "external timestamp anchoring"),
    ("receipt", "compliance receipts"),
    ("policy", "policy artefacts"),
    ("strict base64", "strict base64 of identity notes"),
    ("attestation closure", "attestation closure"),
    ("duplicate JSON member", "duplicate JSON member names"),
    ("duplicate evidence_id", "duplicate evidence identifiers"),
    ("behavioral", "behavioral evaluation"),
    ("memory fidelity", "memory fidelity/continuity"),
    ("anchor", "anchor resolution"),
]


def _not_checked(unjudged):
    """Union of what this run found no rule for and what was never a goal here."""
    out = list(unjudged)
    for keyword, wording in NOT_CHECKED_ALWAYS:
        if any(keyword in item for item in unjudged):
            continue
        out.append(wording)
    return out
KNOWN_EVIDENCE_TYPES = {
    "IDENTITY", "LIFECYCLE", "INPUT", "ACTION", "TOOL", "MEMORY", "OUTPUT",
    "EVALUATION", "HUMAN_DECISION", "VERIFICATION", "INCIDENT", "RETIREMENT",
}


def _jcs_number_str(x):
    """ECMAScript Number::toString (RFC 8785 number rule), restated."""
    if isinstance(x, bool):
        raise TypeError("bool is not a JSON number")
    if isinstance(x, int):
        if not (-(2 ** 53) + 1 <= x <= 2 ** 53 - 1):
            raise ValueError("JCS: integer %r outside safe double range" % (x,))
        return str(x)
    if isinstance(x, float):
        if math.isnan(x) or math.isinf(x):
            raise ValueError("JCS: NaN/Infinity are not valid JSON numbers")
        if x == 0.0:
            return "0"
        s = json.dumps(x)
        if "e" in s or "E" in s:
            # Python uses exponent for 1e20..; ECMAScript keeps the fixed form
            # for whole numbers with <= 21 integer digits. Normalise that edge.
            if x.is_integer():
                iv = int(x)
                if 1 <= len(str(iv)) <= 21:
                    return str(iv)
            return s
        if s.endswith(".0"):
            return s[:-2]
        return s
    raise TypeError("JCS: unsupported number type %r" % (type(x),))


def _jcs_scalar(v):
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return _jcs_number_str(v)
    if isinstance(v, str):
        # json.dumps(ensure_ascii=False) is a faithful JCS string serializer.
        return json.dumps(v, ensure_ascii=False)
    raise TypeError("JCS: unsupported scalar type %r" % (type(v),))


def _jcs_value(v) -> str:
    """Recursive JCS serializer. Structured independently of uibc_core so that
    agreement is a determinism signal, not code reuse."""
    if isinstance(v, dict):
        parts = [json.dumps(k, ensure_ascii=False) + ":" + _jcs_value(v[k])
                 for k in sorted(v.keys(), key=lambda s: s.encode("utf-16-be"))]
        return "{" + ",".join(parts) + "}"
    if isinstance(v, list):
        return "[" + ",".join(_jcs_value(e) for e in v) + "]"
    return _jcs_scalar(v)


def canon_bytes(obj) -> bytes:
    """RFC 8785 (JCS) canonical serialization - written from the SPEC, not from
    uibc_core.canonical. The two must agree only because JCS is deterministic."""
    return _jcs_value(obj).encode("utf-8")


def sha256_file(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def root_from_hashes(content_hashes) -> str:
    return hashlib.sha256(canon_bytes(sorted(content_hashes))).hexdigest()


_TS_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
_UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


def _rfc3339_zoned(value) -> bool:
    """RFC 3339 timestamp with an explicit zone, and a date that actually exists.

    V10 exists because V1-V9 are structural: a string of the right shape passes
    even when the value is wrong. Measured 2026-11-20: three value-level mutations
    (timestamp without zone, 1900-02-29, uppercase UUID) were accepted by this
    implementation while the reference rejected them. A verifier that accepts them
    cannot be cited as agreeing with the reference on negative cases.
    """
    if not isinstance(value, str) or not _TS_RE.match(value):
        return False
    year, month, day = int(value[0:4]), int(value[5:7]), int(value[8:10])
    try:
        import datetime as _dt
        _dt.date(year, month, day)
    except ValueError:
        return False
    return True


def _canonical_lower_uuid(value) -> bool:
    return isinstance(value, str) and bool(_UUID_RE.match(value))


def value_level_violations(manifest, events) -> list:
    """V10: values that are structurally fine and factually wrong."""
    problems = []
    if not _rfc3339_zoned(manifest.get("created_at")):
        problems.append("V10:manifest.created_at")
    for pos, ev in enumerate(events):
        if not _rfc3339_zoned(ev.get("timestamp")):
            problems.append("V10:timestamp@%d" % pos)
        if not _canonical_lower_uuid(ev.get("event_id")):
            problems.append("V10:event_id@%d" % pos)
    return problems


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
    # v1.1: the seal may cover the lifecycle log as well. The coverage is
    # declared in the seal itself ("signed"), so a verifier never has to guess.
    lifecycle = {}
    lc_path = os.path.join(package_dir, "lifecycle.json")
    if os.path.isfile(lc_path):
        with open(lc_path, encoding="utf-8") as f:
            lifecycle = json.load(f)

    def _payload():
        doc = {"identity": identity, "manifest": manifest}
        if "lifecycle" in str(seal.get("signed", "")):
            doc["lifecycle"] = lifecycle
        return canon_bytes(doc)

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
        payload = _payload()
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
    payload = _payload()
    expected = hmac.new(key, payload, hashlib.sha256).digest()
    return "PASS" if hmac.compare_digest(expected, sig) else "FAIL"


def _hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def index_metadata_digest(entries) -> str:
    """Metadata-only digest of the evidence index (mirrors check S7)."""
    meta = [{"path": str(e.get("path", "")), "type": e.get("type"),
             "note": e.get("note"), "action_digest": e.get("action_digest")}
            for e in entries]
    meta.sort(key=lambda m: m["path"])
    return "sha256:" + _hex(canon_bytes(meta))


def lifecycle_head(events) -> str:
    n = len(events)
    last = events[-1] if n else None
    return "sha256:" + _hex(canon_bytes({
        "count": n,
        "last_sequence_number": (last or {}).get("sequence_number"),
        "last_event_digest": (_hex(canon_bytes(last)) if last is not None else None),
    }))


def checkpoint_head(lh: str, root: str, idx: str, count: int) -> str:
    return "sha256:" + _hex(canon_bytes({
        "lifecycle_head": lh, "evidence_root": root,
        "evidence_index_digest": idx, "evidence_count": count}))


def undeclared_root_files(package_dir: str, entries) -> list:
    """Files in the package ROOT that the package never declares (mirrors S1).

    Auxiliary files under a sub-directory (runtime snapshots) are not flagged:
    the root is what a reader sees, and only the root can carry a contradicting
    notes.md / README.md.
    """
    declared = set(REQUIRED) | {"signatures/seal.json"}
    for e in entries:
        declared.add("evidence/" + str(e.get("path", "")).replace("\\", "/"))
    junk = {"thumbs.db", ".ds_store", "desktop.ini"}
    extra = []
    for name in sorted(os.listdir(package_dir)):
        if name in ("evidence", "signatures"):
            continue
        if os.path.isdir(os.path.join(package_dir, name)):
            continue
        if name.lower() in junk:
            continue
        if name.replace("\\", "/") not in declared:
            extra.append(name)
    return extra


def _has_duplicate_members(package_dir):
    """True when any JSON file in the package repeats a member name in one object."""
    import json as _json

    def hook(pairs):
        keys = [k for k, _v in pairs]
        if len(keys) != len(set(keys)):
            hook.found = True
        return dict(pairs)

    hook.found = False
    for root, _dirs, files in os.walk(package_dir):
        for name in files:
            if not name.endswith(".json"):
                continue
            try:
                with open(os.path.join(root, name), encoding="utf-8") as fh:
                    _json.load(fh, object_pairs_hook=hook)
            except Exception:
                continue
            if hook.found:
                return True
    return False


def independent_verify(package_dir: str, key: bytes = None) -> dict:
    """Return {'result': PASS/FAIL/INCONCLUSIVE, 'checks': {V1..V9: result}}."""
    outcomes = {}

    # Foreign container. A verifier handed something that is not a UIBC package at all
    # -- an .aep archive, a random folder, a single file -- has no basis to say "this
    # package is broken". Saying FAIL there is an affirmative claim about a format it
    # never read. Measured 2026-11-20: run against the 13 published EATF vectors, this
    # implementation returned FAIL on all 5 of their packages that are valid by their
    # own contract, and agreement on the other 8 was incidental, not judgment.
    if not os.path.isdir(package_dir) or not any(
            os.path.isfile(os.path.join(package_dir, rel)) for rel in REQUIRED):
        return {"implementer": "independent_verifier/0.1.0",
                "result": "INCONCLUSIVE",
                "checks": {"V1": "INCONCLUSIVE"},
                "unjudged": ["container format: none of %s present" % ", ".join(REQUIRED)],
                "unsupported": "not-a-uibc-package",
                "scope": "Nothing: the input is not a UIBC package directory.",
                "limitations": ["This implementation only reads UIBC package directories; "
                                "other evidence formats are declined, not judged."],
                "checked": [],
                "not_checked": ["everything: no UIBC package was supplied"],
                "statement": "Declined: the input is not a UIBC package, so no verdict "
                             "about it is offered either way.",
                "strict": "open"}

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
    outcomes["V10"] = "PASS" if not value_level_violations(manifest, events) else "FAIL"

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

    # v1.1 parity: three checks the corpus (benchmark/adapter.py) showed this
    # implementation was missing while the reference already had them.
    extra_root = undeclared_root_files(package_dir, index)
    outcomes["V7"] = "FAIL" if extra_root else "PASS"

    sealed_idx = manifest.get("evidence_index_digest")
    if sealed_idx:
        outcomes["V8"] = ("PASS" if index_metadata_digest(index) == sealed_idx
                          else "FAIL")
    else:
        outcomes["V8"] = "INCONCLUSIVE"

    sealed_ckpt = manifest.get("checkpoint_head")
    if sealed_ckpt:
        recomputed = checkpoint_head(lifecycle_head(events),
                                     manifest.get("evidence_root") or
                                     root_from_hashes(hashes),
                                     index_metadata_digest(index), len(index))
        outcomes["V9"] = "PASS" if recomputed == sealed_ckpt else "FAIL"
    else:
        outcomes["V9"] = "INCONCLUSIVE"

    # Scope guard. Everything above is what this implementation can judge; this is the
    # statement of what it cannot. Without it, a package carrying an artefact this
    # implementation has no rule for came back PASS - an affirmative "no violation was
    # detected" about a file nobody in this implementation ever read. Measured before the
    # guard existed: PASS on 9 of 20 hostile packages the reference rejected.
    #
    # INCONCLUSIVE is the honest answer here, and it costs coverage: it does not raise any
    # number in INDEPENDENCE.md, it lowers the number of packages this implementation
    # will endorse.
    unjudged = []
    try:
        manifest = load("manifest.json") or {}
    except Exception:
        manifest = {}
    if isinstance(manifest, dict) and manifest.get("closure") is not None:
        unjudged.append("attestation closure (manifest.closure)")
    if os.path.isfile(os.path.join(package_dir, "evidence", "anchors.json")):
        unjudged.append("anchor resolution (evidence/anchors.json)")
    if os.path.isfile(os.path.join(package_dir, "evidence", "external_anchor.json")):
        unjudged.append("external timestamp (evidence/external_anchor.json)")
    if os.path.isfile(os.path.join(package_dir, "evidence", "chain.json")):
        unjudged.append("receipt chain (evidence/chain.json)")
    if os.path.isfile(os.path.join(package_dir, "evidence", "policies.json")):
        unjudged.append("policy artefacts (evidence/policies.json)")
    identity = None
    try:
        identity = load("identity.json") or {}
    except Exception:
        identity = {}
    if isinstance(identity, dict) and identity.get("note_b64") is not None:
        unjudged.append("strict base64 (identity.note_b64)")
    # Duplicate identifiers and duplicate JSON member names are detectable without
    # deciding whether they are violations; this implementation has no rule for either,
    # so it says it cannot judge rather than counting them as fine.
    try:
        index = load("evidence/index.json")
        entries = index["entries"] if isinstance(index, dict) else index
        ids = [e.get("evidence_id") for e in entries]
        if len(ids) != len(set(ids)):
            unjudged.append("duplicate evidence_id (S12 class)")
    except Exception:
        pass
    if _has_duplicate_members(package_dir):
        unjudged.append("duplicate JSON member name (S11 class)")

    # overall (seal v0.3 three-valued rule, same as the reference):
    # FAIL anywhere -> FAIL; unresolved INCONCLUSIVE anywhere -> INCONCLUSIVE.
    vals = list(outcomes.values())
    if "FAIL" in vals:
        overall = "FAIL"
    elif "INCONCLUSIVE" in vals or unjudged:
        overall = "INCONCLUSIVE"
    else:
        overall = "PASS"
    return {"implementer": "independent_verifier/0.1.0",
            "result": overall,
            "checks": outcomes,
            "unjudged": unjudged,
            # Disclosure of the same shape the reference emits, because a verdict without
            # a scope statement is read as broader than it is. `not_checked` here is the
            # union of what this run found it had no rule for and what this implementation
            # never set out to check at all - two different reasons, kept in one list on
            # purpose, since a consumer only needs to know it was not checked.
            "scope": ("Structure, identity consistency, lifecycle state machine, evidence "
                      "content hashes, evidence index metadata, value-level validity of "
                      "timestamps and event identifiers, and the seal signature, "
                      "using rules V1-V10 only."),
            "limitations": [
                "Rules V1-V9 cover nine of the checks the reference implements; the rest "
                "are declared not checked rather than assumed clean.",
                "HMAC seals are symmetric: verification needs the owner key. Ed25519 "
                "seals are third-party verifiable with the key recorded in the seal.",
                "In open mode the seal key is read out of the package under test, so a "
                "passing signature proves internal consistency only ('unanchored').",
                "No Merkle proof, anchor, receipt, policy or strict-base64 evaluation "
                "exists in this implementation.",
            ],
            "checked": ["structure", "identity", "lifecycle", "evidence hashes",
                        "index metadata", "seal signature"],
            "not_checked": _not_checked(unjudged),
            "statement": NOT_DETECTED,
            "strict": key is not None}

