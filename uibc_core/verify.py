"""Verifier (archive SS16): PASS / FAIL / INCONCLUSIVE, scoped report.

Report discipline (archive SS16/SS17):
  - report MUST state scope, limitations, checked, not_checked
  - result is a scoped proof: "No unauthorized action was detected within the
    observed evidence boundary" - never a claim of absolute trustworthiness.
"""

import json
import os

from .canonical import evidence_root, hash_file
from .lifecycle import validate_lifecycle
from .signing import (ALGORITHM, ALGORITHM_ED25519, b64decode_strict,
                      ed_key_id, ed_seal_verify, key_id, seal_verify)
from . import SPEC_VERSION, VERIFIER_ID, __version__

REQUIRED_FILES = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]

EVIDENCE_TYPES = {
    "IDENTITY", "LIFECYCLE", "INPUT", "ACTION", "TOOL", "MEMORY", "OUTPUT",
    "EVALUATION", "HUMAN_DECISION", "VERIFICATION", "INCIDENT", "RETIREMENT",
}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify(package_dir: str, key: bytes = None, pubkey: bytes = None) -> dict:
    """Verify a submission.uibc package directory. Returns a report dict.

    Seal v0.3 verdict semantics (docs/verdict-and-seal-semantics.md):

    - The top-level result is three-valued: FAIL if any check FAILs, else
      INCONCLUSIVE if any check is INCONCLUSIVE, else PASS. An unverifiable
      seal can therefore no longer hide under a top-level PASS (the v0.2
      behaviour an external review flagged in 2026-11).
    - An Ed25519 seal is verified PUBLICLY in every mode: the public key
      travels with the package, so anyone can check provenance.
      ``pubkey`` optionally pins the expected public key - a substituted
      key then FAILS S6.
    - key=...  : strict owner mode for HMAC seals. A missing/invalid seal
               or a key_id that does not match the provided owner key
               FAILS S6. This is the mode that closes the 'malicious'
               self-consistent forgery for symmetric seals.
    - An unsigned package is INCONCLUSIVE at S6 in open mode: its evidence
      chain is internally consistent, but its provenance is unattested.
    """
    checks = []
    ok = True

    def record(cid, name, passed, detail=""):
        nonlocal ok
        checks.append({"id": cid, "name": name, "result": "PASS" if passed else "FAIL", "detail": detail})
        if not passed:
            ok = False

    # S1 structure
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(package_dir, f))]
    record("S1", "package structure", not missing,
           f"missing: {missing}" if missing else "all required files present")

    manifest = _load_json(os.path.join(package_dir, "manifest.json")) if not missing else {}
    identity = _load_json(os.path.join(package_dir, "identity.json")) if not missing else {}
    lifecycle = _load_json(os.path.join(package_dir, "lifecycle.json")) if not missing else {}
    index = _load_json(os.path.join(package_dir, "evidence", "index.json")) if not missing else {"entries": []}

    # S2 identity consistency
    agent_id_ok = bool(identity.get("agent_id")) and \
        manifest.get("agent_id") == identity.get("agent_id")
    record("S2", "identity consistency", agent_id_ok,
           f"identity.agent_id={identity.get('agent_id')!r}, manifest.agent_id={manifest.get('agent_id')!r}")

    # S3 lifecycle state machine + chain
    events = lifecycle.get("events", [])
    l_errors = validate_lifecycle(events)
    record("S3", "lifecycle state machine", not l_errors, "; ".join(l_errors) or f"{len(events)} events, chain valid")

    # S4 evidence integrity: recompute content hashes from files
    entries = index.get("entries", [])
    s4_failures = []
    recomputed_hashes = []
    for e in entries:
        p = os.path.join(package_dir, "evidence", e.get("path", ""))
        if not os.path.isfile(p):
            s4_failures.append(f"missing file {e.get('path')!r}")
            continue
        actual = hash_file(p)
        recomputed_hashes.append(actual)
        if actual != e.get("content_hash"):
            s4_failures.append(f"hash mismatch on {e.get('path')!r}")
        if e.get("type") not in EVIDENCE_TYPES:
            s4_failures.append(f"unknown evidence type {e.get('type')!r}")
    record("S4", "evidence integrity", not s4_failures,
           f"{len(entries)} entries checked; " + ("; ".join(s4_failures) if s4_failures else "all hashes match"))

    # S5 evidence root
    if entries and not s4_failures:
        computed = evidence_root(recomputed_hashes)
        root_ok = computed == manifest.get("evidence_root")
        record("S5", "evidence root", root_ok,
               f"computed={computed}, manifest={manifest.get('evidence_root')}")
    else:
        ok = False
        checks.append({"id": "S5", "name": "evidence root", "result": "INCONCLUSIVE",
                       "detail": "skipped: evidence missing or S4 failed"})

    # S6 seal signature (v0.3: HMAC owner seals + Ed25519 public seals)
    seal_path = os.path.join(package_dir, "signatures", "seal.json")
    has_seal = os.path.isfile(seal_path) and not missing
    assurance = "unattested"
    if has_seal:
        seal = _load_json(seal_path)
        algo = seal.get("algorithm")
        if algo == ALGORITHM_ED25519:
            pub = b64decode_strict(seal.get("public_key"))
            if pub is None or len(pub) != 32:
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "Ed25519 seal records no valid public_key"})
            elif seal.get("key_id") != ed_key_id(pub):
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "key_id does not match the recorded public key "
                                         "(seal metadata inconsistent)"})
            elif pubkey is not None and bytes(pubkey) != pub:
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "public key does not match the pinned --pubkey "
                                         "(possible key substitution or wrong pin)"})
            elif key is not None:
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "seal algorithm is Ed25519; the provided --key is an "
                                         "HMAC owner key and cannot check it - re-run without "
                                         "--key, or pin the signer with --pubkey"})
            elif not ed_seal_verify(pub, identity, manifest, seal.get("signature", "")):
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "Ed25519 signature invalid: identity/manifest do not "
                                         "match the seal"})
            else:
                assurance = "public-key"
                checks.append({"id": "S6", "name": "seal signature", "result": "PASS",
                               "detail": f"Ed25519 seal valid (key_id {ed_key_id(pub)[:16]}...) - "
                                         "third-party verifiable, no secret involved"})
        elif algo == ALGORITHM:
            if key is not None:
                kid = key_id(key)
                if seal.get("key_id") != kid:
                    ok = False
                    checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                                   "detail": "key mismatch: seal was not created by this key "
                                             "(possible key substitution or wrong key)"})
                elif not seal_verify(key, identity, manifest, seal.get("signature", "")):
                    ok = False
                    checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                                   "detail": "signature invalid: identity/manifest do not match the seal"})
                else:
                    assurance = "owner-key"
                    checks.append({"id": "S6", "name": "seal signature", "result": "PASS",
                                   "detail": f"HMAC-SHA256 seal valid (key_id {kid[:16]}...)"})
            else:
                checks.append({"id": "S6", "name": "seal signature", "result": "INCONCLUSIVE",
                               "detail": "HMAC seal present but no verification key provided "
                                         "(--key); symmetric seals cannot be checked publicly - "
                                         "an Ed25519 seal can"})
        else:
            ok = False
            checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                           "detail": f"unknown seal algorithm {algo!r}"})
    elif key is not None:
        ok = False
        checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                       "detail": "strict mode (--key): package is unsigned - "
                                 "owner demands a sealed submission"})
    else:
        checks.append({"id": "S6", "name": "seal signature", "result": "INCONCLUSIVE",
                       "detail": "package unsigned: evidence chain is internally consistent "
                                 "but provenance is unattested"})

    # Three-valued top-level verdict (seal v0.3): a FAIL anywhere fails the
    # package; an unresolved INCONCLUSIVE anywhere caps the verdict at
    # INCONCLUSIVE - PASS is reserved for packages every check resolved.
    _results = [c["result"] for c in checks]
    if "FAIL" in _results:
        result = "FAIL"
    elif "INCONCLUSIVE" in _results:
        result = "INCONCLUSIVE"
    else:
        result = "PASS"

    return {
        "verifier_id": VERIFIER_ID,
        "verifier_version": __version__,
        "spec_version": SPEC_VERSION,
        "result": result,
        "subject": manifest.get("agent_id"),
        "checks": checks,
        "root_algorithm": "sha256(canonical-json(sorted(content_hashes))) v0.1-provisional",
        "assurance": assurance,
        # --- report discipline (archive SS16) ---
        "scope": "Structure, identity consistency, lifecycle state machine, evidence "
                 "content hashes, evidence root, and the seal signature of this "
                 "submission package only. Ed25519 seals are verified publicly in "
                 "every mode; HMAC seals only in strict --key mode.",
        "limitations": [
            "HMAC-SHA256 seals (v0.2) are symmetric: verification requires the owner "
            "key. Ed25519 seals (v0.3) are third-party verifiable with the public key "
            "recorded in the seal.",
            "Key substitution is detectable only when verifying with the owner key "
            "(--key), a pinned public key (--pubkey), or out-of-band key pinning.",
            "Evidence Root algorithm is provisional (pending canonical serialization ratification).",
            "Timestamps are not independently anchored.",
            "Lifecycle event signatures (event.signature) are not ratified and not verified.",
            "No behavioral evaluation is performed (Evaluation is out of verifier scope, archive SS15).",
        ],
        "checked": ["structure", "identity", "lifecycle", "evidence hashes", "evidence root"]
                   + (["seal signature"] if has_seal or key is not None else []),
        "not_checked": ["lifecycle event signatures",
                        "external timestamp anchoring",
                        "behavioral evaluation", "memory fidelity/continuity"],
        "statement": ("No violation was detected within the observed evidence boundary."
                      if result == "PASS" else
                      "Violations were detected within the observed evidence boundary."
                      if result == "FAIL" else
                      "No violation was detected, but verification is incomplete: at "
                      "least one check could not be resolved within the observed "
                      "evidence boundary."),
    }
