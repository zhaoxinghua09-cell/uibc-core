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
"""

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
