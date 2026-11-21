"""Lifecycle event state machine (archive SS11).

Events: REGISTER ACTIVATE UPDATE TRANSFER DELEGATE MIGRATE SUSPEND RESUME REVOKE RETIRE
Rules (v0.1 minimal set):
  L1  first event must be REGISTER
  L2  exactly one REGISTER
  L3  event types must be known
  L4  previous_event must chain correctly (event_id of prior event; None for first)
  L5  event_id must be unique
  L6  RESUME only valid immediately after SUSPEND
  L7  REVOKE / RETIRE are terminal - no events may follow them
An illegal transition is a lifecycle state violation (archive SS11 goal).

v1.1 semantic layer (fixes F2/F3 of tools/mutation_benchmark.py). The checks
below need context the bare state machine does not have (the identity owner
and the package creation time), so they live in ``validate_lifecycle_strict``
and are only run by the verifier. Measured gap they close: before v1.1, a
rewritten event timestamp (to 2030), a rewritten actor, and an appended
ACTIVATE were all accepted.

  L8  timestamp must be present, ISO-8601 parsible, and monotonic non-decreasing
  L9  no event may be timestamped in the future relative to manifest.created_at
      beyond a tolerance (default 24 h), and none may predate 1970
  L10 actor must be the identity owner (or the agent_id itself), when known
  L11 ACTIVATE is a once-only event; a second ACTIVATE is a fabricated state
"""

import datetime as _dt

EVENTS = [
    "REGISTER", "ACTIVATE", "UPDATE", "TRANSFER", "DELEGATE",
    "MIGRATE", "SUSPEND", "RESUME", "REVOKE", "RETIRE",
]
TERMINAL = {"REVOKE", "RETIRE"}


def validate_lifecycle(events: list) -> list:
    """Return a list of violation strings. Empty list = lifecycle valid."""
    errors = []
    seen_ids = set()
    prev_id = None
    registered = False
    prev_type = None

    for i, ev in enumerate(events):
        etype = ev.get("event_type")
        eid = ev.get("event_id")

        if etype not in EVENTS:                                   # L3
            errors.append(f"L3 unknown event_type '{etype}' at position {i}")

        if eid in seen_ids:                                       # L5
            errors.append(f"L5 duplicate event_id '{eid}' at position {i}")
        seen_ids.add(eid)

        if ev.get("previous_event") != prev_id:                   # L4
            errors.append(
                f"L4 previous_event chain broken at position {i} "
                f"(expected {prev_id!r}, got {ev.get('previous_event')!r})"
            )

        if i == 0:
            if etype != "REGISTER":                               # L1
                errors.append("L1 first event must be REGISTER")
        elif not registered:
            errors.append(f"L1 event before REGISTER at position {i}")
        elif etype == "REGISTER":                                 # L2
            errors.append(f"L2 duplicate REGISTER at position {i}")

        if etype == "REGISTER":
            registered = True

        if etype == "RESUME" and prev_type != "SUSPEND":          # L6
            errors.append(f"L6 RESUME at position {i} not preceded by SUSPEND")

        if i > 0 and prev_type in TERMINAL:                       # L7
            errors.append(f"L7 event after terminal event at position {i}")

        prev_id = eid
        prev_type = etype

    return errors


ONCE_ONLY = {"ACTIVATE"}


def _parse_ts(value):
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip().replace("Z", "+00:00")
    try:
        dt = _dt.datetime.fromisoformat(text)
    except ValueError:
        return None
    # A timestamp without a zone is a *finding* (S12 rejects it), not a crash:
    # comparing it against an aware manifest.created_at raised TypeError and the
    # fail-closed wrapper then reported "verifier robustness" instead of the real
    # problem. Assume UTC for ordering purposes only.
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt


def validate_lifecycle_strict(events: list, created_at: str = None,
                              allowed_actors: list = None,
                              max_future_seconds: int = 86400) -> list:
    """Semantic checks L8-L11. Return violation strings; empty = clean.

    Every argument is optional: a caller with no context gets no extra
    findings, which keeps this a pure widening of validate_lifecycle().
    """
    errors = []
    boundary = _parse_ts(created_at) if created_at else None
    ceiling = boundary + _dt.timedelta(seconds=max_future_seconds) if boundary else None

    prev_ts = None
    counts = {}
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            errors.append(f"L8 event {i} is not an object")
            continue

        # L8 timestamp present / parsible / non-decreasing
        ts = _parse_ts(ev.get("timestamp"))
        if ts is None:
            errors.append(f"L8 event {i} has no parsible ISO-8601 timestamp "
                          f"({ev.get('timestamp')!r})")
        else:
            if ts.year < 1970:
                errors.append(f"L9 event {i} timestamp predates 1970")
            if prev_ts is not None and ts < prev_ts:
                errors.append(f"L8 event {i} timestamp goes backwards "
                              f"({ev.get('timestamp')} < previous)")
            prev_ts = ts

        # L9 future-beyond-tolerance
        if ts is not None and ceiling is not None and ts > ceiling:
            errors.append(
                f"L9 event {i} timestamp {ev.get('timestamp')} is later than "
                f"manifest.created_at + {max_future_seconds}s "
                f"(implausible: the log is sealed at creation time)")

        # L10 actor allow-list
        if allowed_actors is not None:
            actor = ev.get("actor")
            if actor not in allowed_actors:
                errors.append(
                    f"L10 event {i} actor {actor!r} is not an authorised principal "
                    f"{sorted(allowed_actors)}")

        # L11 once-only event types
        etype = ev.get("event_type")
        counts[etype] = counts.get(etype, 0) + 1
        if etype in ONCE_ONLY and counts[etype] > 1:
            errors.append(f"L11 duplicate {etype} at position {i} "
                          f"({counts[etype]} occurrences of a once-only event)")

        # L12 sequence_number: contiguous from 0 when the log carries them.
        # A gap in a sealed log is a suppression indicator - the same
        # semantics GAR -08 Section 6.2 gives session_sequence_number.
        if "sequence_number" in ev:
            seq = ev.get("sequence_number")
            if not isinstance(seq, int) or isinstance(seq, bool):
                errors.append(f"L12 event {i} sequence_number is not an integer ({seq!r})")
            elif seq != i:
                errors.append(f"L12 event {i} sequence_number={seq} breaks contiguity "
                              f"(expected {i}): a gap in a sealed log indicates a "
                              f"suppressed event")

    return errors
