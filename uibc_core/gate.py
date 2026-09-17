"""Gate (archive: LGD third principle - Gates). verify CHECKS, gate DECIDES.

Decision rules (docs/governance.md section 7, v0.1 PROPOSAL):

  revocation valid            -> DENY            (exit 2)   [R2]
  verify FAIL                 -> DENY            (exit 2)
  anything unverifiable       -> HOLD            (exit 3)
  verify PASS + valid dispute -> ALLOW_DISPUTED  (exit 0, flagged)
  verify PASS clean           -> ALLOW           (exit 0)

Boundary (Dispute vs Revocation, governance section 3):
  Dispute    = third party says "I object"  -> flag, never blocks
  Revocation = owner says "this is void"    -> must verify, then blocks

Honest scope:
  - With HMAC (v0.2) only the owner key holder can verify a revocation.
    Without the key a revocation is INCONCLUSIVE -> HOLD, never silently
    ignored and never trusted.
  - gate() never mutates the package. Read-only, like verify().
"""

import hmac
import json
import os

from .canonical import hash_file  # noqa: F401  (re-exported for tools)
from .signing import ALGORITHM, key_id  # noqa: F401  (key_id re-exported for CLI)
from .verify import verify


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _canonical_sig_payload(body: dict) -> bytes:
    core = {k: v for k, v in body.items() if k != "signature"}
    return json.dumps(core, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def _check_revocation(rev: dict, manifest: dict, key) -> tuple:
    """Return (status, detail). status in {"REVOKED", "MISMATCH", "UNVERIFIABLE", "MALFORMED"}."""
    for field in ("revocation_id", "target_root", "signature", "revoked_at"):
        if not rev.get(field):
            return "MALFORMED", f"revocation missing field {field!r}"
    if rev.get("target_root") != manifest.get("evidence_root"):
        return "MISMATCH", ("revocation targets a different evidence_root: "
                            f"{rev.get('target_root')!r} != {manifest.get('evidence_root')!r}")
    if rev.get("algorithm", ALGORITHM) != ALGORITHM:
        return "UNVERIFIABLE", f"unknown revocation algorithm {rev.get('algorithm')!r}"
    if key is None:
        return "UNVERIFIABLE", ("revocation present but no --key provided: "
                               "cannot verify (HOLD, never silently trusted)")
    if not _verify_body(key, rev):
        return "UNVERIFIABLE", "revocation signature invalid for supplied key"
    return "REVOKED", f"valid revocation by key_id {rev.get('key_id', '?')}"


def _verify_body(key, rev: dict) -> bool:
    """HMAC over the canonical revocation body (without 'signature')."""
    try:
        sig = rev.get("signature", "")
        mac = hmac.new(key, _canonical_sig_payload(rev),
                       __import__("hashlib").sha256).digest()
        import base64
        return hmac.compare_digest(mac, base64.b64decode(sig))
    except Exception:
        return False


def _check_dispute(disp: dict, manifest: dict) -> tuple:
    """Return (status, detail). status in {"DISPUTED", "MISMATCH", "MALFORMED"}."""
    for field in ("dispute_id", "target_root", "reason_code", "disputer"):
        if not disp.get(field):
            return "MALFORMED", f"dispute missing field {field!r}"
    if disp.get("target_root") != manifest.get("evidence_root"):
        return "MISMATCH", ("dispute targets a different evidence_root: "
                            f"{disp.get('target_root')!r}")
    return "DISPUTED", f"dispute {disp.get('dispute_id')} ({disp.get('reason_code')})"


def gate(package_dir: str, key: bytes = None,
         revocation_path: str = None, dispute_path: str = None) -> dict:
    """Run verify, then apply governance overlays. Returns a gate report.

    Exit-code contract (CLI layer):
        ALLOW           -> 0
        DENY            -> 2   (blocking: mirrors poka-yoke hook semantics)
        HOLD            -> 3   (INCONCLUSIVE: human decision required)
    """
    report = verify(package_dir, key=key)
    manifest = _load_json(os.path.join(package_dir, "manifest.json")) \
        if os.path.isfile(os.path.join(package_dir, "manifest.json")) else {}

    revocation = {"status": "NONE", "detail": "no revocation supplied"}
    if revocation_path:
        try:
            revocation = dict(zip(("status", "detail"),
                                  _check_revocation(_load_json(revocation_path), manifest, key)))
        except (OSError, ValueError):
            revocation = {"status": "MALFORMED", "detail": "revocation file unreadable/invalid JSON"}

    dispute = {"status": "NONE", "detail": "no dispute supplied"}
    if dispute_path:
        try:
            dispute = dict(zip(("status", "detail"),
                               _check_dispute(_load_json(dispute_path), manifest)))
        except (OSError, ValueError):
            dispute = {"status": "MALFORMED", "detail": "dispute file unreadable/invalid JSON"}

    # decision cascade - order is normative (governance section 7)
    if revocation["status"] == "REVOKED":
        decision, reason = "DENY", "package is revoked by valid owner revocation"
    elif report["result"] == "FAIL":
        decision, reason = "DENY", "verifier FAIL: " + \
            "; ".join(c["id"] for c in report["checks"] if c["result"] == "FAIL")
    elif revocation["status"] in ("MALFORMED", "MISMATCH", "UNVERIFIABLE"):
        decision, reason = "HOLD", f"revocation {revocation['status']}: {revocation['detail']}"
    elif dispute["status"] in ("MALFORMED", "MISMATCH"):
        decision, reason = "HOLD", f"dispute {dispute['status']}: {dispute['detail']}"
    elif report["result"] == "INCONCLUSIVE" or \
            any(c["result"] == "INCONCLUSIVE" for c in report["checks"]) or \
            dispute["status"] == "DISPUTED":
        # disputed packages are not auto-denied, but a human must look
        decision = "HOLD" if report["result"] != "PASS" else "ALLOW_DISPUTED"
        reason = ("dispute registered: " + dispute["detail"]) if dispute["status"] == "DISPUTED" \
            else "verifier INCONCLUSIVE components present"
    else:
        decision, reason = "ALLOW", "verify PASS, no revocation, no dispute"

    return {
        "gate_version": "0.1.0",
        "decision": decision,
        "reason": reason,
        "verify_result": report["result"],
        "revocation": revocation,
        "dispute": dispute,
        "exit_code": {"ALLOW": 0, "ALLOW_DISPUTED": 0, "DENY": 2, "HOLD": 3}[decision],
        "verify_report": report,
        "scope": "Same evidence boundary as verify(), plus revocation/dispute "
                 "overlays explicitly supplied on the command line. gate() does "
                 "not discover governance files on its own - an operator must "
                 "name them, so the decision input is always explicit.",
        "limitations": report["limitations"] + [
            "gate() is a decision layer, not an enforcement layer: it returns "
            "exit codes, it cannot stop a determined caller from ignoring them.",
        ],
    }
