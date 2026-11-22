# -*- coding: utf-8 -*-
"""Tri-state revocation classifier — LOCAL PROTOTYPE (proposal, not shipped).

Why this exists: our public repos contain no implementation of
revoked_at_t / not_revoked_at_t / undetermined (code search: 0 hits).
This is a minimal, stdlib-only prototype to make the claim runnable
before it is used in any external text.

Semantics
---------
Given a revocation feed entry (or its absence) and an evaluation instant t:

- revoked_at_t      : a revocation record for the subject exists with
                      revoked_at <= t (validly signed / parsed).
- not_revoked_at_t  : a feed was obtained, is fresh at t, contains no
                      revocation for the subject, and t >= issued_at.
- undetermined      : anything else — missing feed, stale feed, parse
                      error, revocation dated after t, or clock skew.

The point of the third state is that "absence of evidence" is not
"evidence of absence": a stale or unreachable feed must not silently
become "not revoked".
"""
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional

VALID = {"not_revoked_at_t", "revoked_at_t", "undetermined"}


@dataclass(frozen=True)
class Feed:
    issued_at: datetime          # when this feed snapshot was produced
    entries: dict                # subject_id -> revoked_at (datetime)
    signature_ok: bool = True


@dataclass(frozen=True)
class Result:
    state: str
    reason: str


def classify(feed: Optional[Feed], subject: str, t: datetime, max_age: timedelta) -> Result:
    if feed is None:
        return Result("undetermined", "no feed")
    if not feed.signature_ok:
        return Result("undetermined", "feed signature invalid")
    # 时钟偏移：评估时刻早于 feed 签发时刻，快照不可能覆盖 t
    if t < feed.issued_at:
        return Result("undetermined", "clock skew: t < feed issued_at")
    if t - feed.issued_at > max_age:
        return Result("undetermined", "feed stale at t")
    rev = feed.entries.get(subject)
    if rev is None:
        return Result("not_revoked_at_t", "fresh signed feed, no entry for subject")
    if rev <= t:
        return Result("revoked_at_t", f"revoked at {rev.isoformat()}")
    return Result("undetermined", "revocation date is after t")


if __name__ == "__main__":
    now = datetime(2026, 11, 22, 12, 0, tzinfo=timezone.utc)
    feed = Feed(issued_at=now - timedelta(minutes=10),
                entries={"agent:A": now - timedelta(hours=1)})
    cases = [
        ("A revoked before t", classify(feed, "agent:A", now, timedelta(hours=1)),
         "revoked_at_t"),
        ("B never listed", classify(feed, "agent:B", now, timedelta(hours=1)),
         "not_revoked_at_t"),
        ("A with stale feed", classify(Feed(now - timedelta(days=2), feed.entries), "agent:A", now, timedelta(hours=1)),
         "undetermined"),
        ("no feed", classify(None, "agent:A", now, timedelta(hours=1)), "undetermined"),
    ]
    ok = True
    for name, res, expect in cases:
        mark = "PASS" if res.state == expect else "FAIL"
        ok = ok and res.state == expect
        print(f"{mark}  {name:24s} -> {res.state:19s} ({res.reason})")
    print("ALL PASS" if ok else "SOME FAILED")
