"""Contracts for the agent-card-receipt reader.

Every fixture here is built and signed in the test, with fixed seeds, using the
repository's own Ed25519: nothing of the peer's corpus is vendored, and a
neighbour editing their case cannot turn our suite red. The corpus check, which
does read their files, lives beside this file and runs only when the
environment names a checkout.

The rule order is part of the contract, not an implementation detail: a case
with two faults must answer the earlier rule, because two verifiers that
disagree about which fault they saw cannot be compared.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os

import pytest

from uibc_core import agent_card_receipt as acr
from uibc_core import cli
from uibc_core import ed25519

SEED = hashlib.sha256(b"uibc agent-card-receipt test issuer").digest()
FOREIGN_SEED = hashlib.sha256(b"uibc agent-card-receipt test other").digest()
PUB = ed25519.publickey(SEED)

NOW = "2026-11-20T09:00:00Z"
BEFORE = "2026-11-19T08:00:00Z"
AFTER = "2026-11-21T08:00:00Z"
LIST_ISSUED = "2026-11-20T00:00:00Z"
LIST_NEXT = "2026-11-21T00:00:00Z"

#: A card with the members an A2A catalog leaves on by default, a fractional
#: weight and a small number written with an exponent.
CARD = {
    "name": "receipt-test agent",
    "description": "an agent that answers",
    "version": "1.0.0",
    "url": "https://agent.example/a2a",
    "preferredTransport": "JSONRPC",
    "protocolVersion": "0.3.0",
    "defaultInputModes": ["text/plain"],
    "defaultOutputModes": ["text/plain"],
    "capabilities": {"streaming": True, "pushNotifications": False},
    "skills": [{"id": "lookup", "name": "lookup", "description": "finds a fact",
                "tags": ["search"], "confidence": 0.93}],
    "extensions": {"uibc": {"epsilon": 1e-06, "note": "kept as served"}},
}


def enc(obj):
    return json.dumps(obj, ensure_ascii=False, sort_keys=True).encode("utf-8")


def pae(payload_type, payload):
    """DSSE pre-authentication encoding, built here rather than imported."""
    parts = [b"DSSEv1 ", str(len(payload_type)).encode(), b" ", payload_type.encode(),
             b" ", str(len(payload)).encode(), b" ", payload]
    return b"".join(parts)


def b64(raw):
    return base64.b64encode(raw).decode("ascii")


def make_list(revoked=(), issued=LIST_ISSUED, next_update=LIST_NEXT, seed=SEED,
              payload_over=None, payload_type=acr.PAYLOAD_TYPE):
    body = {"issuedAt": issued, "nextUpdate": next_update, "revoked": list(revoked)}
    if payload_over:
        body.update(payload_over)
    payload = enc(body)
    sig = ed25519.sign(seed, pae(payload_type, payload))
    return enc({
        "payload": b64(payload),
        "payloadType": payload_type,
        "signatures": [{"keyid": hashlib.sha256(ed25519.publickey(seed)).hexdigest(),
                        "sig": b64(sig)}],
    })


def make_statement(card, digest=None, issued=BEFORE, until=AFTER, result="pass",
                   predicate_over=None, predicate_drop=(), statement_over=None,
                   statement_drop=(), subject_over=None):
    if digest is None:
        digest = acr.card_digest(card)
    subject = [{"name": "agent-card", "digest": {"sha256": digest}}]
    if subject_over:
        subject = subject_over
    predicate = {
        "run": {"predicateType": "https://w3id.org/agent-evidence/predicate/v1/mcp-authz",
                "digest": {"sha256": "b" * 64}},
        "result": result,
        "registryDigest": {"sha256": "c" * 64},
        "issuedAt": issued,
        "validUntil": until,
        "revocationList": "https://issuer.example/lists/agent-card-receipt.json",
    }
    if predicate_over:
        predicate.update(predicate_over)
    for name in predicate_drop:
        predicate.pop(name, None)
    statement = {"_type": acr.STATEMENT_TYPE, "subject": subject,
                 "predicateType": acr.PREDICATE_TYPE, "predicate": predicate}
    if statement_over:
        statement.update(statement_over)
    for name in statement_drop:
        statement.pop(name, None)
    return enc(statement)


def base_case():
    """The accepting case every other test edits exactly one thing in."""
    card = enc(CARD)
    statement = make_statement(card)
    return {"card": card, "statement": statement,
            "list": make_list(), "key": PUB, "now": NOW}


def reason_of(**edits):
    case = base_case()
    case.update(edits)
    with pytest.raises(acr.Refusal) as caught:
        acr.judge(case["statement"], case["card"], case["list"], case["key"], case["now"])
    return caught.value.reason


# ---------------------------------------------------------------------------
# The one accepting answer, and what it rests on
# ---------------------------------------------------------------------------

def test_a_current_receipt_is_accepted_and_reports_what_it_computed():
    case = base_case()
    got = acr.judge(case["statement"], case["card"], case["list"], case["key"], case["now"])
    assert got["decision"] == "accept"
    assert got["reason"] == "receipt_current"
    assert got["subjectDigest"] == acr.card_digest(case["card"])
    assert got["statementDigest"] == hashlib.sha256(case["statement"]).hexdigest()


def test_the_digest_is_the_same_however_the_card_is_laid_out():
    """Whitespace and member order are not part of the card; bytes are."""
    compact = json.dumps(CARD, separators=(",", ":")).encode()
    pretty = json.dumps(CARD, indent=2).encode()
    reordered = enc({k: CARD[k] for k in reversed(list(CARD))})
    assert acr.card_digest(compact) == acr.card_digest(pretty) == acr.card_digest(reordered)


def test_top_level_signatures_are_excluded_by_parsed_name():
    """A2A 8.4.1 rule 2: the member is excluded, and it is the parsed member.

    The escape matters: a verifier that compared the raw text for
    `"signatures"` would keep a member that the parser reads as `signatures`,
    and would then disagree with every conformant peer on the digest.
    """
    with_sig = b'{"name":"a","signatur\\u0065s":[{"sig":"x","keyid":"k"}],"ext":{"signatures":1}}'
    without = b'{"name":"a","ext":{"signatures":1}}'
    assert acr.card_digest(with_sig) == acr.card_digest(without)


def test_nested_and_additional_signatures_stay_in_the_digest():
    """Rule 3 excludes once, at the top: an extension keeps its own signatures."""
    plain = b'{"name":"a","ext":{"signatures":1}}'
    nested = b'{"name":"a","ext":{"signatures":2}}'
    additional = b'{"name":"a","additionalSignatures":[1],"ext":{"signatures":1}}'
    assert acr.card_digest(nested) != acr.card_digest(plain)
    assert acr.card_digest(additional) != acr.card_digest(plain)


def test_a_float_in_the_card_is_digested_in_its_ecmascript_form():
    """`0.93` is `0.93` and `1e-06` is `0.000001`, not the bytes as written."""
    card = acr._strict_parse(b'{"a":0.93,"b":1e-06}', "card")
    assert acr._canon(card) == '{"a":0.93,"b":0.000001}'


RFC8785_NUMBERS = [
    ("0000000000000000", "0"), ("8000000000000000", "0"),
    ("0000000000000001", "5e-324"), ("7fefffffffffffff", "1.7976931348623157e+308"),
    ("bff0000000000000", "-1"), ("4024000000000000", "10"),
    ("4340000000000000", "9007199254740992"), ("4430000000000000", "295147905179352830000"),
    ("44b52d02c7e14af5", "9.999999999999997e+22"), ("44b52d02c7e14af6", "1e+23"),
    ("44b52d02c7e14af7", "1.0000000000000001e+23"),
    ("444b1ae4d6e2ef4e", "999999999999999700000"),
    ("444b1ae4d6e2ef50", "1e+21"),
    ("3eb0c6f7a0b5ed8d", "0.000001"),
    ("41b3de4355555553", "333333333.3333332"),
    ("becbf647612f3696", "-0.0000033333333333333333"),
    ("43143ff3c1cb0959", "1424953923781206.2"),
]


@pytest.mark.parametrize("bits,want", RFC8785_NUMBERS)
def test_ecmascript_numbers_hold_against_the_rfcs_own_table(bits, want):
    """RFC 8785 Appendix B, from the raw bits: the table is the authority, not us."""
    import struct
    value = struct.unpack(">d", bytes.fromhex(bits))[0]
    assert acr._es_number(value) == want


# ---------------------------------------------------------------------------
# Every refusing reason, reached by exactly one edit
# ---------------------------------------------------------------------------

def test_a_duplicate_member_leaves_the_statement_unreadable():
    statement = b'{"_type":"%s","_type":"%s"}' % (acr.STATEMENT_TYPE.encode(),
                                                  acr.STATEMENT_TYPE.encode())
    assert reason_of(statement=statement) == "statement_malformed"


def test_an_unexpected_statement_member_is_malformed():
    case = base_case()
    statement = make_statement(case["card"], statement_over={"extra": 1})
    assert reason_of(card=case["card"], statement=statement) == "statement_malformed"


def test_the_statement_type_is_checked_before_the_predicate_type():
    statement = make_statement(enc(CARD), statement_over={"_type": "https://example/wrong"})
    assert reason_of(statement=statement) == "statement_type_wrong"


def test_the_predicate_type_is_checked_before_the_subject():
    statement = make_statement(enc(CARD), statement_over={"predicateType": "x"})
    assert reason_of(statement=statement) == "predicate_type_wrong"


def test_two_subject_members_are_malformed():
    digest = acr.card_digest(enc(CARD))
    subject = [{"name": "a", "digest": {"sha256": digest}},
               {"name": "b", "digest": {"sha256": digest}}]
    assert reason_of(statement=make_statement(enc(CARD), subject_over=subject)) \
        == "subject_malformed"


def test_an_uppercase_digest_is_malformed():
    digest = acr.card_digest(enc(CARD)).upper()
    assert reason_of(statement=make_statement(enc(CARD), digest=digest)) == "subject_malformed"


def test_a_result_outside_the_vocabulary_is_malformed():
    assert reason_of(statement=make_statement(enc(CARD), result="excellent")) \
        == "predicate_malformed"


def test_unsorted_agent_key_thumbprints_are_malformed():
    thumbs = ["b" * 21 + "AAA", "a" * 21 + "AAA"]  # 43 chars each, out of order
    assert reason_of(statement=make_statement(
        enc(CARD), predicate_over={"agentKeyThumbprints": thumbs})) == "predicate_malformed"


def test_an_inverted_window_is_refused_before_the_card_is_read():
    statement = make_statement(enc(CARD), issued=AFTER, until=BEFORE)
    assert reason_of(statement=statement) == "validity_window_inverted"


def test_a_card_that_is_not_an_object_is_malformed():
    assert reason_of(card=b'["not","a","card"]') == "card_malformed"


def test_a_card_integer_outside_i_json_is_malformed():
    assert reason_of(card=b'{"n":9007199254740993}') == "card_malformed"


def test_a_card_the_receipt_does_not_name_is_a_mismatch():
    other = enc(dict(CARD, description="changed after the receipt was signed"))
    assert reason_of(card=other) == "card_digest_mismatch"


def test_a_time_before_the_receipt_was_issued_is_not_yet_valid():
    # One second is enough: the reader judges the receipt before it reads the
    # list, so the list's own window (which also excludes this instant) is not
    # what answers.
    assert reason_of(now="2026-11-19T07:59:59Z") == "receipt_not_yet_valid"
    assert reason_of(now=BEFORE) == "revocation_list_stale"


def test_a_time_at_the_end_of_the_window_is_expired():
    """The window is half-open: `validUntil` is the first instant it no longer holds."""
    assert reason_of(now=AFTER) == "receipt_expired"
    assert reason_of(now="2026-11-21T08:00:00Z") == "receipt_expired"


def test_a_missing_list_is_a_refusal_and_not_a_pass():
    assert reason_of(list=None) == "revocation_list_absent"


def test_a_list_payload_with_an_extra_member_is_malformed():
    bad = make_list(payload_over={"signer": "extra"})
    assert reason_of(list=bad) == "revocation_list_malformed"


def test_a_list_with_the_wrong_payload_type_is_malformed():
    bad = make_list(payload_type="application/json")
    assert reason_of(list=bad) == "revocation_list_malformed"


def test_an_unsorted_revoked_set_is_malformed():
    bad = make_list(revoked=[("ff" * 32), ("00" * 32)])
    assert reason_of(list=bad) == "revocation_list_malformed"


def test_a_list_signed_by_a_foreign_key_is_refused():
    """The list must verify under the key that signed the receipt."""
    assert reason_of(list=make_list(seed=FOREIGN_SEED)) == "revocation_list_signature"


def test_a_list_whose_window_does_not_hold_the_check_time_is_stale():
    assert reason_of(list=make_list(next_update="2026-11-20T09:00:00Z")) \
        == "revocation_list_stale"
    assert reason_of(list=make_list(issued="2026-11-20T09:00:01Z")) \
        == "revocation_list_stale"


def test_a_list_that_names_this_statement_revokes_it():
    case = base_case()
    digest = hashlib.sha256(case["statement"]).hexdigest()
    assert reason_of(list=make_list(revoked=[digest])) == "receipt_revoked"


def test_a_list_that_names_another_statement_does_not_revoke_this_one():
    """The refused case has to be the statement's digest, not any digest."""
def test_a_list_that_names_another_statement_does_not_revoke_this_one():
    """The refused case has to be this statement's digest, not any digest."""
    case = base_case()
    case["list"] = make_list(revoked=[("ab" * 32)])
    got = acr.judge(case["statement"], case["card"], case["list"], case["key"], case["now"])
    assert got["decision"] == "accept"


def test_a_case_that_cannot_be_read_raises_rather_than_deciding(tmp_path):
    with pytest.raises(OSError):
        acr.judge_case(os.path.join(str(tmp_path), "no-such-case"))



# ---------------------------------------------------------------------------
# The order the fifteen rules run in, when a case has two faults
# ---------------------------------------------------------------------------

def test_digest_mismatch_answers_before_expiry():
    assert reason_of(card=enc(dict(CARD, version="2")), now=AFTER) == "card_digest_mismatch"


def test_expiry_answers_before_a_missing_list():
    assert reason_of(now=AFTER, list=None) == "receipt_expired"


def test_a_card_that_cannot_be_read_answers_before_its_digest_is_compared():
    assert reason_of(card=b'{"n":9007199254740993}') == "card_malformed"


# ---------------------------------------------------------------------------
# Case directories, the CLI and its report line
# ---------------------------------------------------------------------------

def write_case(root, name, card, statement, lst, key=PUB, now=NOW):
    directory = os.path.join(root, name)
    os.makedirs(directory, exist_ok=True)
    for file_name, blob in (("card.json", card), ("statement.json", statement),
                            ("context.json", enc({"issuerKey": b64(key), "now": now}))):
        with open(os.path.join(directory, file_name), "wb") as fh:
            fh.write(blob)
    if lst is not None:
        with open(os.path.join(directory, "revocations.json"), "wb") as fh:
            fh.write(lst)
    return directory


def test_a_case_directory_is_judged_and_a_missing_list_is_rule_eleven(tmp_path):
    case = base_case()
    good = write_case(str(tmp_path), "good", case["card"], case["statement"], case["list"])
    assert acr.judge_case(good)["decision"] == "accept"
    gone = write_case(str(tmp_path), "gone", case["card"], case["statement"], None)
    got = acr.judge_case(gone)
    assert got["decision"] == "reject"
    assert got["reason"] == "revocation_list_absent"
    assert got["exit"] == 1


def test_the_cli_exits_by_the_decision(tmp_path):
    import subprocess
    import sys

    case = base_case()
    good = write_case(str(tmp_path), "good", case["card"], case["statement"], case["list"])
    proc = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify-agent-card-receipt",
                           "--case", good], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1])["decision"] == "accept"

    revoked = write_case(str(tmp_path), "revoked", case["card"], case["statement"],
                         make_list(revoked=[hashlib.sha256(case["statement"]).hexdigest()]))
    proc = subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify-agent-card-receipt",
                           "--case", revoked], capture_output=True, text=True, timeout=120)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert json.loads(proc.stdout.strip().splitlines()[-1])["reason"] == "receipt_revoked"


def test_the_report_line_keeps_the_digest_and_the_result_apart():
    accept = cli._agent_card_receipt_line("c", "accept", "receipt_current", "d" * 64, 0)
    refuse = cli._agent_card_receipt_line("c", "reject", "card_digest_mismatch", "d" * 64, 1)
    broken = cli._agent_card_receipt_line("c", None, None, None, 3, error="not JSON")
    assert accept["result"] == "PASS" and refuse["result"] == "FAIL"
    assert broken["result"] == "ERROR" and broken["decision"] is None
    assert accept["format"] == cli.AGENT_CARD_RECEIPT_REPORT_FORMAT
