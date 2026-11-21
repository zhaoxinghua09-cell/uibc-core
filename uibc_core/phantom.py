"""Phantom entries: a hash-chained record of the calls the gate REFUSED.

Why this exists
---------------
A gate that says DENY and writes nothing leaves the two most important
questions unanswerable: *was this request never made, or was it made and
refused?* Absence of a record and absence of an attempt look identical.
`draft-noctem-cogitator-witness-protocol-00` names the missing object a
**phantom entry** — a record of a tool call intercepted and blocked before
dispatch — and puts it inside the witness bundle so the chain covers blocked
work too.

Scope discipline (what this is NOT)
-----------------------------------
This is an append-only local ledger with a hash chain. It proves the ledger was
not edited *after the fact* relative to its neighbours - the same limit
`draft-ruvalcaba-nhe-audit-00` states for unkeyed chains: a party able to
rebuild the whole chain can produce a consistent alternative. There is **no
signature, no witness, no external anchor** here, so a verified chain means
"internally consistent", never "authoritative". Callers must not report it as
more than that.
"""
from __future__ import annotations

import json
import os

from .canonical import hash_obj, sha256_hex

GENESIS = "sha256:genesis"
DECISIONS = {"ALLOW", "HOLD", "DENY"}


def _entry_hash(entry: dict) -> str:
    body = {k: v for k, v in entry.items() if k != "entry_hash"}
    return hash_obj(body)


class PhantomLog:
    """Append-only JSONL chain. One file, one line per decision."""

    def __init__(self, path: str):
        self.path = path
        self._head = None
        self._seq = 0
        if os.path.exists(path):
            for line in open(path, encoding="utf-8"):
                if line.strip():
                    e = json.loads(line)
                    self._head = e["entry_hash"]
                    self._seq = e["seq"]

    @property
    def head(self) -> str:
        return self._head or GENESIS

    def append(self, *, decision: str, reason: str, rule_id: str,
               request_digest: str, executed: bool, at: str,
               subject: str = None) -> dict:
        """Record one gate decision. `executed=False` makes it a phantom entry."""
        if decision not in DECISIONS:
            raise ValueError("decision must be one of %s" % sorted(DECISIONS))
        entry = {
            "seq": self._seq + 1,
            "at": at,
            "decision": decision,
            "executed": bool(executed),
            "phantom": not executed,
            "rule_id": rule_id,
            "reason": reason,
            "request_digest": request_digest,
            "subject": subject,
            "prev": self.head,
        }
        entry["entry_hash"] = _entry_hash(entry)
        os.makedirs(os.path.dirname(os.path.abspath(self.path)), exist_ok=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
        self._seq = entry["seq"]
        self._head = entry["entry_hash"]
        return entry


def request_digest(obj) -> str:
    """Digest of the request itself, so a phantom entry names what was refused."""
    return "sha256:" + hash_obj(obj)


def verify_phantom_log(path: str) -> dict:
    """Recompute the chain. Reports consistency only - never authority."""
    problems = []
    entries = []
    if not os.path.exists(path):
        return {"result": "INCONCLUSIVE", "entries": 0, "head": GENESIS,
                "problems": ["no phantom log: an empty log and a deleted log "
                             "are indistinguishable without an out-of-band head"]}
    for i, line in enumerate(open(path, encoding="utf-8"), start=1):
        if not line.strip():
            continue
        try:
            e = json.loads(line)
        except Exception as exc:
            problems.append("line %d is not JSON (%s)" % (i, type(exc).__name__))
            continue
        entries.append(e)
    prev = GENESIS
    for idx, e in enumerate(entries, start=1):
        if e.get("seq") != idx:
            problems.append("sequence gap at position %d: seq=%r" % (idx, e.get("seq")))
        if e.get("prev") != prev:
            problems.append("broken link at seq %r: prev=%r expected %r"
                            % (e.get("seq"), e.get("prev"), prev))
        if e.get("entry_hash") != _entry_hash(e):
            problems.append("content edited at seq %r (entry_hash mismatch)"
                            % (e.get("seq"),))
        if e.get("decision") not in DECISIONS:
            problems.append("unknown decision at seq %r: %r"
                            % (e.get("seq"), e.get("decision")))
        prev = e.get("entry_hash", prev)

    if not entries:
        return {"result": "INCONCLUSIVE", "entries": 0, "head": GENESIS,
                "problems": ["log exists but holds no entry"]}
    head = entries[-1].get("entry_hash")
    phantom = sum(1 for e in entries if e.get("phantom"))
    return {"result": "FAIL" if problems else "PASS",
            "entries": len(entries), "head": head,
            "phantom_entries": phantom, "problems": problems,
            "scope": "internal consistency of the local ledger only; unsigned, "
                     "unwitnessed, no external anchor"}


def head_of(path: str) -> str:
    r = verify_phantom_log(path)
    return r["head"]


def head_digest(head: str) -> str:
    return "sha256:" + sha256_hex(head.encode("utf-8"))
