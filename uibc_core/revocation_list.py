"""Read the signed, cumulative revocation list authored elsewhere.

The format is the peer's ``predicate/v1/revocation-list``: one signed list is
``{"body": BODY, "sig": base64(Ed25519 over DOMAIN || JCS(BODY))}``; lists are
chained by sequence number and digest; an entry, once published, stays in every
later list byte for byte; and a verifier pins its root key ids out of band and
never reads one from a list.

This reader answers the same order of checks as the peer's reference verifier
and reports the same refusal codes, so its verdicts can be compared with the
shipped corpus answer key member by member. It is a reader only: it neither
mints nor signs anything.

Canonicalization (RFC 8785 under an integers-only I-JSON profile) and Ed25519
verification (RFC 8032) are the ones this package already uses for the evidence
tier, so both sides of a comparison canonicalize and verify identically.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os

from .aee import (
    _IJsonError,
    _JcsError,
    _ed25519_verify,
    _jcs_dumps,
    _parse_json_value,
    _walk_check_ints,
)

SCHEMA = "revocation-list/v1"
REPORT_FORMAT = "uibc-revocation-list-report/1"

#: The domain separator prepended to the canonical body before signing.
DOMAIN = b"probity-revocation-v1\x00"

#: The one body type a list carries.
LIST_TYPE = (
    "https://probityai.github.io/agent-evidence-vectors/predicate/v1/revocation-list"
)

#: The seven subject kinds a list names, ascending.
KINDS = ("agent", "build", "grant", "key", "permit", "sponsor", "stream")

#: The kinds whose id must be a lowercase hex SHA-256 digest.
DIGEST_KINDS = ("grant", "key", "permit")

CODES = (
    "revocation_list_shape",
    "revocation_list_signer_not_a_root",
    "revocation_list_signature_unverified",
    "revocation_list_other_chain",
    "revocation_list_rollback",
    "revocation_list_gap",
    "revocation_list_previous_mismatch",
    "revocation_list_time_reversed",
    "revocation_entry_from_future",
    "revocation_list_drops_entry",
)

#: Largest sequence number that is exact in every JSON reader (2**53 - 1).
MAX_EXACT_SEQ = (1 << 53) - 1

_B64 = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_B64_INDEX = {c: i for i, c in enumerate(_B64)}

_BODY_MEMBERS = ("type", "listId", "seq", "previous", "issuedAt", "issuerKey", "entries")
_ENTRY_MEMBERS = ("kind", "id", "revokedAt", "reason", "successor")


def _parse_list_bytes(raw: bytes):
    """Parse one list file under the integers-only I-JSON profile: unparseable,
    out-of-exact-range integers, duplicate members and bad scalars all make the
    document unreadable, exactly as the reference reader does."""
    try:
        top = _parse_json_value(raw)
        _walk_check_ints(top)
    except _IJsonError:
        return None
    except RecursionError:  # pragma: no cover - guarded by the parser
        return None
    return top


class Refusal(Exception):
    """A refusal, rendered as ``code`` or ``code:detail``."""

    def __init__(self, code: str, detail: str = ""):
        super().__init__(code + (":" + detail if detail else ""))
        self.code = code
        self.detail = detail

    def __str__(self) -> str:
        return self.code + (":" + self.detail if self.detail else "")

    def as_dict(self) -> dict:
        return {"code": self.code, "detail": self.detail}


def _shape(why: str) -> Refusal:
    return Refusal("revocation_list_shape", why)


def _is_identifier(s) -> bool:
    """1..512 printable ASCII bytes, no space: a list id or a non-digest id."""
    if not isinstance(s, str) or not 1 <= len(s) <= 512:
        return False
    return all(0x21 <= ord(c) <= 0x7E for c in s)


def _is_hex64(s) -> bool:
    if not isinstance(s, str) or len(s) != 64:
        return False
    return all(c in "0123456789abcdef" for c in s)


def _is_list_digest(s) -> bool:
    if not isinstance(s, str) or len(s) != 71 or s[:7] != "sha256:":
        return False
    return all(c in "0123456789abcdef" for c in s[7:])


def _read_time(v, what: str) -> str:
    """Exactly ``YYYY-MM-DDTHH:MM:SSZ`` naming a real calendar instant."""
    if not isinstance(v, str) or len(v) != 20:
        raise _shape(what + "_not_a_utc_second")
    if (
        v[4] != "-"
        or v[7] != "-"
        or v[10] != "T"
        or v[13] != ":"
        or v[16] != ":"
        or v[19] != "Z"
    ):
        raise _shape(what + "_not_a_utc_second")
    for i in (0, 1, 2, 3, 5, 6, 8, 9, 11, 12, 14, 15, 17, 18):
        if not ("0" <= v[i] <= "9"):
            raise _shape(what + "_not_a_utc_second")
    if v[:4] == "0000":
        raise _shape(what + "_not_a_calendar_instant")
    try:
        datetime.datetime.strptime(v, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        raise _shape(what + "_not_a_calendar_instant") from None
    return v


def _b64_strict(s) -> bytes:
    """Strict padded standard base64: right chars, right padding, and the
    unused low bits of the last sextet zero (what ``StdEncoding.Strict`` and
    the canonical-spelling check together admit)."""
    if not isinstance(s, str) or not s:
        raise ValueError("not a padded quartet")
    s = s.replace("\r", "").replace("\n", "")  # Go base64 ignores line breaks
    if len(s) % 4:
        raise ValueError("not a padded quartet")
    body, pad = s, 0
    while body.endswith("="):
        body, pad = body[:-1], pad + 1
        if pad > 2:
            raise ValueError("too much padding")
    if "=" in body or any(c not in _B64_INDEX for c in body):
        raise ValueError("not base64")
    if len(body) % 4 == 1:
        raise ValueError("dangling sextet")
    if pad:
        idx = _B64_INDEX[body[-1]]
        if (pad == 1 and idx & 0x03) or (pad == 2 and idx & 0x0F):
            raise ValueError("unused bits in the last sextet")
    return base64.b64decode(body + "=" * pad, validate=True)


def _read_raw_key(v, what: str) -> bytes:
    try:
        raw = _b64_strict(v)
    except ValueError:
        raise _shape(what + "_not_base64") from None
    if len(raw) != 32:
        raise _shape(what + "_not_an_ed25519_key")
    if base64.b64encode(raw).decode("ascii") != v:
        raise _shape(what + "_not_canonical_base64")
    return raw


def _canonical_base64(v):
    try:
        raw = _b64_strict(v)
    except ValueError:
        return None
    if base64.b64encode(raw).decode("ascii") != v:
        return None
    return raw


def _digest_of_canon(canon: bytes) -> str:
    return "sha256:" + hashlib.sha256(canon).hexdigest()


def list_digest(value) -> str:
    """``sha256:`` + lowercase hex SHA-256 of JCS(body) for a body value."""
    return _digest_of_canon(_jcs_dumps(value))


def _digest_of_file(raw: bytes):
    """The digest a corpus records for one list file: computed whenever the
    file is an object carrying a canonicalizable ``body``, ``None`` otherwise
    (that file never got far enough to have one)."""
    top = _parse_list_bytes(raw)
    if top is None:
        return None
    if not isinstance(top, dict) or "body" not in top:
        return None
    try:
        return list_digest(top["body"])
    except (_JcsError, TypeError, ValueError):
        return None


class RevocationState:
    """A verifier's side: pinned roots and the list in force (none: seq 0)."""

    __slots__ = ("roots", "list_id", "seq", "head", "issued_at", "entries")

    def __init__(self, roots=(), list_id="", seq=0, head="", issued_at="", entries=None):
        self.roots = tuple(sorted(set(roots)))
        self.list_id = list_id
        self.seq = seq
        self.head = head
        self.issued_at = issued_at
        self.entries = dict(entries or {})  # (kind, id) -> JCS bytes of the entry

    def is_root(self, key_id: str) -> bool:
        return key_id in self.roots

    def revoked(self, kind: str, subject_id: str) -> bool:
        return (kind, subject_id) in self.entries

    def revoked_ids(self, kind: str):
        return sorted(i for (k, i) in self.entries if k == kind)

    def as_dict(self) -> dict:
        return {
            "head": self.head,
            "issuedAt": self.issued_at,
            "listId": self.list_id,
            "revoked": {k: self.revoked_ids(k) for k in KINDS},
            "roots": list(self.roots),
            "seq": self.seq,
        }


class _Entry:
    __slots__ = ("kind", "id", "revoked_at", "successor", "canon")

    def __init__(self, kind, subject_id, revoked_at, successor, canon):
        self.kind = kind
        self.id = subject_id
        self.revoked_at = revoked_at
        self.successor = successor
        self.canon = canon


class _Body:
    __slots__ = ("list_id", "previous", "has_previous", "seq", "issued_at", "issuer_key", "entries", "canon")


def _read_body(value) -> _Body:
    if not isinstance(value, dict) or len(value) != len(_BODY_MEMBERS):
        raise _shape("body_members")
    for name in _BODY_MEMBERS:
        if name not in value:
            raise _shape("body_members")

    b = _Body()
    if value["type"] != LIST_TYPE:
        raise _shape("type")
    if not _is_identifier(value["listId"]):
        raise _shape("list_id_form")
    b.list_id = value["listId"]

    seq = value["seq"]
    if isinstance(seq, bool) or not isinstance(seq, int) or not 1 <= seq <= MAX_EXACT_SEQ:
        raise _shape("seq_not_a_positive_exact_integer")
    b.seq = seq
    previous = value["previous"]
    if previous is None:
        if seq != 1:
            raise _shape("previous_form")
        b.previous, b.has_previous = "", False
    elif isinstance(previous, str):
        if seq == 1 or not _is_list_digest(previous):
            raise _shape("previous_form")
        b.previous, b.has_previous = previous, True
    else:
        raise _shape("previous_form")

    b.issued_at = _read_time(value["issuedAt"], "issuedAt")
    b.issuer_key = _read_raw_key(value["issuerKey"], "issuerKey")

    entries = value["entries"]
    if not isinstance(entries, list):
        raise _shape("entries_not_a_list")
    b.entries = [_read_entry(e) for e in entries]
    for prev, cur in zip(b.entries, b.entries[1:]):
        if prev.kind > cur.kind or (prev.kind == cur.kind and prev.id >= cur.id):
            raise _shape("entries_not_strictly_ascending")

    try:
        b.canon = _jcs_dumps(value)
    except (_JcsError, TypeError, ValueError):
        raise _shape("body_not_canonical") from None
    return b


def _read_entry(value) -> _Entry:
    if not isinstance(value, dict):
        raise _shape("entry_not_an_object")
    for name in value:
        if name not in _ENTRY_MEMBERS:
            raise _shape("entry_members")
    for name in ("kind", "id", "revokedAt"):
        if name not in value:
            raise _shape("entry_members")

    kind = value["kind"]
    if kind not in KINDS:
        raise _shape("entry_kind_unknown")
    subject_id = value["id"]
    if kind in DIGEST_KINDS:
        if not _is_hex64(subject_id):
            raise _shape("entry_id_form:" + kind)
    elif not _is_identifier(subject_id):
        raise _shape("entry_id_form:" + kind)

    revoked_at = _read_time(value["revokedAt"], "revokedAt")
    if "reason" in value and not isinstance(value["reason"], str):
        raise _shape("entry_reason_not_text")
    successor = None
    if "successor" in value:
        if kind != "key":
            raise _shape("successor_on_non_key_entry")
        successor = _read_raw_key(value["successor"], "successor")

    try:
        canon = _jcs_dumps(value)
    except (_JcsError, TypeError, ValueError):
        raise _shape("entry_not_canonical") from None
    return _Entry(kind, subject_id, revoked_at, successor, canon)


def apply(state: RevocationState, signed: bytes) -> RevocationState:
    """Return the state with ``signed`` as the list in force, or raise Refusal."""
    top = _parse_list_bytes(signed)
    if top is None:
        raise _shape("signed_list_unreadable")
    if not isinstance(top, dict) or len(top) != 2 or "body" not in top or "sig" not in top:
        raise _shape("signed_list_members")

    body = _read_body(top["body"])

    key_id = hashlib.sha256(body.issuer_key).hexdigest()
    if not state.is_root(key_id):
        raise Refusal("revocation_list_signer_not_a_root")

    sig = _canonical_base64(top["sig"])
    if sig is None or len(sig) != 64 or not _ed25519_verify(body.issuer_key, DOMAIN + body.canon, sig):
        raise Refusal("revocation_list_signature_unverified")

    return _install(state, body)


def _install(state: RevocationState, body: _Body) -> RevocationState:
    if state.list_id and body.list_id != state.list_id:
        raise Refusal("revocation_list_other_chain")
    if body.seq <= state.seq:
        raise Refusal("revocation_list_rollback", "%d<=%d" % (body.seq, state.seq))
    if body.seq > state.seq + 1:
        raise Refusal("revocation_list_gap", "%d>%d" % (body.seq, state.seq + 1))
    if body.has_previous != (state.head != "") or body.previous != state.head:
        raise Refusal("revocation_list_previous_mismatch")
    if state.issued_at and body.issued_at < state.issued_at:
        raise Refusal("revocation_list_time_reversed")

    entries = {}
    for e in body.entries:
        if e.revoked_at > body.issued_at:
            raise Refusal("revocation_entry_from_future")
        entries[(e.kind, e.id)] = e.canon

    for key in sorted(state.entries):
        if entries.get(key) != state.entries[key]:
            raise Refusal("revocation_list_drops_entry", "%s:%s" % (key[0], key[1][:12]))

    gone, joined = set(), []
    for e in body.entries:
        if e.kind != "key":
            continue
        gone.add(e.id)
        if e.successor is not None and state.is_root(e.id):
            joined.append(hashlib.sha256(e.successor).hexdigest())
    roots = sorted((set(state.roots) | set(joined)) - gone)

    return RevocationState(
        roots=roots,
        list_id=body.list_id,
        seq=body.seq,
        head=_digest_of_canon(body.canon),
        issued_at=body.issued_at,
        entries=entries,
    )


def verify_chain(root_ids, lists) -> dict:
    """Apply the signed lists in order from a verifier holding no list."""
    state = RevocationState(root_ids)
    digests = []
    for i, raw in enumerate(lists):
        digests.append(_digest_of_file(raw))
        try:
            state = apply(state, raw)
        except Refusal as r:
            return {
                "verdict": "invalid",
                "decision": "reject",
                "reason": str(r),
                "refusal": r.as_dict(),
                "index": i,
                "listDigests": digests,
                "state": state.as_dict(),
            }
    return {
        "verdict": "valid",
        "decision": "accept",
        "reason": "in_force",
        "refusal": None,
        "index": None,
        "listDigests": digests,
        "state": state.as_dict(),
    }


def iter_cases(corpus: str):
    """Yield ``(vector, roots, lists)`` for a corpus laid out like the peer's:
    a ``MANIFEST.json`` whose vectors name a case directory holding ``roots.json``
    and the signed lists, in order."""
    manifest_path = os.path.join(corpus, "MANIFEST.json")
    with open(manifest_path, encoding="utf-8") as fh:
        manifest = json.load(fh)
    for vector in manifest.get("vectors") or []:
        case_dir = os.path.join(corpus, vector.get("path") or os.path.join("cases", vector["id"]))
        with open(os.path.join(case_dir, "roots.json"), encoding="utf-8") as fh:
            roots = json.load(fh)["roots"]
        lists = []
        for name in vector.get("lists") or []:
            with open(os.path.join(case_dir, name), "rb") as fh:
                lists.append(fh.read())
        yield vector, roots, lists


def judge_case(case_dir: str) -> dict:
    """Judge one case directory: pinned roots plus the lists named in order."""
    with open(os.path.join(case_dir, "roots.json"), encoding="utf-8") as fh:
        roots = json.load(fh)["roots"]
    names = sorted(n for n in os.listdir(case_dir) if n.startswith("list-") and n.endswith(".json"))
    lists = []
    for name in names:
        with open(os.path.join(case_dir, name), "rb") as fh:
            lists.append(fh.read())
    return verify_chain(roots, lists)


def judge_corpus(corpus: str) -> dict:
    """Judge every member of a corpus against its own answer key."""
    records = []
    conforming = 0
    for vector, roots, lists in iter_cases(corpus):
        expected = vector.get("expected") or {}
        got = verify_chain(roots, lists)
        fields = ("decision", "index", "reason", "listDigests", "state")
        mismatched = [f for f in fields if got.get(f) != expected.get(f)]
        ok = not mismatched
        conforming += 1 if ok else 0
        records.append({
            "id": vector.get("id"),
            "got": {f: got.get(f) for f in fields},
            "expected": {f: expected.get(f) for f in fields},
            "conforms": ok,
            "mismatched": mismatched,
        })
    return {
        "members": len(records),
        "conforming": conforming,
        "records": records,
    }
