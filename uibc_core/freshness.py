"""Freshness state: the one thing a verifier can remember between runs.

S9 answers "is this the head I was told to expect", which requires the caller
to know the head every time. This module answers the weaker question that
does not need a human in the loop: "is this newer than the last one I
accepted", by remembering the last accepted head on disk.

Three deliberate limits, because a state file that over-promises is worse than
none:

1. One writer. No locking. A state file raced by two processes is a race, not
   a state file; the caller serialises, or it does not use this.
2. Ordering needs a stated sequence. Without one, a different head cannot be
   placed in time, and the answer is INCONCLUSIVE - never PASS, because
   "different" is not "newer".
3. First observation is INCONCLUSIVE. There is no high-water mark to compare
   against, so nothing has been established. A high-water mark has to start
   somewhere; this module does not pretend that "started" means "verified".
"""
import json
import os
import tempfile

SCHEMA = "uibc-freshness/1"


def empty():
    return {"schema": SCHEMA, "subjects": {}}


def load(path):
    """Read state, or return an empty state when the file does not exist yet."""
    if not path or not os.path.exists(path):
        return empty()
    with open(path, "r", encoding="utf-8") as fh:
        doc = json.load(fh)
    if not isinstance(doc, dict) or not isinstance(doc.get("subjects"), dict):
        raise ValueError("state file is not an object with a 'subjects' map")
    return doc


def evaluate(state, subject, head, sequence=None, prev_head=None):
    """Place a presented head against the remembered one.

    Returns (result, detail) where result is PASS, FAIL or INCONCLUSIVE.
    PASS here means "not observed to be stale", not "authentic" - that is
    S6's job and this module does not borrow it.
    """
    row = state.get("subjects", {}).get(subject)
    if row is None:
        return ("INCONCLUSIVE",
                "first observation of %r: no high-water mark to compare against" % (subject,))

    recorded_head = str(row.get("head", ""))
    recorded_seq = row.get("sequence")

    if sequence is None:
        if str(head) == recorded_head:
            return ("PASS", "same head as the last accepted observation")
        return ("INCONCLUSIVE",
                "a different head was presented with no sequence number, so it "
                "cannot be placed before or after the recorded one")

    try:
        seq = int(sequence)
    except (TypeError, ValueError):
        return ("INCONCLUSIVE", "sequence %r is not an integer" % (sequence,))

    if recorded_seq is None:
        if str(head) == recorded_head:
            return ("PASS", "same head; the recorded observation carries no sequence")
        return ("INCONCLUSIVE",
                "presented a sequence but the remembered observation has none")

    try:
        last = int(recorded_seq)
    except (TypeError, ValueError):
        return ("INCONCLUSIVE", "recorded sequence %r is not an integer" % (recorded_seq,))

    if seq < last:
        return ("FAIL", "regressed: presented sequence %d is older than the "
                        "remembered %d - a validly signed package from an earlier "
                        "point in time" % (seq, last))
    if seq == last:
        if str(head) == recorded_head:
            return ("PASS", "same sequence, same head")
        return ("FAIL", "two different heads at sequence %d - fork" % seq)
    # seq > last
    if prev_head is not None and str(prev_head).lower() != recorded_head.lower():
        return ("FAIL", "sequence advanced past %d but prev_head does not match "
                        "the remembered head - skipped step or fork" % last)
    return ("PASS", "advanced from %d to %d" % (last, seq))


def record(path, subject, head, sequence=None, accepted_at=None):
    """Remember an observation. Atomic replace so a crash cannot leave half a file."""
    state = load(path) if path else empty()
    row = {"head": str(head)}
    if sequence is not None:
        try:
            row["sequence"] = int(sequence)
        except (TypeError, ValueError):
            pass
    if accepted_at:
        row["accepted_at"] = str(accepted_at)
    state.setdefault("subjects", {})[subject] = row
    d = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".freshness-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(state, fh, indent=1, sort_keys=True, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
    return state
