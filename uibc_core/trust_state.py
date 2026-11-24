"""Which moves between the seven states are allowed, and what each one requires.

A vocabulary is only worth its size if a recipient can act on it. This module is
the half that was missing: `interop_result` says what a verdict *is*, this says
what may legally *follow* it when the same subject is judged again.

Two rules carry the weight:

1. **Nothing becomes `VERIFIED` without evidence.** Including a state that was
   `REVOKED` a minute ago -- that one additionally needs an explicit
   reinstatement flag, so un-revocation is a policy act and never a re-run.
2. **Bad news always travels.** A `VERIFIED` subject may fall to `INVALID`,
   `REVOKED`, `EXPIRED` or `INCONCLUSIVE` at any time with no special permission;
   the reverse direction is what gets checked. Silence is never an upgrade.

This does not decide *who* is right. It decides which sequences a conforming
implementation may emit, so two implementations can disagree about a subject
without disagreeing about whether the history was legal.
"""
from . import interop_result as ir

__all__ = [
    "TransitionError", "RULES", "allowed", "transition", "transitions_document",
]

# Reaching VERIFIED from these requires fresh evidence; from REVOKED it also
# requires `reinstated=True`, because lifting a revocation is a governance act.
_TO_VERIFIED_WITH_EVIDENCE = frozenset(
    {"INCONCLUSIVE", "UNRESOLVED", "UNSUPPORTED", "EXPIRED"})
_TO_VERIFIED_WITH_REINSTATEMENT = frozenset({"REVOKED"})
_TO_VERIFIED_NEVER = frozenset({"INVALID"})

# Bad news needs no permission. Losing certainty always beats keeping a label.
_DOWNGRADES = {
    "VERIFIED": frozenset({"INVALID", "REVOKED", "EXPIRED", "INCONCLUSIVE"}),
    "REVOKED": frozenset({"INVALID", "EXPIRED"}),
    "EXPIRED": frozenset({"INVALID", "REVOKED"}),
    "INCONCLUSIVE": frozenset({"INVALID", "REVOKED", "EXPIRED", "UNRESOLVED",
                               "UNSUPPORTED"}),
    "UNRESOLVED": frozenset({"INCONCLUSIVE", "UNSUPPORTED", "INVALID"}),
    "UNSUPPORTED": frozenset({"INCONCLUSIVE", "UNRESOLVED"}),
}

# Lateral moves: the method became readable, or the endpoint came back. Neither
# is news about the subject, so neither needs evidence.
_LATERAL = {
    "UNSUPPORTED": frozenset({"UNRESOLVED"}),
    "UNRESOLVED": frozenset({"UNSUPPORTED"}),
}


class TransitionError(Exception):
    """A sequence a conforming implementation must not emit."""


def _status(prior, new):
    if prior == new:
        return "no-op"
    if new == "VERIFIED":
        if prior in _TO_VERIFIED_NEVER:
            return "forbidden"
        if prior in _TO_VERIFIED_WITH_REINSTATEMENT:
            return "with_evidence_and_reinstatement"
        return "with_evidence"
    if new in _DOWNGRADES.get(prior, frozenset()):
        return "allowed"
    if new in _LATERAL.get(prior, frozenset()):
        return "allowed"
    return "forbidden"


RULES = {(a, b): _status(a, b) for a in ir.STATES for b in ir.STATES}


def allowed(prior, new):
    return RULES[(prior, new)] != "forbidden"


def transition(prior, new, evidence=None, reason=None, reinstated=False):
    """Return a transition record, or raise. No silent upgrades, no silent lifts."""
    if prior not in ir.STATES:
        raise ir.ResultError("prior state %r is not one of the seven" % (prior,))
    if new not in ir.STATES:
        raise ir.ResultError("new state %r is not one of the seven" % (new,))
    status = RULES[(prior, new)]
    if status == "forbidden":
        raise TransitionError(
            "%s -> %s is not an allowed transition; a subject that was %s cannot "
            "become %s (new evidence belongs to the new artifact, not the old one)"
            % (prior, new, prior, new))
    used_evidence = 0
    if status.startswith("with_evidence"):
        used_evidence = len(list(evidence or []))
        if used_evidence == 0:
            raise ir.ResultError(
                "%s -> VERIFIED requires evidence; a re-run is not a re-admission"
                % prior)
    if status == "with_evidence_and_reinstatement" and not reinstated:
        raise TransitionError(
            "REVOKED -> VERIFIED requires reinstated=True: lifting a revocation "
            "is a policy act, not a verification result")
    if new in ("REVOKED", "EXPIRED") and new != prior and not (reason or "").strip():
        raise ir.ResultError("%s requires a stated reason" % new)
    return {
        "prior": prior,
        "new": new,
        "rule": status,
        "evidence_used": used_evidence,
        "reinstated": bool(reinstated),
        "reason": reason,
    }


def transitions_document():
    """The whole 7x7 table, for docs and for byte comparison."""
    rows = []
    for prior in ir.STATES:
        for new in ir.STATES:
            rows.append({"prior": prior, "new": new, "rule": RULES[(prior, new)]})
    return {
        "states": list(ir.STATES),
        "rows": rows,
        "rules": {
            "no-op": "the same state again; no new claim is made",
            "allowed": "permitted without evidence (bad news travelling, or a lateral move)",
            "with_evidence": "requires at least one evidence item",
            "with_evidence_and_reinstatement": (
                "requires evidence and reinstated=True; lifting a revocation is a policy act"),
            "forbidden": "must not be emitted by a conforming implementation",
        },
        "note": ("This table constrains emitted sequences, not who is right. Two "
                 "implementations may disagree about a subject without "
                 "disagreeing about whether the history was legal."),
    }
