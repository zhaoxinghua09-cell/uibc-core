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
from . import SPEC_VERSION, VERIFIER_ID, __version__

REQUIRED_FILES = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]

EVIDENCE_TYPES = {
    "IDENTITY", "LIFECYCLE", "INPUT", "ACTION", "TOOL", "MEMORY", "OUTPUT",
    "EVALUATION", "HUMAN_DECISION", "VERIFICATION", "INCIDENT", "RETIREMENT",
}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def verify(package_dir: str) -> dict:
    """Verify a submission.uibc package directory. Returns a report dict."""
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

    result = "PASS" if ok else "FAIL"

    return {
        "verifier_id": VERIFIER_ID,
        "verifier_version": __version__,
        "spec_version": SPEC_VERSION,
        "result": result,
        "subject": manifest.get("agent_id"),
        "checks": checks,
        "root_algorithm": "sha256(canonical-json(sorted(content_hashes))) v0.1-provisional",
        # --- report discipline (archive SS16) ---
        "scope": "Structure, identity consistency, lifecycle state machine, evidence "
                 "content hashes, and evidence root of this submission package only.",
        "limitations": [
            "Signatures are not verified in v0.1 (field present but signing not ratified).",
            "Evidence Root algorithm is provisional (pending canonical serialization ratification).",
            "Timestamps are not independently anchored in v0.1.",
            "No behavioral evaluation is performed (Evaluation is out of verifier scope, archive SS15).",
        ],
        "checked": ["structure", "identity", "lifecycle", "evidence hashes", "evidence root"],
        "not_checked": ["cryptographic signatures", "external timestamp anchoring",
                        "behavioral evaluation", "memory fidelity/continuity"],
        "statement": ("No violation was detected within the observed evidence boundary."
                      if ok else "Violations were detected within the observed evidence boundary."),
    }
