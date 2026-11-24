"""Interoperability result vocabulary: seven states, one strict rule.

The seven states are the ones the UIBC interoperability initiative fixes, and
they exist because "failed" is not one condition:

    VERIFIED      evidence was sufficient and nothing contradicted it
    INVALID       evidence was sufficient and something contradicted it
    REVOKED       the subject's authority was withdrawn before this decision
    EXPIRED       the credential / attestation was outside its validity window
    INCONCLUSIVE  not enough evidence to decide either way
    UNSUPPORTED   this build has no rule for that method / credential type
    UNRESOLVED    the method is supported, but the registry did not answer

The rule that makes this vocabulary worth having:

    no claim reaches VERIFIED without evidence, and missing evidence is
    never treated as a successful verification.

`result()` raises rather than downgrading, because a silent downgrade hides the
caller's bug at the exact place a reviewer would want to see it.

`from_verify_report()` maps this repository's verifier report (PASS / FAIL /
INCONCLUSIVE plus per-check names) onto the seven states, so an internal run can
be republished in a form another implementation can compare against.
"""

import hashlib
import re

__all__ = [
    "STATES",
    "ResultError",
    "EVIDENCE_REQUIRED",
    "result",
    "from_verify_report",
    "is_verified",
    "states_document",
]

STATES = (
    "VERIFIED",
    "INVALID",
    "REVOKED",
    "EXPIRED",
    "INCONCLUSIVE",
    "UNSUPPORTED",
    "UNRESOLVED",
)

#: fields every evidence entry must carry before it may support a VERIFIED claim
EVIDENCE_REQUIRED = ("id", "type", "issuer", "digest")

_DIGEST_RE = re.compile(r"^(sha256|sha384|sha512):[0-9a-f]{64,128}$")


class ResultError(ValueError):
    """The result document would have claimed more than the evidence allows."""


def _check_evidence(evidence):
    cleaned = []
    for entry in evidence or []:
        if not isinstance(entry, dict):
            raise ResultError("evidence entry must be an object, got %r" % (entry,))
        missing = [f for f in EVIDENCE_REQUIRED if not entry.get(f)]
        if missing:
            raise ResultError("evidence entry %r is missing %s"
                              % (entry.get("id"), ", ".join(missing)))
        digest = entry["digest"]
        if not _DIGEST_RE.match(digest):
            raise ResultError("evidence %r digest must be <alg>:<lowercase hex>, got %r"
                              % (entry["id"], digest))
        item = {f: entry[f] for f in EVIDENCE_REQUIRED}
        for optional in ("subject", "issued_at", "expires_at", "method",
                         "status", "verification_result", "provenance", "scope"):
            if entry.get(optional) is not None:
                item[optional] = entry[optional]
        cleaned.append(item)
    return cleaned


def result(state, subject, evidence=None, method=None, detail="",
           scope=None, verified_at=None):
    """Build one result document, or refuse to.

    `VERIFIED` is the only state with an evidence precondition, and it is
    enforced here rather than documented: an empty or malformed evidence list
    raises, so a caller cannot publish VERIFIED by forgetting to attach proof.
    """
    if state not in STATES:
        raise ResultError("state %r is not one of %s" % (state, ", ".join(STATES)))
    if not subject:
        raise ResultError("a result without a subject names nothing")
    evidence = _check_evidence(evidence)
    if state == "VERIFIED" and not evidence:
        raise ResultError(
            "VERIFIED needs at least one evidence entry (%s); an unevidenced "
            "verification is at best INCONCLUSIVE"
            % ", ".join(EVIDENCE_REQUIRED))
    if state in ("REVOKED", "EXPIRED") and not detail:
        raise ResultError("%s must say what was withdrawn or when it lapsed" % state)
    doc = {
        "state": state,
        "subject": subject,
        "evidence": evidence,
        "detail": detail,
    }
    if method:
        doc["method"] = method
    if scope:
        doc["scope"] = scope
    if verified_at:
        doc["verified_at"] = verified_at
    return doc


def is_verified(doc):
    """True only for a VERIFIED document that still carries its evidence."""
    return (isinstance(doc, dict)
            and doc.get("state") == "VERIFIED"
            and bool(_check_evidence(doc.get("evidence"))))


# --------------------------------------------------------------------------- #
# mapping this repository's own verifier report onto the seven states
# --------------------------------------------------------------------------- #
_REVOCATION = ("revocation",)
_EXPIRY = ("expire", "expiry", "expires", "validity", "freshness", "stale")
_UNSUPPORTED = ("unsupported", "no published", "method")
_UNRESOLVED = ("resolve", "resolution", "unreachable", "fetcher")


def _failing_names(report):
    names = []
    for check in report.get("checks") or []:
        if check.get("result") in ("FAIL", "INCONCLUSIVE"):
            names.append("%s %s %s" % (check.get("id", ""), check.get("name", ""),
                                       check.get("detail", "")))
    return " | ".join(names).lower()


def from_verify_report(report, evidence=None, verified_at=None):
    """Republish a UIBC verifier report in the seven-state vocabulary.

    Mapping is deliberately directional: an internal FAIL never becomes
    something softer, and PASS becomes VERIFIED only if the caller supplies the
    evidence entries that made it pass.
    """
    if not isinstance(report, dict):
        raise ResultError("report must be an object")
    internal = report.get("result")
    if internal not in ("PASS", "FAIL", "INCONCLUSIVE"):
        raise ResultError("report result %r is not PASS / FAIL / INCONCLUSIVE"
                          % (internal,))
    names = _failing_names(report)
    subject = report.get("subject") or ""
    method = None
    custody = report.get("key_custody")
    if isinstance(custody, str) and custody.startswith("did:"):
        method = custody
    if internal == "PASS":
        state, detail = "VERIFIED", "all checks resolved and none contradicted"
    elif internal == "INCONCLUSIVE":
        state = "INCONCLUSIVE"
        detail = "not enough evidence to decide: %s" % (names or "unstated")
    elif any(w in names for w in _REVOCATION):
        state, detail = "REVOKED", "revocation check failed: %s" % names
    elif any(w in names for w in _EXPIRY):
        state, detail = "EXPIRED", "validity window failed: %s" % names
    elif any(w in names for w in _UNSUPPORTED):
        state = "UNSUPPORTED"
        detail = "no rule for this method in this build: %s" % names
    elif any(w in names for w in _UNRESOLVED):
        state = "UNRESOLVED"
        detail = "supported method, no answer from the registry: %s" % names
    else:
        state, detail = "INVALID", "evidence contradicted the claim: %s" % names
    return result(state, subject or "(unnamed subject)", evidence=evidence,
                  method=method, detail=detail, verified_at=verified_at,
                  scope=report.get("scope"))


def states_document():
    """The vocabulary as data, so a schema file can be diffed against it."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "UIBC interoperability verification result",
        "description": "One identity / trust decision, in seven states. "
                       "VERIFIED requires evidence; absence of evidence is "
                       "INCONCLUSIVE and never a pass.",
        "type": "object",
        "additionalProperties": False,
        "required": ["state", "subject", "evidence", "detail"],
        "properties": {
            "state": {"enum": list(STATES)},
            "subject": {"type": "string", "minLength": 1},
            "method": {"type": "string"},
            "detail": {"type": "string"},
            "scope": {"type": "string"},
            "verified_at": {"type": "string"},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": list(EVIDENCE_REQUIRED),
                    "properties": {
                        "id": {"type": "string", "minLength": 1},
                        "type": {"type": "string", "minLength": 1},
                        "issuer": {"type": "string", "minLength": 1},
                        "digest": {"type": "string",
                                   "pattern": "^(sha256|sha384|sha512):[0-9a-f]{64,128}$"},
                        "subject": {"type": "string"},
                        "issued_at": {"type": "string"},
                        "expires_at": {"type": "string"},
                        "method": {"type": "string"},
                        "status": {"type": "string"},
                        "verification_result": {"type": "string"},
                        "provenance": {"type": "string"},
                        "scope": {"type": "string"},
                    },
                },
            },
        },
        "allOf": [
            {"if": {"properties": {"state": {"const": "VERIFIED"}},
                    "required": ["state"]},
             "then": {"properties": {"evidence": {"minItems": 1}}}},
            {"if": {"properties": {"state": {"enum": ["REVOKED", "EXPIRED"]}},
                    "required": ["state"]},
             "then": {"properties": {"detail": {"minLength": 1}}}},
        ],
    }


def digest_of(data):
    """sha256 digest string for a bytes payload, in the form the schema expects."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return "sha256:" + hashlib.sha256(data).hexdigest()
