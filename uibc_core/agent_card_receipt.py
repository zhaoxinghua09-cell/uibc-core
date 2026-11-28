"""Judge a receipt that binds an evaluation result to the A2A card an agent serves.

The suite is `agent-card-receipt/v1`: someone other than the agent ran it, graded
it, and signed the grade over the card's bytes. This reader is handed the card as
served, the unsigned receipt statement, the issuer's signed revocation list, the
issuer's public key and the time of the check, and answers one of two things —
`accept` with the reason `receipt_current`, or `reject` with the first rule that
failed.

Two things make the reading hard, and both are deliberate:

* the subject digest is over the RFC 8785 form of the card **without its
  top-level `signatures`**, at the parsed-name level, once, and never
  recursively (A2A 8.4.1 rules 2 and 3). A card with signatures and the same card
  without them have one digest, an `additionalSignatures` member is *not*
  excluded, and a member named by an escape (`signatur\\u0065s`) *is*;
* a verifier that cannot read the revocation state does not know the receipt is
  good, so a missing, unreadable, foreign-signed or stale list is a refusal and
  never a clean pass.

This reader mints and signs nothing.
"""

import hashlib
import json
import os
import re

from .aee import (MAX_PARSE_BYTES, MAX_PARSE_DEPTH, SAFE_INT_LIMIT, _JcsError,
                  _StringNotScalarError, _b64decode_strict, _check_string_scalars,
                  _ed25519_verify, _jcs_string, _max_json_depth, _pae,
                  _reject_dup_pairs, _utf16_sort_key)

SUITE = "agent-card-receipt/v1"
REPORT_FORMAT = "uibc-agent-card-receipt-report/1"

STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://w3id.org/agent-evidence/predicate/v1/agent-card-receipt"
PAYLOAD_TYPE = "application/vnd.agent-evidence.agent-card-receipt-revocations.v1+json"

#: Two decisions: the receipt holds, or the first rule that failed says why.
DECISIONS = ("accept", "reject")

#: The sixteen reasons, in the order the reader can reach them.
REASONS = (
    "receipt_current",
    "statement_malformed",
    "statement_type_wrong",
    "predicate_type_wrong",
    "subject_malformed",
    "predicate_malformed",
    "validity_window_inverted",
    "card_malformed",
    "card_digest_mismatch",
    "receipt_not_yet_valid",
    "receipt_expired",
    "revocation_list_absent",
    "revocation_list_malformed",
    "revocation_list_signature",
    "revocation_list_stale",
    "receipt_revoked",
)

#: The result lattice, lowest first. This reader does not rank results; it only
#: refuses a value outside the vocabulary.
RESULTS = ("fail", "degraded", "pass_indirect", "pass")

_STATEMENT_MEMBERS = ("_type", "subject", "predicateType", "predicate")
_PREDICATE_MEMBERS = ("run", "result", "registryDigest", "issuedAt", "validUntil",
                      "revocationList")
_PREDICATE_OPTIONAL = ("agentKeyThumbprints",)
_LIST_MEMBERS = ("issuedAt", "nextUpdate", "revoked")

_INSTANT = re.compile(r"\A[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z\Z")
_HEX64 = re.compile(r"\A[0-9a-f]{64}\Z")
_THUMB = re.compile(r"\A[A-Za-z0-9_-]{43}\Z")
_HTTPS = re.compile(r"\Ahttps://[^\s]+\Z")


class Refusal(Exception):
    """A refusal, rendered as ``reason`` or ``reason:detail``.

    ``facts`` carries whatever the reader had already established when it stopped
    — the card digest above all — so a report can show what it computed rather
    than only that it refused.
    """

    def __init__(self, reason, detail="", facts=None):
        super().__init__(reason + (":" + detail if detail else ""))
        self.reason = reason
        self.detail = detail
        self.facts = facts or {}

    def __str__(self):
        return self.reason + (":" + self.detail if self.detail else "")


# ---------------------------------------------------------------------------
# Strict JSON, and RFC 8785 over numbers that are not only integers
#
# The house canonicaliser is an integers-only profile: it refuses a fractional
# float outright, which is right for the payloads it was written for and wrong
# for an A2A card, where `0.93` and `1e-06` are ordinary. RFC 8785 does not
# forbid them; it defines them by ECMAScript's Number::toString. So this module
# carries the ES6 form of a number and sorts member names by UTF-16 code units,
# which is what the digest has to reproduce.
# ---------------------------------------------------------------------------

def _strict_parse(raw, reason):
    """Parse under strict JSON: no duplicate member, no lone surrogate, no
    non-finite number, no integer of magnitude 2^53 or more."""
    if len(raw) > MAX_PARSE_BYTES:
        raise Refusal(reason, "input exceeds the maximum size")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise Refusal(reason, "input is not UTF-8")
    if _max_json_depth(text) > MAX_PARSE_DEPTH:
        raise Refusal(reason, "nesting exceeds the maximum depth")

    def _no_const(name):
        raise ValueError("non-finite number %s" % name)

    try:
        obj = json.loads(text, object_pairs_hook=_reject_dup_pairs,
                         parse_constant=_no_const)
    except ValueError as exc:
        raise Refusal(reason, "does not parse as strict JSON: %s" % exc)
    except RecursionError:
        raise Refusal(reason, "does not parse as strict JSON: nesting")
    try:
        _check_string_scalars(raw)
    except _StringNotScalarError as exc:
        raise Refusal(reason, "string is not scalar: %s" % exc)
    _check_numbers(obj, reason)
    return obj


def _check_numbers(v, reason):
    if isinstance(v, bool):
        return
    if isinstance(v, int):
        if abs(v) >= SAFE_INT_LIMIT:
            raise Refusal(reason, "integer of magnitude 2^53 or more")
        return
    if isinstance(v, float):
        if v != v or v in (float("inf"), float("-inf")):
            raise Refusal(reason, "non-finite number")
        return
    if isinstance(v, list):
        for x in v:
            _check_numbers(x, reason)
    elif isinstance(v, dict):
        for x in v.values():
            _check_numbers(x, reason)


def _es_number(x):
    """ECMAScript Number::toString for a finite double (RFC 8785 §3.2.4)."""
    if x != x or x in (float("inf"), float("-inf")):
        raise _JcsError("non-finite number")
    if x == 0:
        return "0"
    sign = "-" if x < 0 else ""
    rep = repr(abs(x))
    if "e" in rep or "E" in rep:
        mant, exp = re.split("[eE]", rep)
        exp = int(exp)
    else:
        mant, exp = rep, 0
    ip, _, fp = mant.partition(".")
    digits = (ip + fp).lstrip("0")
    e = exp - len(fp)
    if not digits:
        return "0"
    stripped = digits.rstrip("0")
    e += len(digits) - len(stripped)
    digits = stripped
    k = len(digits)
    n = k + e
    if k <= n <= 21:
        out = digits + "0" * (n - k)
    elif 0 < n <= 21:
        out = digits[:n] + "." + digits[n:]
    elif -6 < n <= 0:
        out = "0." + "0" * (-n) + digits
    else:
        out = digits[0] + ("." + digits[1:] if k > 1 else "") \
            + "e" + ("+" if n - 1 >= 0 else "-") + str(abs(n - 1))
    return sign + out


def _canon(v):
    """RFC 8785 canonical form: UTF-16 member order, ES6 numbers, raw UTF-8."""
    if v is None:
        return "null"
    if v is True:
        return "true"
    if v is False:
        return "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return _es_number(v)
    if isinstance(v, str):
        return _jcs_string(v)
    if isinstance(v, list):
        return "[" + ",".join(_canon(x) for x in v) + "]"
    if isinstance(v, dict):
        keys = sorted(v.keys(), key=_utf16_sort_key)
        return "{" + ",".join(_jcs_string(k) + ":" + _canon(v[k]) for k in keys) + "}"
    raise _JcsError("unsupported type: %r" % (type(v),))


# ---------------------------------------------------------------------------
# The three byte-level readings
# ---------------------------------------------------------------------------

def card_digest(card_bytes):
    """SHA-256 of the RFC 8785 form of the card without its top-level signatures.

    The exclusion happens on the *parsed* name, so a member written with an JSON
    escape is the same member; it happens once, so a `signatures` nested in an
    extension stays in the bytes; and it excludes that one member only, so an
    `additionalSignatures` the catalog format reserves is digested as served.
    """
    try:
        card = _strict_parse(card_bytes, "card_malformed")
    except Refusal:
        raise
    if not isinstance(card, dict):
        raise Refusal("card_malformed", "the card is not a JSON object")
    kept = {k: v for k, v in card.items() if k != "signatures"}
    try:
        canon = _canon(kept).encode("utf-8")
    except _JcsError as exc:
        raise Refusal("card_malformed", "no RFC 8785 form: %s" % exc)
    return hashlib.sha256(canon).hexdigest()


def read_statement(statement_bytes):
    """The unsigned receipt statement, under strict JSON (duplicates refused)."""
    try:
        obj = _strict_parse(statement_bytes, "statement_malformed")
    except Refusal:
        raise
    if not isinstance(obj, dict):
        raise Refusal("statement_malformed", "the statement is not a JSON object")
    if set(obj) != set(_STATEMENT_MEMBERS):
        missing = sorted(set(_STATEMENT_MEMBERS) - set(obj))
        extra = sorted(set(obj) - set(_STATEMENT_MEMBERS))
        raise Refusal("statement_malformed",
                      "members %s" % (", ".join(["missing " + m for m in missing]
                                                + ["unexpected " + m for m in extra])))
    if obj["_type"] != STATEMENT_TYPE:
        raise Refusal("statement_type_wrong", "_type is %r" % (obj["_type"],))
    if obj["predicateType"] != PREDICATE_TYPE:
        raise Refusal("predicate_type_wrong", "predicateType is %r" % (obj["predicateType"],))
    _check_subject(obj["subject"])
    predicate = obj["predicate"]
    _check_predicate(predicate)
    return obj


def _check_subject(subject):
    if not isinstance(subject, list) or len(subject) != 1:
        raise Refusal("subject_malformed", "subject must hold exactly one member")
    entry = subject[0]
    if not isinstance(entry, dict) or set(entry) != {"name", "digest"}:
        raise Refusal("subject_malformed", "the subject member carries name and digest only")
    if not isinstance(entry["name"], str) or not entry["name"]:
        raise Refusal("subject_malformed", "subject name is not a non-empty string")
    digest = entry["digest"]
    if not isinstance(digest, dict) or set(digest) != {"sha256"}:
        raise Refusal("subject_malformed", "digest must hold exactly sha256")
    if not isinstance(digest["sha256"], str) or not _HEX64.match(digest["sha256"]):
        raise Refusal("subject_malformed", "digest is not 64 lower-case hex characters")


def _check_predicate(pred):
    if not isinstance(pred, dict):
        raise Refusal("predicate_malformed", "the predicate is not a JSON object")
    missing = sorted(set(_PREDICATE_MEMBERS) - set(pred))
    extra = sorted(set(pred) - set(_PREDICATE_MEMBERS) - set(_PREDICATE_OPTIONAL))
    if missing or extra:
        raise Refusal("predicate_malformed",
                      "members %s" % (", ".join(["missing " + m for m in missing]
                                                + ["unexpected " + m for m in extra])))
    run = pred["run"]
    if not isinstance(run, dict) or set(run) != {"predicateType", "digest"}:
        raise Refusal("predicate_malformed", "run carries predicateType and digest only")
    if not isinstance(run["predicateType"], str) or not _HTTPS.match(run["predicateType"]):
        raise Refusal("predicate_malformed", "run predicateType is not an https URL")
    if not isinstance(run["digest"], dict) or set(run["digest"]) != {"sha256"} \
            or not isinstance(run["digest"]["sha256"], str) \
            or not _HEX64.match(run["digest"]["sha256"]):
        raise Refusal("predicate_malformed", "run digest is not a sha256 of 64 lower-case hex")
    if pred["result"] not in RESULTS:
        raise Refusal("predicate_malformed", "result %r is outside the vocabulary" % (pred["result"],))
    reg = pred["registryDigest"]
    if not isinstance(reg, dict) or set(reg) != {"sha256"} \
            or not isinstance(reg["sha256"], str) or not _HEX64.match(reg["sha256"]):
        raise Refusal("predicate_malformed", "registryDigest is not a sha256 of 64 lower-case hex")
    for name in ("issuedAt", "validUntil"):
        if not isinstance(pred[name], str) or not _INSTANT.match(pred[name]):
            raise Refusal("predicate_malformed",
                          "%s is not a UTC instant to whole seconds" % name)
    if not isinstance(pred["revocationList"], str) or not _HTTPS.match(pred["revocationList"]):
        raise Refusal("predicate_malformed", "revocationList is not an https URL")
    if "agentKeyThumbprints" in pred:
        thumbs = pred["agentKeyThumbprints"]
        if not isinstance(thumbs, list) or not thumbs:
            raise Refusal("predicate_malformed", "agentKeyThumbprints must be a non-empty list")
        if any(not isinstance(t, str) or not _THUMB.match(t) for t in thumbs):
            raise Refusal("predicate_malformed",
                          "an agent key thumbprint is not 43 base64url characters")
        if thumbs != sorted(set(thumbs)):
            raise Refusal("predicate_malformed",
                          "agentKeyThumbprints must be sorted and duplicate-free")


def read_revocations(list_bytes, issuer_key, now):
    """The signed revocation list: envelope, payload, signature, window.

    A list nobody signed with the receipt signer's key, or one whose window does
    not hold the check time, is refused — the reader cannot claim the receipt is
    good when it cannot read the revocation state.
    """
    try:
        env = _strict_parse(list_bytes, "revocation_list_malformed")
    except Refusal:
        raise
    if not isinstance(env, dict):
        raise Refusal("revocation_list_malformed", "the envelope is not a JSON object")
    if set(env) != {"payload", "payloadType", "signatures"}:
        raise Refusal("revocation_list_malformed",
                      "the envelope carries payload, payloadType and signatures only")
    if env["payloadType"] != PAYLOAD_TYPE:
        raise Refusal("revocation_list_malformed",
                      "payloadType is %r" % (env["payloadType"],))
    try:
        payload = _b64decode_strict(env["payload"])
    except (ValueError, TypeError) as exc:
        raise Refusal("revocation_list_malformed", "payload is not canonical base64: %s" % exc)
    try:
        body = _strict_parse(payload, "revocation_list_malformed")
    except Refusal as exc:
        raise Refusal("revocation_list_malformed", "payload: " + str(exc))
    if not isinstance(body, dict) or set(body) != set(_LIST_MEMBERS):
        raise Refusal("revocation_list_malformed",
                      "the payload carries issuedAt, nextUpdate and revoked only")
    for name in ("issuedAt", "nextUpdate"):
        if not isinstance(body[name], str) or not _INSTANT.match(body[name]):
            raise Refusal("revocation_list_malformed",
                          "payload %s is not a UTC instant to whole seconds" % name)
    revoked = body["revoked"]
    if not isinstance(revoked, list) or any(
            not isinstance(r, str) or not _HEX64.match(r) for r in revoked):
        raise Refusal("revocation_list_malformed",
                      "revoked must be a list of 64 lower-case hex digests")
    if revoked != sorted(set(revoked)):
        raise Refusal("revocation_list_malformed", "revoked must be sorted and duplicate-free")

    sigs = env["signatures"]
    if not isinstance(sigs, list) or not sigs:
        raise Refusal("revocation_list_malformed", "the envelope carries no signature")
    pae = _pae(PAYLOAD_TYPE, payload)
    verified = False
    for sig in sigs:
        if not isinstance(sig, dict) or not isinstance(sig.get("sig"), str):
            continue
        try:
            raw = _b64decode_strict(sig["sig"])
        except ValueError:
            continue
        if _ed25519_verify(issuer_key, pae, raw):
            verified = True
            break
    if not verified:
        raise Refusal("revocation_list_signature",
                      "no signature on the list verifies under the receipt signer's key")
    if not (body["issuedAt"] <= now < body["nextUpdate"]):
        raise Refusal("revocation_list_stale",
                      "the check time %s is outside [%s, %s)"
                      % (now, body["issuedAt"], body["nextUpdate"]))
    return body


def judge(statement_bytes, card_bytes, list_bytes, issuer_key, now):
    """Apply the fifteen rules in order and report the first that fails."""
    stmt = read_statement(statement_bytes)
    issued = stmt["predicate"]["issuedAt"]
    until = stmt["predicate"]["validUntil"]
    if not issued < until:
        raise Refusal("validity_window_inverted",
                      "issuedAt %s is not before validUntil %s" % (issued, until))
    digest = card_digest(card_bytes)
    declared = stmt["subject"][0]["digest"]["sha256"]
    facts = {"subject_digest": digest}
    if digest != declared:
        raise Refusal("card_digest_mismatch",
                      "the card digests to %s, the receipt names %s"
                      % (digest[:16], declared[:16]), facts)
    if now < issued:
        raise Refusal("receipt_not_yet_valid",
                      "the check time %s is before %s" % (now, issued), facts)
    if not now < until:
        raise Refusal("receipt_expired",
                      "the check time %s is at or after %s" % (now, until), facts)
    if list_bytes is None:
        raise Refusal("revocation_list_absent", "no list was supplied", facts)
    body = read_revocations(list_bytes, issuer_key, now)
    statement_digest = hashlib.sha256(statement_bytes).hexdigest()
    if statement_digest in body["revoked"]:
        raise Refusal("receipt_revoked",
                      "the list names this statement (%s)" % statement_digest[:16], facts)
    return {"decision": "accept", "reason": "receipt_current",
            "subjectDigest": digest, "statementDigest": statement_digest,
            "result": stmt["predicate"]["result"]}


# ---------------------------------------------------------------------------
# Cases and corpora
# ---------------------------------------------------------------------------

_CASE_FILES = ("card.json", "statement.json", "context.json")
_LIST_FILE = "revocations.json"


def read_case(case_dir):
    """One case directory: the three required files plus the list, if present.

    A missing `revocations.json` is passed through as None rather than raised
    here: rule 11 is about the *list* being absent, and a reader that fails at
    the filesystem level would report it as an unreadable case instead.
    """
    blobs = {}
    for name in _CASE_FILES:
        paths = [os.path.join(case_dir, name)]
        with open(paths[0], "rb") as fh:
            blobs[name] = fh.read()
    list_path = os.path.join(case_dir, _LIST_FILE)
    blobs[_LIST_FILE] = open(list_path, "rb").read() if os.path.isfile(list_path) else None
    return blobs


def _context(blob):
    try:
        ctx = _strict_parse(blob, "context")
    except Refusal as exc:
        raise ValueError(str(exc))
    if not isinstance(ctx, dict) or set(ctx) != {"issuerKey", "now"}:
        raise ValueError("context carries issuerKey and now only")
    try:
        key = _b64decode_strict(ctx["issuerKey"])
    except ValueError as exc:
        raise ValueError("context issuerKey: %s" % exc)
    if len(key) != 32:
        raise ValueError("context issuerKey is not 32 bytes")
    if not isinstance(ctx["now"], str) or not _INSTANT.match(ctx["now"]):
        raise ValueError("context now is not a UTC instant to whole seconds")
    return key, ctx["now"]


def judge_case(case_dir):
    """Judge one case directory and return the report-shaped decision."""
    blobs = read_case(case_dir)
    issuer_key, now = _context(blobs["context.json"])
    try:
        got = judge(blobs["statement.json"], blobs["card.json"],
                    blobs[_LIST_FILE], issuer_key, now)
    except Refusal as refusal:
        return {"decision": "reject", "reason": refusal.reason,
                "detail": refusal.detail,
                "subjectDigest": refusal.facts.get("subject_digest"), "exit": 1}
    return dict(got, detail="", exit=0)


def iter_cases(corpus):
    """Every manifest member with its declared decision, in manifest order."""
    import json
    with open(os.path.join(corpus, "MANIFEST.json"), encoding="utf-8") as fh:
        manifest = json.load(fh)
    for vector in manifest["vectors"]:
        yield vector, os.path.join(corpus, vector["path"])


def judge_corpus(corpus):
    """Judge every member against the answer key it declares."""
    records = []
    conforming = 0
    for vector, case_dir in iter_cases(corpus):
        expected = vector.get("expected") or {}
        try:
            got = judge_case(case_dir)
        except (OSError, ValueError) as exc:
            # A case we cannot even read is neither accept nor reject: it fails
            # conformance and is reported as an error, never folded into a pass.
            got = {"decision": None, "reason": None, "error": str(exc), "exit": 3}
        mismatched = [f for f in ("decision", "reason") if got.get(f) != expected.get(f)]
        if not mismatched:
            conforming += 1
        records.append({"id": vector.get("id"), "got": got, "expected": expected,
                        "conforms": not mismatched, "mismatched": mismatched})
    return {"members": len(records), "conforming": conforming, "records": records}
