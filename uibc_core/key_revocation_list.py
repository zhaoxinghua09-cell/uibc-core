"""Read the signed key-revocation list authored elsewhere.

The format is the peer's ``key-revocation-list/v1``: one signed list is
``{"list": BODY, "sig": base64(Ed25519 over JCS(BODY)), "signer": {"key":
hex, "thumbprint": hex}}``. A verifier holds the thumbprints of the list
signing keys it trusts, the issue time of the last list it accepted and the
revocations it has already seen, and is asked whether one key is revoked at
one time.

This reader applies the peer's four checks in the peer's order and names the
first that fails, then reads a list that passes together with the revocations
already seen:

1. the signer is trusted by the SHA-256 thumbprint **recomputed from the key
   the envelope carries**, never by the thumbprint the envelope claims
   (``signer_not_trusted``);
2. the list verifies under that key (``list_signature_invalid``);
3. the list was not issued before the last list accepted
   (``list_older_than_accepted``), because a replayed older list can omit a
   revocation a newer one carries;
4. the verifier's clock is not past ``nextUpdate`` (``list_stale``).

A revocation once seen is kept even when a later list omits it, and a person
who is not mentioned at all is ``no_statement`` rather than ``not_revoked``:
silence about a key is not a statement about it.

Two things this reader refuses that the reference reader folds silently, both
named as ``key_revocation_list_shape`` or ``key_revocation_list_conflict``
rather than answered: a record whose instants are not the one UTC spelling
this suite compares as text, and two entries for one key that disagree about
when the revocation takes effect. The last-wins dictionary the reference
builds would answer either way without saying which record it answered from.

Canonicalization (RFC 8785 under an integers-only I-JSON profile) and Ed25519
verification (RFC 8032) are the ones this package already uses for the
evidence tier, so the same bytes give the same verdict on both sides.
"""

from __future__ import annotations

import base64
import datetime
import hashlib
import json
import os
import re

from .aee import (
    _IJsonError,
    _ed25519_verify,
    _jcs_dumps,
    _parse_json_value,
    _walk_check_ints,
)

SUITE = "key-revocation-list/v1"
REPORT_FORMAT = "uibc-key-revocation-list-report/1"

#: The five decisions, and the exit code the external-verifier contract assigns.
DECISIONS = ("revoked", "not_revoked", "no_statement", "rejected", "stale")
EXIT_FOR = {
    "revoked": 0,
    "not_revoked": 1,
    "no_statement": 2,
    "rejected": 3,
    "stale": 4,
}

#: The peer's reason tokens, in the order the reader can reach them.
REASONS = (
    "signer_not_trusted",
    "list_signature_invalid",
    "list_older_than_accepted",
    "list_stale",
    "revoked_in_list",
    "revoked_kept_from_earlier_list",
    "revocation_not_yet_effective",
    "key_not_covered",
    "covered_no_entry",
)

#: This reader's own refusals, for states the reference reader answers instead.
CODES = ("key_revocation_list_shape", "key_revocation_list_conflict")

_LIST_MEMBERS = ("issuedAt", "issuer", "keysCovered", "nextUpdate", "revoked")
_INSTANT = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")


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
    return Refusal("key_revocation_list_shape", why)


def _conflict(why: str) -> Refusal:
    return Refusal("key_revocation_list_conflict", why)


def _is_hex64(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _read_instant(value, what: str) -> datetime.datetime:
    """An instant under the one spelling this suite compares as text."""
    if not isinstance(value, str) or not _INSTANT.match(value):
        raise _shape(what + "_not_a_utc_second")
    try:
        return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=datetime.timezone.utc
        )
    except ValueError:
        raise _shape(what + "_not_a_calendar_instant")


def thumbprint(key_hex: str) -> str:
    """SHA-256 over the raw public key: recomputed, never taken on trust."""
    if not _is_hex64(key_hex):
        raise _shape("signer_key_not_hex64")
    return hashlib.sha256(bytes.fromhex(key_hex)).hexdigest()


def _load_json(path: str):
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        raise Refusal("unreadable", "cannot read " + os.path.basename(path) + ": " + str(exc))
    try:
        value = _parse_json_value(raw)
        _walk_check_ints(value)
    except (_IJsonError, RecursionError):
        raise _shape("not_i_json")
    return value


def _is_plain_object(value) -> bool:
    return isinstance(value, dict)


def read_envelope(value) -> tuple[dict, bytes, str, str, bool, bool]:
    """The list body, the signer's key bytes, its claimed thumbprint, and two facts.

    The two facts are what the corpus declares about a case: whether the
    claimed thumbprint is the honest one, and whether the signature verifies
    under the key the envelope carries. Both are recomputed here, so a claim
    in a file cannot stand in for a check.
    """
    if not _is_plain_object(value):
        raise _shape("envelope_not_an_object")
    for member in ("list", "sig", "signer"):
        if member not in value:
            raise _shape("envelope_missing_" + member)
    body, signer = value["list"], value["signer"]
    if not _is_plain_object(body):
        raise _shape("list_not_an_object")
    if not _is_plain_object(signer):
        raise _shape("signer_not_an_object")
    if "key" not in signer or "thumbprint" not in signer:
        raise _shape("signer_members")
    for member in _LIST_MEMBERS:
        if member not in body:
            raise _shape("list_missing_" + member)
    if not isinstance(body["issuer"], str) or not body["issuer"]:
        raise _shape("issuer_not_text")
    if not isinstance(body["keysCovered"], list) or not all(
        _is_hex64(k) for k in body["keysCovered"]
    ):
        raise _shape("keysCovered_not_hex64_list")
    if not isinstance(body["revoked"], list):
        raise _shape("revoked_not_a_list")
    if not _is_hex64(signer["key"]):
        raise _shape("signer_key_not_hex64")
    if not _is_hex64(signer["thumbprint"]):
        raise _shape("signer_thumbprint_not_hex64")
    issued = _read_instant(body["issuedAt"], "issuedAt")
    due = _read_instant(body["nextUpdate"], "nextUpdate")
    if due < issued:
        raise _shape("nextUpdate_before_issuedAt")
    for entry in body["revoked"]:
        if not _is_plain_object(entry):
            raise _shape("entry_not_an_object")
        for member in ("effectiveFrom", "thumbprint"):
            if member not in entry:
                raise _shape("entry_members")
        if not _is_hex64(entry["thumbprint"]):
            raise _shape("entry_thumbprint_not_hex64")
        _read_instant(entry["effectiveFrom"], "effectiveFrom")
    sig = value["sig"]
    if not isinstance(sig, str):
        raise _shape("sig_not_text")
    try:
        sig_bytes = base64.b64decode(sig, validate=True)
    except (ValueError, TypeError):
        raise _shape("sig_not_base64")
    if len(sig_bytes) != 64:
        raise _shape("sig_not_64_bytes")
    key_bytes = bytes.fromhex(signer["key"])
    honest = signer["thumbprint"] == hashlib.sha256(key_bytes).hexdigest()
    verifies = _ed25519_verify(key_bytes, _jcs_dumps(body), sig_bytes)
    return body, key_bytes, signer["thumbprint"], sig, honest, verifies


def read_case(value) -> dict:
    """The case file, split into the inputs the reader needs and checked."""
    if not _is_plain_object(value):
        raise _shape("case_not_an_object")
    for member in ("list", "now", "query", "suite"):
        if member not in value:
            raise _shape("case_missing_" + member)
    if value["suite"] != SUITE:
        raise _shape("case_suite_mismatch")
    if not isinstance(value["list"], str) or not value["list"]:
        raise _shape("case_list_not_text")
    trusted = value.get("trusted")
    if not isinstance(trusted, list) or not all(_is_hex64(t) for t in trusted):
        raise _shape("trusted_not_hex64_list")
    query = value["query"]
    if not _is_plain_object(query):
        raise _shape("query_not_an_object")
    for member in ("at", "key"):
        if member not in query:
            raise _shape("query_missing_" + member)
    if not _is_hex64(query["key"]):
        raise _shape("query_key_not_hex64")
    at = _read_instant(query["at"], "query_at")
    now = _read_instant(value["now"], "now")
    prior = value.get("prior") or {}
    if not _is_plain_object(prior):
        raise _shape("prior_not_an_object")
    accepted = prior.get("acceptedIssuedAt")
    accepted_at = None if accepted is None else _read_instant(accepted, "acceptedIssuedAt")
    seen = prior.get("seen")
    if seen is None:
        seen = []
    if not isinstance(seen, list):
        raise _shape("prior_seen_not_a_list")
    seen_map: dict[str, datetime.datetime] = {}
    for entry in seen:
        if not _is_plain_object(entry):
            raise _shape("prior_seen_entry_not_an_object")
        for member in ("effectiveFrom", "thumbprint"):
            if member not in entry:
                raise _shape("prior_seen_entry_members")
        if not _is_hex64(entry["thumbprint"]):
            raise _shape("prior_seen_thumbprint_not_hex64")
        when = _read_instant(entry["effectiveFrom"], "prior_seen_effectiveFrom")
        seen_map = _remember(seen_map, entry["thumbprint"], when, "prior.seen")
    return {
        "trusted": trusted,
        "accepted": accepted_at,
        "seen": seen_map,
        "key": query["key"],
        "at": at,
        "now": now,
        "list": value["list"],
    }


def _remember(mapping: dict, key: str, when: datetime.datetime, where: str) -> dict:
    """Record one key's revocation time; two records that disagree are a refusal."""
    if key in mapping and mapping[key] != when:
        raise _conflict(where + ":two_times_for_" + key[:12])
    result = dict(mapping)
    result[key] = when
    return result


def _entries(body: dict) -> dict[str, datetime.datetime]:
    """The revocations a list carries, keeping the one time each key has."""
    found: dict[str, datetime.datetime] = {}
    for entry in body["revoked"]:
        when = datetime.datetime.strptime(
            entry["effectiveFrom"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=datetime.timezone.utc)
        found = _remember(found, entry["thumbprint"], when, "list.revoked")
    return found


def judge(case_value, envelope_value) -> tuple[dict, dict, dict]:
    """Answer one case: the decision, what the answer rests on, and the recorded facts.

    ``basis`` names which of the reader's rules produced the answer
    (``trusted_by_recomputed_thumbprint``, ``signature``, ``freshness``,
    ``retained`` or ``absent``), so a decision can be audited without re-deriving
    it from the same code that produced it.
    """
    body, key_bytes, claimed, _sig, honest, verifies = read_envelope(envelope_value)
    inputs = read_case(case_value)
    facts = {
        "signerThumbprintHonest": honest,
        "signatureVerifiesUnderCarriedKey": verifies,
        "claimedThumbprint": claimed,
        "recomputedThumbprint": hashlib.sha256(key_bytes).hexdigest(),
    }
    trusted = hashlib.sha256(key_bytes).hexdigest() in inputs["trusted"]
    if not trusted:
        return ({"decision": "rejected", "reason": "signer_not_trusted"},
                {"rule": "trusted_by_recomputed_thumbprint", "trusted": False}, facts)
    if not verifies:
        return ({"decision": "rejected", "reason": "list_signature_invalid"},
                {"rule": "signature", "verifies": False}, facts)
    issued = _read_instant(body["issuedAt"], "issuedAt")
    if inputs["accepted"] is not None and issued < inputs["accepted"]:
        return ({"decision": "rejected", "reason": "list_older_than_accepted"},
                {"rule": "freshness", "olderThanAccepted": True}, facts)
    if inputs["now"] > _read_instant(body["nextUpdate"], "nextUpdate"):
        return ({"decision": "stale", "reason": "list_stale"},
                {"rule": "freshness", "pastNextUpdate": True}, facts)

    key, at = inputs["key"], inputs["at"]
    entries = _entries(body)
    kept = inputs["seen"]
    if key in entries and entries[key] <= at:
        return ({"decision": "revoked", "reason": "revoked_in_list"},
                {"rule": "in_list", "effectiveFrom": entries[key].isoformat()}, facts)
    if key in kept and kept[key] <= at:
        return ({"decision": "revoked", "reason": "revoked_kept_from_earlier_list"},
                {"rule": "retained", "effectiveFrom": kept[key].isoformat()}, facts)
    if key in entries or key in kept:
        when = entries.get(key) or kept.get(key)
        return ({"decision": "not_revoked", "reason": "revocation_not_yet_effective"},
                {"rule": "in_list", "effectiveFrom": when.isoformat()}, facts)
    if key not in body["keysCovered"]:
        return ({"decision": "no_statement", "reason": "key_not_covered"},
                {"rule": "absent", "covered": False}, facts)
    return ({"decision": "not_revoked", "reason": "covered_no_entry"},
            {"rule": "absent", "covered": True}, facts)


def judge_case(case_path: str) -> dict:
    """Judge one ``case.json``: the decision, the reason, and what it rests on."""
    case_dir = os.path.dirname(os.path.abspath(case_path))
    case_value = _load_json(os.path.abspath(case_path))
    if not isinstance(case_value, dict):
        raise _shape("case_not_an_object")
    list_name = case_value.get("list")
    if not isinstance(list_name, str) or not list_name:
        raise _shape("case_list_not_text")
    envelope = _load_json(os.path.join(case_dir, list_name))
    decision, basis, facts = judge(case_value, envelope)
    return {"decision": decision["decision"], "reason": decision["reason"],
            "exit": EXIT_FOR[decision["decision"]], "basis": basis, "facts": facts}


def judge_case_or_refusal(case_path: str) -> dict:
    """Judge a case, turning this reader's own refusals into ``rejected`` answers."""
    try:
        return judge_case(case_path)
    except Refusal as refusal:
        return {
            "decision": "rejected",
            "reason": refusal.code,
            "detail": refusal.detail,
            "exit": EXIT_FOR["rejected"],
            "basis": {"rule": "shape", "refusal": str(refusal)},
            "facts": {},
        }


def retained(case_path: str) -> dict:
    """The two facts the corpus declares about a case, recomputed from its bytes."""
    case_value = _load_json(os.path.abspath(case_path))
    list_name = case_value["list"]
    envelope = _load_json(os.path.join(os.path.dirname(os.path.abspath(case_path)), list_name))
    _body, _key, _claimed, _sig, honest, verifies = read_envelope(envelope)
    return {
        "signerThumbprintHonest": honest,
        "signatureVerifiesUnderCarriedKey": verifies,
    }


def iter_cases(corpus: str):
    """Yield ``(vector, case_path)`` for a corpus laid out like the peer's."""
    with open(os.path.join(corpus, "MANIFEST.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    for vector in manifest.get("vectors") or []:
        path = os.path.join(corpus, vector.get("path") or os.path.join("cases", vector["id"]),
                            "case.json")
        yield vector, path


def judge_corpus(corpus: str) -> dict:
    """Judge every member of a corpus against its own answer key."""
    records = []
    conforming = 0
    for vector, case_path in iter_cases(corpus):
        expected = vector.get("expected") or {}
        got = judge_case_or_refusal(case_path)
        fields = ("decision", "reason")
        mismatched = [f for f in fields if got.get(f) != expected.get(f)]
        facts_ok = True
        if vector.get("retained") is not None:
            try:
                facts_ok = retained(case_path) == vector["retained"]
            except Refusal:
                facts_ok = False
            if not facts_ok:
                mismatched.append("retained")
        ok = not mismatched
        conforming += 1 if ok else 0
        records.append({
            "id": vector.get("id"),
            "got": {f: got.get(f) for f in fields},
            "expected": {f: expected.get(f) for f in fields},
            "retained": facts_ok,
            "conforms": ok,
            "mismatched": mismatched,
        })
    return {"members": len(records), "conforming": conforming, "records": records}
