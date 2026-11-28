"""Read the signed revocation list in *delta* form.

The v1 reader in this package reads a cumulative list: every list repeats what
the chain already holds, and a list that drops an entry is refused
(``revocation_list_drops_entry``). The peer's ``predicate/v2/revocation-list``
reverses that: a list carries only what it *newly* revokes, a reader folds each
list into the state it already holds, an entry is published once and never
again (a repeat is refused, ``revocation_entry_repeated``), and an empty list is
a freshness list. Both types are live upstream, so a reader that knows only one
of them is a reader that refuses half the lists in circulation.

The wire form is the same::

    {"body": {"type": LIST_TYPE, "listId": id, "seq": n,
              "previous": "sha256:<hex>" | None, "issuedAt": "…Z",
              "issuerKey": b64 raw Ed25519,
              "entries": [{"kind": k, "id": i, "revokedAt": "…Z",
                           "reason": str (optional),
                           "successor": b64 raw Ed25519 (key kind only)}, …]},
     "sig": b64 Ed25519 over "probity-revocation-v1\\0" || JCS(body)}

What differs, beyond the type and the fold, is the subject vocabulary: the
delta form names eight kinds, adding ``idp-key``, an identity provider's
token-signing key named by its RFC 7638 JWK thumbprint (SHA-256, base64url,
no padding, 43 digits) rather than by this format's own hex key id. A key of
kind ``key`` may carry a ``successor``; revoking such a root rotates it.

Roots are pinned by the verifier, never read from a list. The roots after a
list are the roots held plus the successor ids of the roots that list revokes
(less any successor revoked earlier, and less any key this same list revokes),
minus every key id the list revokes: a revoked key is never a root, in whatever
order the entries come, in whichever list it was revoked.

Canonicalization, base64 strictness, time form and Ed25519 verification are the
ones the v1 reader in this package already uses, imported rather than copied,
so a list read by either reader gets the same verdict from the same bytes.
This module is a reader: it mints and signs nothing.
"""

from __future__ import annotations

import base64
import hashlib

from .aee import _IJsonError, _JcsError, _ed25519_verify, _jcs_dumps, _parse_json_value
from .revocation_list import (
    Refusal,
    _b64_strict,
    _digest_of_canon,
    _is_hex64,
    _is_identifier,
    _is_list_digest,
    _parse_list_bytes,
    _read_time,
    _shape,
)

SCHEMA = "revocation-list/delta"
REPORT_FORMAT = "uibc-revocation-delta-report/1"

#: The domain separator is the one the v1 lists use; the type differs, the bytes
#: a producer signs are framed the same way.
DOMAIN = b"probity-revocation-v1\x00"

#: Where the type is written in this release, and the second host the peer
#: recognises for the same identifier. Each key has one spelling per host; a
#: reader that accepted only one would refuse every list issued under the other.
LIST_TYPE = "https://probityai.github.io/agent-evidence-vectors/predicate/v2/revocation-list"
_LIST_HOSTS = (
    "https://probityai.github.io/",
    "https://probityai.org/",
)
_TYPE_PATH = "agent-evidence-vectors/predicate/v2/revocation-list"

#: The eight subject kinds a list names, ascending.
KINDS = ("agent", "build", "grant", "idp-key", "key", "permit", "sponsor", "stream")

#: The kinds whose id must be a lowercase hex SHA-256 digest.
DIGEST_KINDS = ("grant", "key", "permit")

#: The kind named by an RFC 7638 thumbprint instead of a hex id.
IDP_KIND = "idp-key"

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
    "revocation_entry_repeated",
)

#: Largest sequence number that is exact in every JSON reader (2**53 - 1).
MAX_EXACT_SEQ = (1 << 53) - 1

_BODY_MEMBERS = ("type", "listId", "seq", "previous", "issuedAt", "issuerKey", "entries")
_ENTRY_MEMBERS = ("kind", "id", "revokedAt", "reason", "successor")

_THUMBPRINT_ALPHABET = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
)
#: A base64url thumbprint of 43 digits whose last sextet carries two zero bits,
#: so one key has exactly one spelling.
_THUMBPRINT_LAST = "AEIMQUYcgkosw048"


def _is_thumbprint(s) -> bool:
    if not isinstance(s, str) or len(s) != 43:
        return False
    if any(c not in _THUMBPRINT_ALPHABET for c in s):
        return False
    return s[-1] in _THUMBPRINT_LAST


def _same_type(value) -> bool:
    """Whether ``value`` names this list type, under either host, byte-exact."""
    if not isinstance(value, str):
        return False
    for host in _LIST_HOSTS:
        if value == host + _TYPE_PATH:
            return True
    return False


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


class _Entry:
    __slots__ = ("kind", "id", "revoked_at", "successor")

    def __init__(self, kind, subject_id, revoked_at, successor):
        self.kind = kind
        self.id = subject_id
        self.revoked_at = revoked_at
        self.successor = successor


class _Body:
    __slots__ = ("list_id", "previous", "seq", "issued_at", "issuer_key", "entries", "canon")


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
    elif kind == IDP_KIND:
        if not _is_thumbprint(subject_id):
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
    return _Entry(kind, subject_id, revoked_at, successor)


def _read_body(value) -> _Body:
    if not isinstance(value, dict) or len(value) != len(_BODY_MEMBERS):
        raise _shape("body_members")
    for name in _BODY_MEMBERS:
        if name not in value:
            raise _shape("body_members")

    b = _Body()
    if not _same_type(value["type"]):
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
        b.previous = ""
    elif isinstance(previous, str):
        if seq == 1 or not _is_list_digest(previous):
            raise _shape("previous_form")
        b.previous = previous
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


class RevocationState:
    """What a verifier holds: pinned roots, the list in force, and every entry
    the chain has published up to its ``seq`` — keyed ``(kind, id)``, mapped to
    the entry's ``revokedAt``. ``seq`` 0 means no list is in force."""

    __slots__ = ("roots", "list_id", "seq", "head", "issued_at", "entries")

    def __init__(self, roots=(), list_id="", seq=0, head="", issued_at="", entries=None):
        self.roots = tuple(sorted(set(roots)))
        self.list_id = list_id
        self.seq = seq
        self.head = head
        self.issued_at = issued_at
        self.entries = dict(entries or {})

    def is_root(self, key_id: str) -> bool:
        return key_id in self.roots

    def revoked(self, kind: str, subject_id: str) -> bool:
        return (kind, subject_id) in self.entries

    def revoked_ids(self, kind: str):
        return sorted(i for (k, i) in self.entries if k == kind)

    def as_dict(self) -> dict:
        return {
            "head": self.head or None,
            "issuedAt": self.issued_at or None,
            "listId": self.list_id or None,
            "revoked": {k: self.revoked_ids(k) for k in KINDS},
            "roots": list(self.roots),
            "seq": self.seq,
        }


def apply(state: RevocationState, signed) -> RevocationState:
    """The state with ``signed`` (a parsed ``{"body", "sig"}``) as the list in
    force, or a ``Refusal``. ``state`` itself is never changed."""
    if not isinstance(signed, dict) or len(signed) != 2 or "body" not in signed or "sig" not in signed:
        raise _shape("signed_list_members")
    body = _read_body(signed["body"])

    key_id = hashlib.sha256(body.issuer_key).hexdigest()
    if not state.is_root(key_id):
        raise Refusal("revocation_list_signer_not_a_root")

    # A signature that is not the canonical base64 of 64 bytes is an
    # unverified signature, not a malformed list: the refusal says the list
    # could not be authenticated, which is the thing the reader wants to know.
    try:
        sig = _b64_strict(signed["sig"])
        if base64.b64encode(sig).decode("ascii") != signed["sig"]:
            raise ValueError("not the canonical base64 of the signature")
        if len(sig) != 64:
            raise ValueError("not 64 bytes")
        authenticated = _ed25519_verify(body.issuer_key, DOMAIN + body.canon, sig)
    except ValueError:
        raise Refusal("revocation_list_signature_unverified", "signature_not_canonical_base64") from None
    if not authenticated:
        raise Refusal("revocation_list_signature_unverified")

    if state.list_id and body.list_id != state.list_id:
        raise Refusal("revocation_list_other_chain")
    if body.seq <= state.seq:
        raise Refusal("revocation_list_rollback", "%d<=%d" % (body.seq, state.seq))
    if body.seq > state.seq + 1:
        raise Refusal("revocation_list_gap", "%d>%d" % (body.seq, state.seq + 1))
    if (state.head == "") != (body.previous == "") or body.previous != state.head:
        raise Refusal("revocation_list_previous_mismatch")
    if state.issued_at and body.issued_at < state.issued_at:
        raise Refusal("revocation_list_time_reversed")

    delta = {}
    for e in body.entries:
        if e.revoked_at > body.issued_at:
            raise Refusal("revocation_entry_from_future")
        delta[(e.kind, e.id)] = e

    for key in delta:
        if key in state.entries:
            raise Refusal("revocation_entry_repeated", "%s:%s" % (key[0], key[1][:12]))

    # A revoked key is never a root, wherever the entry sits and whichever list
    # revoked it: successors of the roots this list revokes join unless an
    # earlier list revoked them, then every key this list revokes leaves, so a
    # successor the same list revokes does not stay either.
    revoked_keys = {i for (k, i) in delta if k == "key"}
    successors = set()
    for (kind, ident), e in delta.items():
        if kind != "key" or ident not in state.roots or e.successor is None:
            continue
        successor_id = hashlib.sha256(e.successor).hexdigest()
        if ("key", successor_id) not in state.entries:
            successors.add(successor_id)
    roots = sorted((set(state.roots) | successors) - revoked_keys)

    entries = dict(state.entries)
    entries.update({k: e.revoked_at for k, e in delta.items()})

    return RevocationState(
        roots=roots,
        list_id=body.list_id,
        seq=body.seq,
        head=_digest_of_canon(body.canon),
        issued_at=body.issued_at,
        entries=entries,
    )


def verify_chain(root_ids, lists) -> dict:
    """Apply the signed lists in the order given, from a verifier holding none."""
    state = RevocationState(root_ids)
    for i, signed in enumerate(lists):
        try:
            state = apply(state, signed)
        except Refusal as r:
            return {
                "decision": "reject",
                "reason": str(r),
                "refusal": r.as_dict(),
                "index": i,
                "state": state.as_dict(),
            }
    return {
        "decision": "accept",
        "reason": "in_force",
        "refusal": None,
        "index": None,
        "state": state.as_dict(),
    }


def _members(document):
    """The cases in a shared vectors file, refusing anything else."""
    if not isinstance(document, list) or not document:
        raise ValueError("the suite is not a non-empty list of cases")
    out = []
    for case in document:
        if not isinstance(case, dict):
            raise ValueError("a case is not an object")
        for name in ("id", "roots", "lists", "expected"):
            if name not in case:
                raise ValueError("a case is missing " + name)
        if not isinstance(case["roots"], list) or not isinstance(case["lists"], list):
            raise ValueError("case %r has a roots or lists field that is not a list" % (case.get("id"),))
        out.append(case)
    return out


def load_suite(path: str):
    """Parse a shared vectors file under the strict profile, without the
    exact-integer walk.

    The suite is a *container* of signed lists, not a signed list: one case
    deliberately carries a sequence number outside the exact range, and its
    point is that a reader refuses it as a shape fault rather than as unreadable
    bytes. Duplicate members, non-scalar strings, floats, bad UTF-8 and
    over-deep nesting still make the whole file unreadable — a reader that
    silently skipped one case would report a smaller denominator as if it were
    the same test.
    """
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        top = _parse_json_value(raw)
    except _IJsonError:
        raise ValueError("the suite file is not readable JSON under the strict profile") from None
    return _members(top)


def judge_case(case: dict) -> dict:
    return verify_chain(case["roots"], case["lists"])


_FIELDS = ("decision", "reason", "index", "state")


def judge_suite(path: str) -> dict:
    """Judge every case against the answer key the file ships with."""
    records = []
    conforming = 0
    for case in load_suite(path):
        got = judge_case(case)
        expected = case["expected"]
        # A refusal is compared on decision, reason and index; an acceptance on
        # decision, reason and the whole folded state.
        if expected.get("state") is not None:
            compared = ("decision", "reason", "state")
        else:
            compared = ("decision", "reason", "index")
            got = dict(got)
            got["reason"] = got["refusal"]["code"] if got["refusal"] else got["reason"]
        got_view = {f: got.get(f) for f in compared}
        want_view = {}
        if expected.get("state") is not None:
            want_view = {"decision": "accept", "reason": "in_force", "state": expected["state"]}
        else:
            want_view = {"decision": "reject", "reason": expected.get("refused"), "index": expected.get("index")}
        mismatched = [f for f in compared if got_view.get(f) != want_view.get(f)]
        ok = not mismatched
        conforming += 1 if ok else 0
        records.append({
            "id": case.get("id"),
            "description": case.get("description"),
            "got": got_view,
            "expected": want_view,
            "conforms": ok,
            "mismatched": mismatched,
        })
    return {"members": len(records), "conforming": conforming, "records": records}


def judge_chain_file(path: str) -> dict:
    """Judge one chain document ``{"roots": [...], "lists": [{body, sig}, …]}``."""
    with open(path, "rb") as fh:
        raw = fh.read()
    try:
        top = _parse_json_value(raw)
    except _IJsonError:
        raise ValueError("the chain file is not readable JSON under the strict profile") from None
    if not isinstance(top, dict) or set(top) != {"roots", "lists"}:
        raise ValueError("a chain document is exactly {roots, lists}")
    if not isinstance(top["roots"], list) or not isinstance(top["lists"], list):
        raise ValueError("roots and lists must be lists")
    return verify_chain(top["roots"], top["lists"])
