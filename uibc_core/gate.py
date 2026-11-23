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

import base64
import hashlib
import hmac
import json
import os
import time

from . import ed25519 as _ed
from .canonical import hash_file  # noqa: F401  (re-exported for tools)
from .coverage_feed import fetch as _fetch_coverage, ChannelError as _CoverageChannelError, \
    DEFAULT_TIMEOUT_S as _CHANNEL_TIMEOUT_S
from .signing import (ALGORITHM, ALGORITHM_ED25519, ed_key_id, key_id)  # noqa: F401
from .verify import verify


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _canonical_sig_payload(body: dict) -> bytes:
    core = {k: v for k, v in body.items() if k != "signature"}
    return json.dumps(core, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False).encode("utf-8")


def revocation_body_sha256(body: dict) -> str:
    """sha256 over the canonical revocation body (everything except `signature`).

    One implementation, called by the signer, the gate and the receipt
    recomputation. Two copies of this canonicalization is exactly how a valid
    signature stops verifying (measured, #319): the signer signed four fields
    while the verifier canonicalized six.
    """
    return hashlib.sha256(_canonical_sig_payload(body)).hexdigest()


def _check_revocation(rev: dict, manifest: dict, key, pubkey=None) -> tuple:
    """Return (status, detail). status in {"REVOKED", "MISMATCH", "UNVERIFIABLE", "MALFORMED"}.

    Two signature algorithms are accepted, and which one is used has to be
    stated in the file rather than guessed:

      * ``HMAC-SHA256`` (v0.2) - symmetric, needs ``--key``. Only the owner can
        verify, so a third party cannot check a revocation at all.
      * ``Ed25519`` (v0.3) - asymmetric, needs the signer's ``--pubkey``. This
        is the one that lets somebody who never held the owner's secret check
        that the owner really revoked the package.

    Anything else - unknown algorithm, missing key material, signature that
    does not verify - is UNVERIFIABLE, which HOLDs. It is never treated as
    "no revocation present".
    """
    for field in ("revocation_id", "target_root", "signature", "revoked_at"):
        if not rev.get(field):
            return "MALFORMED", f"revocation missing field {field!r}"
    if rev.get("target_root") != manifest.get("evidence_root"):
        return "MISMATCH", ("revocation targets a different evidence_root: "
                            f"{rev.get('target_root')!r} != {manifest.get('evidence_root')!r}")
    algorithm = rev.get("algorithm", ALGORITHM)
    if algorithm == ALGORITHM:
        if key is None:
            return "UNVERIFIABLE", ("revocation present but no --key provided: "
                                    "cannot verify (HOLD, never silently trusted)")
        if not _verify_body(key, rev):
            return "UNVERIFIABLE", "revocation signature invalid for supplied key"
        return "REVOKED", f"valid revocation by key_id {rev.get('key_id', '?')}"
    if algorithm == ALGORITHM_ED25519:
        if pubkey is None:
            return "UNVERIFIABLE", ("Ed25519-signed revocation present but no --pubkey "
                                    "provided: cannot verify (HOLD, never silently trusted)")
        if rev.get("key_id") and rev["key_id"] != ed_key_id(pubkey):
            return "UNVERIFIABLE", ("revocation key_id does not match the pinned public "
                                    f"key ({rev.get('key_id', '?')})")
        try:
            sig = base64.b64decode(rev.get("signature", ""), validate=True)
        except Exception:
            return "UNVERIFIABLE", "revocation signature is not valid base64"
        if not _ed.verify(pubkey, _canonical_sig_payload(rev), sig):
            return "UNVERIFIABLE", "revocation signature invalid for the pinned public key"
        return "REVOKED", ("valid Ed25519 revocation by key_id "
                           f"{rev.get('key_id', ed_key_id(pubkey))}")
    return "UNVERIFIABLE", f"unknown revocation algorithm {algorithm!r}"



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


def _parse_iso(value):
    """ISO-8601 with a timezone -> aware datetime, or None."""
    from datetime import datetime
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return parsed if parsed.tzinfo is not None else None


def _check_coverage(cov: dict, manifest: dict, key=None, pubkey=None,
                    now=None, max_age_s=None, remembered_seq=None) -> tuple:
    """Check a signed "no revocation as of issued_at" statement.

    Return (status, detail). status in
    {"VERIFIED", "MALFORMED", "MISMATCH", "UNVERIFIABLE", "STALE", "ROLLBACK"}.

    Verification comes before freshness: an unsigned statement is UNVERIFIABLE
    no matter how new it is. Freshness is then two independent refusals - the
    statement is too old to rely on (STALE), or its ``sequence`` went backwards
    against what this verifier already saw (ROLLBACK).

    What this cannot do: the statement is signed by the same holder whose
    revocations it denies, so it is self-attestation. It says "as of that
    moment I had not revoked this package", not "it is not revoked now".
    """
    for field in ("coverage_id", "target_root", "issued_at", "sequence",
                  "no_revocation", "key_id", "algorithm", "signature"):
        if cov.get(field) in (None, "", []):
            return "MALFORMED", f"coverage statement missing field {field!r}"
    if cov.get("no_revocation") is not True:
        return "MALFORMED", "no_revocation must be true (a coverage statement only denies)"
    if _parse_iso(cov.get("issued_at")) is None:
        return "MALFORMED", "issued_at is not ISO-8601 with a timezone"
    seq = cov.get("sequence")
    if not isinstance(seq, int) or isinstance(seq, bool) or seq < 1:
        return "MALFORMED", "sequence must be an integer >= 1"
    if cov.get("target_root") != manifest.get("evidence_root"):
        return "MISMATCH", ("coverage targets a different evidence_root: "
                            f"{cov.get('target_root')!r}")

    algorithm = cov.get("algorithm")
    if algorithm == ALGORITHM:
        if key is None:
            return "UNVERIFIABLE", ("coverage present but no --key provided: "
                                    "cannot verify (HOLD, never silently trusted)")
        if not _verify_body(key, cov):
            return "UNVERIFIABLE", "coverage signature invalid for supplied key"
    elif algorithm == ALGORITHM_ED25519:
        if pubkey is None:
            return "UNVERIFIABLE", ("Ed25519-signed coverage present but no --pubkey "
                                    "provided: cannot verify (HOLD, never silently trusted)")
        if cov.get("key_id") and cov["key_id"] != ed_key_id(pubkey):
            return "UNVERIFIABLE", ("coverage key_id does not match the pinned public "
                                    f"key ({cov.get('key_id', '?')})")
        try:
            sig = base64.b64decode(cov.get("signature", ""), validate=True)
        except Exception:
            return "UNVERIFIABLE", "coverage signature is not valid base64"
        if not _ed.verify(pubkey, _canonical_sig_payload(cov), sig):
            return "UNVERIFIABLE", "coverage signature invalid for the pinned public key"
    else:
        return "UNVERIFIABLE", f"unknown coverage algorithm {algorithm!r}"

    if remembered_seq is not None and seq < remembered_seq:
        return "ROLLBACK", (f"sequence {seq} < remembered "
                            f"{remembered_seq} (an older statement is not newer news)")
    if max_age_s is not None:
        from datetime import datetime, timezone
        issued = _parse_iso(cov["issued_at"])
        now_dt = datetime.fromtimestamp(now if now is not None else time.time(), timezone.utc)
        age = (now_dt - issued).total_seconds()
        if age > max_age_s:
            return "STALE", (f"issued_at {cov['issued_at']} is {int(age)}s "
                             f"older than the allowed {int(max_age_s)}s")
    return "VERIFIED", f"coverage verified (sequence={seq}, issued_at={cov['issued_at']})"



def _coverage_state_get(path: str, target_root) -> int:
    """Largest coverage sequence this verifier has already accepted, or None."""
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            state = json.load(f)
        entry = (state.get("targets") or {}).get(target_root) or {}
        seq = entry.get("sequence")
        return seq if isinstance(seq, int) and not isinstance(seq, bool) else None
    except (OSError, ValueError):
        return None


def _coverage_state_put(path: str, target_root, sequence, issued_at):
    """Remember the last accepted sequence. Atomic: tmp + replace, never partial."""
    import tempfile
    state = {"schema": "uibc-coverage-state/1", "targets": {}}
    if os.path.isfile(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            if isinstance(loaded, dict) and isinstance(loaded.get("targets"), dict):
                state["targets"] = loaded["targets"]
        except (OSError, ValueError):
            state["targets"] = {}
    prev = (state["targets"].get(target_root) or {}).get("sequence")
    if isinstance(prev, int) and not isinstance(prev, bool) and prev >= sequence:
        return
    state["targets"][target_root] = {"sequence": sequence, "issued_at": issued_at}
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".coverage-state-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, sort_keys=True, ensure_ascii=False)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def gate(package_dir: str, key: bytes = None,
         revocation_path: str = None, dispute_path: str = None,
         pubkey: bytes = None, require_revocation_coverage: bool = False,
         coverage_path: str = None, coverage_max_age_s: float = None,
         coverage_state_path: str = None, now: float = None,
         coverage_url: str = None, coverage_channel_timeout_s: float = None) -> dict:
    """Run verify, then apply governance overlays. Returns a gate report.

    Exit-code contract (CLI layer):
        ALLOW           -> 0
        DENY            -> 2   (blocking: mirrors poka-yoke hook semantics)
        HOLD            -> 3   (INCONCLUSIVE: human decision required)

    ``require_revocation_coverage`` is the fail-closed form of "I have no
    revocation overlay": without it, a caller with no overlay gets ALLOW,
    because the gate cannot see a revocation it was never given. With it, an
    absent overlay is HOLD (exit 3) instead of ALLOW - absence is never read as
    "nothing was revoked". It does not make the absence *verified*; it only
    stops the absence from being silently treated as a clean state.
    """
    report = verify(package_dir, key=key, pubkey=pubkey)
    manifest = _load_json(os.path.join(package_dir, "manifest.json")) \
        if os.path.isfile(os.path.join(package_dir, "manifest.json")) else {}

    revocation = {"status": "NONE", "detail": "no revocation supplied"}
    if revocation_path:
        try:
            revocation = dict(zip(("status", "detail"),
                                  _check_revocation(_load_json(revocation_path), manifest,
                                                    key, pubkey)))
        except (OSError, ValueError):
            revocation = {"status": "MALFORMED", "detail": "revocation file unreadable/invalid JSON"}

    dispute = {"status": "NONE", "detail": "no dispute supplied"}
    if dispute_path:
        try:
            dispute = dict(zip(("status", "detail"),
                               _check_dispute(_load_json(dispute_path), manifest)))
        except (OSError, ValueError):
            dispute = {"status": "MALFORMED", "detail": "dispute file unreadable/invalid JSON"}

    coverage = {"status": "ABSENT", "detail": "no coverage statement supplied"}
    cov = None
    if coverage_path:
        try:
            cov = _load_json(coverage_path)
        except (OSError, ValueError):
            coverage = {"status": "MALFORMED",
                        "detail": "coverage file unreadable/invalid JSON"}
    elif coverage_url:
        try:
            cov = _fetch_coverage(
                coverage_url,
                timeout=(coverage_channel_timeout_s
                         if coverage_channel_timeout_s is not None else _CHANNEL_TIMEOUT_S))
        except _CoverageChannelError as exc:
            # an unreachable feed is conspicuous, not clean: HOLD, never ALLOW
            coverage = {"status": "UNREACHABLE", "detail": str(exc)}
    if cov is not None:
        remembered = None
        if coverage_state_path:
            remembered = _coverage_state_get(coverage_state_path,
                                             cov.get("target_root"))
        coverage = dict(zip(("status", "detail"),
                            _check_coverage(cov, manifest, key=key, pubkey=pubkey,
                                            now=now, max_age_s=coverage_max_age_s,
                                            remembered_seq=remembered)))
        if coverage["status"] == "VERIFIED" and coverage_state_path:
            _coverage_state_put(coverage_state_path, cov.get("target_root"),
                                cov.get("sequence"), cov.get("issued_at"))

    # decision cascade - order is normative (governance section 7)
    if revocation["status"] == "REVOKED":
        decision, reason = "DENY", "package is revoked by valid owner revocation"
    elif report["result"] == "FAIL":
        decision, reason = "DENY", "verifier FAIL: " + \
            "; ".join(c["id"] for c in report["checks"] if c["result"] == "FAIL")
    elif revocation["status"] in ("MALFORMED", "MISMATCH", "UNVERIFIABLE"):
        decision, reason = "HOLD", f"revocation {revocation['status']}: {revocation['detail']}"
    elif coverage["status"] in ("MALFORMED", "MISMATCH", "UNVERIFIABLE", "STALE",
                                "ROLLBACK", "UNREACHABLE"):
        decision, reason = "HOLD", f"coverage {coverage['status']}: {coverage['detail']}"
    elif revocation["status"] == "NONE" and coverage["status"] == "ABSENT" \
            and require_revocation_coverage:
        decision = "HOLD"
        reason = ("revocation coverage absent: caller demanded coverage and neither a "
                  "coverage statement nor a revocation overlay was supplied (HOLD, "
                  "never read as 'nothing was revoked')")
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
        if coverage["status"] == "VERIFIED":
            reason += "; " + coverage["detail"]

    return {
        "gate_version": "0.1.0",
        "decision": decision,
        "reason": reason,
        "verify_result": report["result"],
        "revocation": revocation,
        "coverage": coverage,
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
