"""Observation-record access — the supported public surface.

Callers that need to read an Adversarial Execution Evidence statement's
carried observation records MUST go through this module rather than
reaching into ``aee`` internals. The three functions here are the whole
contract:

``iter_records(statement)``
    Yield one :class:`Record` per carried record, in statement order.

``record_verified(record, pinned_pubs)``
    True when some signature entry on the record Ed25519-verifies over the
    record's DSSE PAE against one of the caller's pinned public keys.
    The carried ``keyid`` is a lookup hint and is never the check.

``verified_arming_instants(statement, pinned_pubs)``
    The ``armedAt`` strings carried by arming records whose signatures
    verify against the pinned keys.

Nothing here decides validity, tier, or admission. Those remain the
verifier's and the consumer's answers; this module only makes the records
readable without exposing private helpers.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Iterable

from . import aee as _aee

__all__ = [
    "Record",
    "iter_records",
    "record_verified",
    "verified_arming_instants",
    "records_of",
]


@dataclass(frozen=True)
class Record:
    """One carried record, decoded once.

    ``kind`` is the payload's ``aeeKind`` (``arming``, ``sealed``,
    ``interception``, ``examination``) or ``None`` when the payload is
    unreadable. ``payload`` is the strict-parsed payload object or ``None``;
    ``payload_error`` names why it could not be parsed when it could not.
    """

    index: int
    raw: dict[str, Any]
    payload_type: str | None
    payload: dict[str, Any] | None
    payload_error: str | None
    pae: bytes | None
    signature_count: int

    @property
    def kind(self) -> str | None:
        return self.payload.get("aeeKind") if isinstance(self.payload, dict) else None

    @property
    def method(self) -> str | None:
        return self.payload.get("aeeMethod") if isinstance(self.payload, dict) else None


def _views(statement: Any) -> Iterator[tuple[_aee._RecordView, Record]]:
    pred = (statement.get("predicate") if isinstance(statement, dict) else None) or {}
    for i, rec in enumerate(pred.get("observationRecords") or []):
        view = _aee._RecordView(i, rec)
        yield view, Record(
            index=i,
            raw=rec if isinstance(rec, dict) else {},
            payload_type=view.payload_type,
            payload=view.payload if isinstance(view.payload, dict) else None,
            payload_error=getattr(view, "payload_error", None),
            pae=view.pae,
            signature_count=view.signature_count,
        )


def iter_records(statement: Any) -> Iterator[Record]:
    """Yield the statement's carried records in order."""
    for _view, record in _views(statement):
        yield record


def records_of(statement: Any) -> list[Record]:
    """Materialised form of :func:`iter_records`, for callers that need a list."""
    return list(iter_records(statement))


def record_verified(record: Record, pinned_pubs: Iterable[bytes]) -> bool:
    """True when a signature on the record verifies under a pinned key."""
    keys = list(pinned_pubs)
    if not keys:
        return False
    view = _aee._RecordView(record.index, record.raw)
    return bool(_aee._record_verifies(view, keys))


def verified_arming_instants(statement: Any, pinned_pubs: Iterable[bytes]) -> list[str]:
    """``armedAt`` values of arming records that verify under pinned keys."""
    keys = list(pinned_pubs)
    out: list[str] = []
    for view, record in _views(statement):
        if record.kind != "arming" or not isinstance(record.payload, dict):
            continue
        if not keys or not _aee._record_verifies(view, keys):
            continue
        armed_at = record.payload.get("armedAt")
        if isinstance(armed_at, str):
            out.append(armed_at)
    return out
