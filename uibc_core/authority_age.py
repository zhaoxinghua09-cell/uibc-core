"""Authority answer age, measured against a bound — the check WG0 #71 R1 asks for.

Why this module exists
----------------------
Requirement 1 in `fg-tida-wg0/use-cases#71` asks for two things a record can
carry: the time the status source gave its answer, and the age of that answer
at the moment the decision was made. `freshness.py` in this repository answers
a different question -- "is this head newer than the last head I accepted" --
and cannot substitute for it: monotonicity says nothing about how old an
answer is.

The wording follows IETF WIMSE `draft-hulea-wimse-agent-mandate-00`, which
already calls the bound `max_status_age` and measures `T - iat`. We use their
terms rather than inventing a second name for the same idea.

Two things this does that the draft's Validation Result does not
--------------------------------------------------------------
1. It **reports the age**, per link, not only whether the bound was met. The
   draft carries `max_status_age` in the profile and `time: T` in the result;
   a reader of our record can recompute the age without the profile.
2. It keeps **T and A apart in the record**. The draft's procedures do this
   (`A >= T`, checks at A recorded with the authorization decision) but its
   result object carries only `time: T`. An answer can be fresh at T and over
   the bound at A; without both instants on the record, that case is
   indistinguishable from a pass.

Deliberately not here
--------------------
No I/O, no clock reading: callers pass both instants. A module that read its
own clock could not be tested for the case that matters, where T and A differ
because a person waited.
"""

from __future__ import annotations

from datetime import datetime, timezone

SCHEMA = "uibc-authority-age/1"

PASS = "PASS"
FAIL = "FAIL"
INCONCLUSIVE = "INCONCLUSIVE"

CURRENT = "CURRENT"
CHANGED = "CHANGED"

EXECUTED = "executed"
REFUSED = "refused"

__all__ = [
    "SCHEMA",
    "PASS",
    "FAIL",
    "INCONCLUSIVE",
    "CURRENT",
    "CHANGED",
    "EXECUTED",
    "REFUSED",
    "answer_age",
    "check_link",
    "evaluate_links",
    "commit_recheck",
    "status_at",
    "commit_recheck_from_history",
    "decision_record",
]


def _instant(value, name):
    """Parse an ISO-8601 instant into an aware UTC datetime."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be an ISO-8601 string, got %r" % (name, value))
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("%s is not ISO-8601: %s" % (name, exc)) from None
    if parsed.tzinfo is None:
        raise ValueError("%s carries no timezone; a local time is not an instant" % name)
    return parsed.astimezone(timezone.utc)


def answer_age(answer_iat, decision_at):
    """Seconds from the source's answer time to the decision time.

    A negative age is not clamped to zero: it means the answer is dated after
    the decision, which is a clock disagreement rather than freshness, and
    ``check_link`` reports it as INCONCLUSIVE instead of quietly passing.
    """
    return (_instant(decision_at, "decision_at") - _instant(answer_iat, "answer_iat")).total_seconds()


def check_link(answer_iat, decision_at, max_status_age, link=None):
    """One link's answer against its bound.

    Returns a dict with ``link``, ``state``, ``age_seconds``, ``bound_seconds``,
    ``answer_iat`` and ``detail``. ``state`` is PASS, FAIL or INCONCLUSIVE.

    A missing answer is INCONCLUSIVE, never PASS: "we did not look" and "we
    looked and it is fresh" are different facts, and Requirement 3's whole
    point is that the first one must not be upgraded by a later refresh.
    """
    if max_status_age is None or max_status_age <= 0:
        raise ValueError("max_status_age must be a positive number of seconds")
    row = {
        "link": link,
        "answer_iat": answer_iat,
        "bound_seconds": max_status_age,
    }
    if answer_iat is None:
        row.update({"state": INCONCLUSIVE, "age_seconds": None,
                    "detail": "no answer recorded for this link; unresolved, not passed"})
        return row
    age = answer_age(answer_iat, decision_at)
    if age < 0:
        row.update({"state": INCONCLUSIVE, "age_seconds": age,
                    "detail": "answer is dated after the decision; clocks disagree"})
        return row
    row["age_seconds"] = age
    if age > max_status_age:
        row.update({"state": FAIL,
                    "detail": "answer age %.0fs exceeds the %ss bound"
                              % (age, max_status_age)})
    else:
        row.update({"state": PASS,
                    "detail": "answer age %.0fs within the %ss bound"
                              % (age, max_status_age)})
    return row


def evaluate_links(answers_by_link, decision_at, bounds):
    """Evaluate every link and aggregate.

    Aggregate rule, chosen so that "worst wins" cannot be softened by a
    majority: any FAIL gives FAIL; otherwise any INCONCLUSIVE gives
    INCONCLUSIVE; otherwise PASS. There is no path where an unexamined link
    contributes a pass.
    """
    rows = []
    for link in sorted(answers_by_link):
        bound = bounds.get(link, bounds.get("*"))
        rows.append(check_link(answers_by_link[link], decision_at, bound, link=link))
    states = [r["state"] for r in rows]
    if FAIL in states:
        overall = FAIL
    elif INCONCLUSIVE in states:
        overall = INCONCLUSIVE
    else:
        overall = PASS
    return {
        "state": overall,
        "decision_at": decision_at,
        "links": rows,
        "rule": "FAIL > INCONCLUSIVE > PASS; an unanswered link cannot contribute a pass",
    }


def commit_recheck(answers_by_link, commit_at, bounds):
    """Re-check the answers at the instant the action commits.

    Between decision and commit there is a window: a token can be revoked, a
    mandate can expire, a status answer can go stale. A record showing the
    answer was fresh at decision time does not show it was still fresh when
    the action ran -- the point draft-malhotra-scitt-oar-00 Section 4.2 makes
    with its ``authority_check`` and ``result: current | changed``.

    We return ``state`` (CURRENT or CHANGED) plus the ``outcome`` a caller must
    record: an action whose answer went stale before commit is ``refused``, not
    executed, and names why in ``reason_codes``.

    This narrows the window; it cannot close it. The gap between ``commit_at``
    and the actual commit is the caller's to keep short, and this module does
    no I/O, so it cannot re-ask anyone -- the caller must supply fresh answers.

    Reason codes: ``authority_expired`` for an answer over its bound,
    ``authority_unknown`` for a link with no answer, ``authority_clock_skew``
    for an answer dated after the commit instant.
    """
    evaluation = evaluate_links(answers_by_link, commit_at, bounds)
    codes = []
    for row in evaluation["links"]:
        if row["state"] == FAIL:
            codes.append("authority_expired")
        elif row["state"] == INCONCLUSIVE:
            codes.append("authority_clock_skew" if (row["age_seconds"] or 0) < 0
                         else "authority_unknown")
    if codes:
        state, outcome = CHANGED, REFUSED
    else:
        state, outcome = CURRENT, EXECUTED
    return {
        "state": state,
        "outcome": outcome,
        "checked_at": commit_at,
        "reason_codes": codes,
        "answer_checks": evaluation["links"],
        "rule": ("an answer over its bound, absent, or dated after the commit "
                 "refuses the action rather than executing it"),
    }


def status_at(history, at):
    """What our own record says a link's status was at instant ``at``.

    ``history`` is a list of transition records in ascending time order, each
    with ``at`` (ISO-8601), ``new`` (one of interop_result.STATES) and optional
    ``reason``. Records dated after ``at`` are ignored: they had not happened
    yet, and using them would let a later revocation retroactively describe an
    earlier moment.

    Why this exists: the SCITT OAR profile asks a relying party to hand it the
    authority's status. We can do better on the one axis we own -- we derive
    the status at commit from our own revocation history, so the refusal does
    not rest on a caller remembering to re-ask. This does not make the answer
    fresh by itself; it makes the *revocation* self-attested.
    """
    if not isinstance(history, (list, tuple)):
        raise ValueError("history must be a sequence of transition records")
    at_dt = _instant(at, "at")
    chosen = None
    used = 0
    for record in history:
        when = _instant(record.get("at"), "history.at")
        if when > at_dt:
            break
        used += 1
        chosen = record
    if chosen is None:
        return {"state": None, "answer_iat": None, "records_used": 0,
                "detail": "no record at or before this instant; the link had no "
                          "status then, which is not the same as being valid"}
    return {
        "state": chosen.get("new"),
        "answer_iat": chosen.get("at"),
        "records_used": used,
        "reason": chosen.get("reason"),
    }


def commit_recheck_from_history(histories, commit_at, bounds):
    """Re-check at commit using our own status history instead of an outside answer.

    Each link's status at ``commit_at`` is derived with ``status_at()``; a link
    whose status is REVOKED, EXPIRED, INVALID or UNRESOLVED refuses the action
    with ``authority_revoked`` / ``authority_expired`` / ``authority_invalid``,
    regardless of how young the answer is. A link that is still VERIFIED at
    commit then goes through the ordinary age bound.

    The distinction that matters: age answers "is it stale", status answers
    "was it withdrawn". A fresh answer for a revoked authority is still a
    refusal, and this function cannot return CURRENT for one.
    """
    REVOKING = {"REVOKED": "authority_revoked",
                "EXPIRED": "authority_expired",
                "INVALID": "authority_invalid",
                "UNRESOLVED": "authority_unknown"}
    rows, codes, answers = [], [], {}
    for link in sorted(histories):
        status = status_at(histories[link], commit_at)
        revoked_code = REVOKING.get(status["state"])
        if revoked_code:
            rows.append({"link": link, "state": CHANGED, "status": status["state"],
                         "answer_iat": status["answer_iat"], "age_seconds": None,
                         "reason_code": revoked_code,
                         "detail": "status at commit is %s from our own record"
                                   % status["state"]})
            codes.append(revoked_code)
            continue
        if status["state"] is None:
            rows.append({"link": link, "state": INCONCLUSIVE, "status": None,
                         "answer_iat": None, "age_seconds": None,
                         "reason_code": "authority_unknown",
                         "detail": status["detail"]})
            codes.append("authority_unknown")
            continue
        answers[link] = status["answer_iat"]
    if answers:
        age_eval = evaluate_links(answers, commit_at, bounds)
        for row in age_eval["links"]:
            rows.append(row)
            if row["state"] == FAIL:
                codes.append("authority_expired")
            elif row["state"] == INCONCLUSIVE:
                codes.append("authority_clock_skew")
    rows.sort(key=lambda r: r["link"])
    if codes:
        state, outcome = CHANGED, REFUSED
    else:
        state, outcome = CURRENT, EXECUTED
    return {
        "state": state,
        "outcome": outcome,
        "checked_at": commit_at,
        "reason_codes": sorted(set(codes)),
        "links": rows,
        "rule": ("status at commit comes from our own transition history; a revoked "
                 "or expired link refuses the action even when its answer is young"),
    }


def decision_record(validation_at, decision_at, answers_by_link, bounds,
                    conditions_met=None, recourse_relied_on=None):
    """The record R1 and R3 ask for: both instants, per-link ages, and — when
    a reversible action proceeds while unresolved — the two fields that make
    that bounded rather than a general upgrade path.

    ``conditions_met`` and ``recourse_relied_on`` are lists of short strings.
    They are emitted even when empty, so a reader can tell "none named" from
    "field absent"; the difference is exactly what Requirement 3 turns on.
    """
    evaluation = evaluate_links(answers_by_link, decision_at, bounds)
    if evaluation["state"] == FAIL and conditions_met:
        raise ValueError("a failed age check cannot be justified by conditions; "
                         "re-answer or treat as unresolved")
    return {
        "schema": SCHEMA,
        "validation_at": validation_at,
        "decision_at": decision_at,
        "answer_checks": evaluation["links"],
        "state": evaluation["state"],
        "aggregate_rule": evaluation["rule"],
        "conditions_met": list(conditions_met or []),
        "recourse_relied_on": list(recourse_relied_on or []),
        "note": ("validation_at is T, decision_at is A; the same answer can be "
                 "fresh at T and over the bound at A, which is why both are "
                 "carried. Empty condition/recourse lists mean none were named."),
    }
