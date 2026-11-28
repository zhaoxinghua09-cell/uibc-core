"""The delta-form revocation reader, held to its own signed chains.

The peer's shared vectors are judged separately (see
``tests/test_revocation_delta_corpus.py``, which runs only when
``UIBC_REVOCATION_DELTA_CORPUS`` points at the file), so this file neither
venders their fixtures nor needs the network. It checks the checks: what the
fold installs, what it refuses, and which of the ten tokens it refuses with.

Every list here is signed at test time with the package's own Ed25519, from
fixed seeds, so a fixture cannot drift from what it claims to be: the body the
signature covers is the body the assertions read.
"""

import base64
import hashlib
import json
import subprocess
import sys

import pytest

from uibc_core import aee, ed25519
from uibc_core import revocation_delta as rd

SEEDS = {
    name: hashlib.sha256(("uibc-delta-" + name).encode("ascii")).digest()
    for name in ("A", "B", "C", "D")
}
ROOT_A = hashlib.sha256(ed25519.publickey(SEEDS["A"])).hexdigest()
ROOT_B = hashlib.sha256(ed25519.publickey(SEEDS["B"])).hexdigest()
LIST_ID = "probity-revocations"
T0 = "2026-06-01T00:00:00Z"
T1 = "2026-06-02T00:00:00Z"
T2 = "2026-06-03T00:00:00Z"


def _b64(raw: bytes) -> str:
    return base64.b64encode(raw).decode("ascii")


def _key(seed) -> str:
    return _b64(ed25519.publickey(seeds_of(seed)))


def seeds_of(seed):
    return SEEDS[seed] if isinstance(seed, str) else seed


def _body(seed, seq, entries=(), issued_at=T0, previous=None, list_id=LIST_ID,
          type_=rd.LIST_TYPE):
    return {
        "entries": list(entries),
        "issuedAt": issued_at,
        "issuerKey": _key(seed),
        "listId": list_id,
        "previous": previous,
        "seq": seq,
        "type": type_,
    }


def _signed(body, seed="A", sig=None):
    canon = aee._jcs_dumps(body)
    raw = ed25519.sign(SEEDS[seed], rd.DOMAIN + canon)
    return {"body": body, "sig": _b64(raw) if sig is None else sig}


def _digest(body) -> str:
    return "sha256:" + hashlib.sha256(aee._jcs_dumps(body)).hexdigest()


def _entry(kind, ident, revoked_at="2026-05-31T00:00:00Z", **extra):
    row = {"id": ident, "kind": kind, "revokedAt": revoked_at}
    row.update(extra)
    return row


def _refusal(state, signed):
    with pytest.raises(rd.Refusal) as excinfo:
        rd.apply(state, signed)
    return excinfo.value


# Fold and install


def test_an_empty_first_list_is_in_force():
    list1 = _signed(_body("A", 1))
    got = rd.verify_chain([ROOT_A], [list1])
    assert got["decision"] == "accept"
    assert got["reason"] == "in_force"
    assert got["index"] is None
    assert got["state"]["seq"] == 1
    assert got["state"]["roots"] == [ROOT_A]
    assert got["state"]["head"] == _digest(list1["body"])
    assert got["state"]["revoked"] == {k: [] for k in rd.KINDS}


def test_a_delta_carries_only_what_it_newly_revokes():
    list1 = _signed(_body("A", 1))
    list2 = _signed(_body("A", 2, [_entry("agent", "agent:alpha")], T1,
                          previous=_digest(list1["body"])))
    got = rd.verify_chain([ROOT_A], [list1, list2])
    assert got["decision"] == "accept"
    assert got["state"]["revoked"]["agent"] == ["agent:alpha"]
    assert got["state"]["seq"] == 2
    assert got["state"]["head"] == _digest(list2["body"])


def test_an_empty_later_list_is_a_freshness_list_and_drops_nothing():
    list1 = _signed(_body("A", 1))
    list2 = _signed(_body("A", 2, [_entry("agent", "agent:alpha")], T1,
                          previous=_digest(list1["body"])))
    list3 = _signed(_body("A", 3, [], T2, previous=_digest(list2["body"])))
    got = rd.verify_chain([ROOT_A], [list1, list2, list3])
    assert got["decision"] == "accept"
    assert got["state"]["seq"] == 3
    assert got["state"]["revoked"]["agent"] == ["agent:alpha"]


def test_the_eight_kinds_are_all_represented_and_sorted():
    entries = [
        _entry("agent", "agent:a"),
        _entry("build", "build:b"),
        _entry("grant", "0" * 63 + "1"),
        _entry("idp-key", "A" * 42 + "E"),
        _entry("key", "0" * 63 + "2"),
        _entry("permit", "0" * 63 + "3"),
        _entry("sponsor", "sponsor:s"),
        _entry("stream", "stream:t"),
    ]
    list1 = _signed(_body("A", 1, entries))
    got = rd.verify_chain([ROOT_A], [list1])
    assert got["decision"] == "accept"
    assert list(got["state"]["revoked"]) == list(rd.KINDS)
    assert got["state"]["revoked"]["idp-key"] == ["A" * 42 + "E"]


# The ten refusal tokens


def test_a_repeated_entry_is_refused_by_name():
    list1 = _signed(_body("A", 1, [_entry("agent", "agent:alpha")]))
    list2 = _signed(_body("A", 2, [_entry("agent", "agent:alpha")], T1,
                          previous=_digest(list1["body"])))
    got = rd.verify_chain([ROOT_A], [list1, list2])
    assert got["decision"] == "reject"
    assert got["refusal"]["code"] == "revocation_entry_repeated"
    assert got["index"] == 1


def test_replaying_the_list_in_force_is_a_rollback():
    list1 = _signed(_body("A", 1))
    state = rd.apply(rd.RevocationState([ROOT_A]), list1)
    refusal = _refusal(state, list1)
    assert str(refusal) == "revocation_list_rollback:1<=1"


def test_skipping_a_sequence_is_a_gap():
    list1 = _signed(_body("A", 1))
    state = rd.apply(rd.RevocationState([ROOT_A]), list1)
    later = _signed(_body("A", 3, [], T1, previous=_digest(list1["body"])))
    assert str(_refusal(state, later)) == "revocation_list_gap:3>2"


def test_another_list_id_is_another_chain():
    list1 = _signed(_body("A", 1))
    other = _signed(_body("A", 2, [], T1, previous=_digest(list1["body"]), list_id="other-chain"))
    state = rd.apply(rd.RevocationState([ROOT_A]), list1)
    assert str(_refusal(state, other)) == "revocation_list_other_chain"


def test_a_previous_digest_that_does_not_match_is_refused():
    list1 = _signed(_body("A", 1))
    state = rd.apply(rd.RevocationState([ROOT_A]), list1)
    wrong = _signed(_body("A", 2, [], T1, previous="sha256:" + "0" * 64))
    assert str(_refusal(state, wrong)) == "revocation_list_previous_mismatch"


def test_an_issue_time_that_moves_backwards_is_refused():
    list1 = _signed(_body("A", 1, [], T1))
    state = rd.apply(rd.RevocationState([ROOT_A]), list1)
    backwards = _signed(_body("A", 2, [], T0, previous=_digest(list1["body"])))
    assert str(_refusal(state, backwards)) == "revocation_list_time_reversed"


def test_an_entry_from_the_future_is_refused():
    list1 = _signed(_body("A", 1, [_entry("agent", "agent:alpha", T1)]))
    got = rd.verify_chain([ROOT_A], [list1])
    assert got["refusal"]["code"] == "revocation_entry_from_future"


def test_a_signer_that_is_not_a_pinned_root_is_refused():
    list1 = _signed(_body("B", 1))
    got = rd.verify_chain([ROOT_A], [list1])
    assert got["refusal"]["code"] == "revocation_list_signer_not_a_root"


def test_a_signature_that_does_not_verify_is_refused():
    body = _body("A", 1)
    forged = _signed(body, "B")  # B signs a body naming A's key
    got = rd.verify_chain([ROOT_A], [forged])
    assert got["refusal"]["code"] == "revocation_list_signature_unverified"


def test_a_signature_in_non_canonical_base64_is_unverified_not_malformed():
    list1 = _signed(_body("A", 1))
    broken = dict(list1)
    broken["sig"] = list1["sig"][:10] + "\n" + list1["sig"][10:]
    got = rd.verify_chain([ROOT_A], [broken])
    assert got["refusal"]["code"] == "revocation_list_signature_unverified"
    assert got["refusal"]["detail"] == "signature_not_canonical_base64"


@pytest.mark.parametrize("body_mutator,detail", [
    (lambda b: b.update(entries=[_entry("robot", "agent:a")]), "entry_kind_unknown"),
    (lambda b: b.update(entries=[_entry("key", "not-hex")]), "entry_id_form:key"),
    (lambda b: b.update(entries=[_entry("idp-key", "0" * 64)]), "entry_id_form:idp-key"),
    (lambda b: b.update(entries=[_entry("agent", "a b")]), "entry_id_form:agent"),
    (lambda b: b.update(entries=[_entry("agent", "agent:b"), _entry("agent", "agent:a")]),
     "entries_not_strictly_ascending"),
    (lambda b: b.update(entries=[_entry("agent", "agent:a"), _entry("agent", "agent:a")]),
     "entries_not_strictly_ascending"),
    (lambda b: b.update(seq=0), "seq_not_a_positive_exact_integer"),
    (lambda b: b.update(previous="sha256:" + "0" * 64), "previous_form"),
    (lambda b: b.update(issuedAt="2026-06-01 00:00:00"), "issuedAt_not_a_utc_second"),
    (lambda b: b.update(issuedAt="2026-02-30T00:00:00Z"), "issuedAt_not_a_calendar_instant"),
    (lambda b: b.update(unexpected="x"), "body_members"),
])
def test_shape_faults_refuse_as_shape(body_mutator, detail):
    body = _body("A", 1)
    body_mutator(body)
    got = rd.verify_chain([ROOT_A], [_signed(body)])
    assert got["refusal"]["code"] == "revocation_list_shape"
    assert got["refusal"]["detail"] == detail


def test_the_v1_type_is_refused_as_a_shape_fault():
    got = rd.verify_chain([ROOT_A], [_signed(_body(
        "A", 1, type_="https://probityai.github.io/agent-evidence-vectors/predicate/v1/revocation-list"))])
    assert got["refusal"]["code"] == "revocation_list_shape"
    assert got["refusal"]["detail"] == "type"


def test_a_successor_on_a_non_key_entry_is_a_shape_fault():
    body = _body("A", 1, [_entry("agent", "agent:a", successor=_key("B"))])
    got = rd.verify_chain([ROOT_A], [_signed(body)])
    assert got["refusal"]["detail"] == "successor_on_non_key_entry"


def test_a_key_of_the_wrong_length_is_a_shape_fault():
    body = _body("A", 1)
    body["issuerKey"] = _b64(b"\x01" * 31)
    got = rd.verify_chain([ROOT_A], [_signed(body)])
    assert got["refusal"]["detail"] == "issuerKey_not_an_ed25519_key"


def test_the_second_host_names_the_same_type():
    body = _body("A", 1, type_="https://probityai.org/agent-evidence-vectors/predicate/v2/revocation-list")
    got = rd.verify_chain([ROOT_A], [_signed(body)])
    assert got["decision"] == "accept"


def test_another_host_spelling_is_not_the_type():
    body = _body("A", 1, type_="http://probityai.github.io/agent-evidence-vectors/predicate/v2/revocation-list")
    got = rd.verify_chain([ROOT_A], [_signed(body)])
    assert got["refusal"]["code"] == "revocation_list_shape"


# Root rotation


def test_revoking_a_root_with_a_successor_rotates_it():
    list1 = _signed(_body("A", 1))
    list2 = _signed(_body("A", 2, [_entry("key", ROOT_A, successor=_key("B"))], T1,
                          previous=_digest(list1["body"])))
    got = rd.verify_chain([ROOT_A], [list1, list2])
    assert got["decision"] == "accept"
    assert got["state"]["roots"] == [ROOT_B]
    # and B can sign the next list
    list3 = _signed(_body("B", 3, [_entry("agent", "agent:beta")], T2,
                          previous=_digest(list2["body"])), seed="B")
    got3 = rd.verify_chain([ROOT_A], [list1, list2, list3])
    assert got3["decision"] == "accept"
    assert got3["state"]["roots"] == [ROOT_B]


def test_a_successor_the_same_list_revokes_is_not_a_root():
    list1 = _signed(_body("A", 1))
    list2 = _signed(_body("A", 2, [
        _entry("key", ROOT_A, successor=_key("B")),
        _entry("key", ROOT_B),
    ], T1, previous=_digest(list1["body"])))
    got = rd.verify_chain([ROOT_A], [list1, list2])
    assert got["decision"] == "accept"
    assert got["state"]["roots"] == []


def test_a_successor_revoked_earlier_is_not_rejoined():
    list1 = _signed(_body("A", 1, [_entry("key", ROOT_B)]))
    list2 = _signed(_body("A", 2, [_entry("key", ROOT_A, successor=_key("B"))], T1,
                          previous=_digest(list1["body"])))
    got = rd.verify_chain([ROOT_A, ROOT_B], [list1, list2])
    assert got["decision"] == "accept"
    assert got["state"]["roots"] == []


# Suite and chain documents


def _write_suite(tmp_path, cases):
    path = tmp_path / "revocation.json"
    path.write_text(json.dumps(cases, indent=2), encoding="utf-8")
    return str(path)


def test_the_suite_comparison_counts_a_matching_case(tmp_path):
    list1 = _signed(_body("A", 1, [_entry("agent", "agent:alpha")]))
    case = {
        "id": "X1", "description": "one list", "roots": [ROOT_A], "lists": [list1],
        "expected": {"state": {"head": _digest(list1["body"]), "issuedAt": T0, "listId": LIST_ID,
                               "revoked": {k: (["agent:alpha"] if k == "agent" else []) for k in rd.KINDS},
                               "roots": [ROOT_A], "seq": 1}},
    }
    summary = rd.judge_suite(_write_suite(tmp_path, [case]))
    assert summary["members"] == 1 and summary["conforming"] == 1


def test_the_suite_comparison_names_the_field_a_case_differs_on(tmp_path):
    list1 = _signed(_body("A", 1))
    case = {
        "id": "X2", "roots": [ROOT_A], "lists": [list1],
        "expected": {"state": {"head": "sha256:" + "0" * 64, "issuedAt": T0, "listId": LIST_ID,
                               "revoked": {k: [] for k in rd.KINDS}, "roots": [ROOT_A], "seq": 1}},
    }
    summary = rd.judge_suite(_write_suite(tmp_path, [case]))
    assert summary["conforming"] == 0
    assert summary["records"][0]["mismatched"] == ["state"]


def test_a_suite_carrying_a_sequence_beyond_the_exact_range_still_judges(tmp_path):
    # The container is not a signed list: one case deliberately carries a seq
    # outside 2**53 to prove the reader refuses it as a shape fault.
    body = _body("A", 1)
    body["seq"] = 2 ** 53
    case = {"id": "X3", "roots": [ROOT_A], "lists": [{"body": body, "sig": _signed(_body("A", 1))["sig"]}],
            "expected": {"index": 0, "refused": "revocation_list_shape"}}
    summary = rd.judge_suite(_write_suite(tmp_path, [case]))
    assert summary["conforming"] == 1


def test_a_chain_document_judges_from_a_file(tmp_path):
    list1 = _signed(_body("A", 1))
    path = tmp_path / "chain.json"
    path.write_text(json.dumps({"roots": [ROOT_A], "lists": [list1]}), encoding="utf-8")
    got = rd.judge_chain_file(str(path))
    assert got["decision"] == "accept"
    assert got["state"]["seq"] == 1


def test_a_chain_document_with_another_shape_is_unreadable(tmp_path):
    path = tmp_path / "chain.json"
    path.write_text(json.dumps({"roots": [ROOT_A], "lists": [], "extra": 1}), encoding="utf-8")
    with pytest.raises(ValueError):
        rd.judge_chain_file(str(path))


def test_a_suite_with_a_duplicate_member_is_unreadable(tmp_path):
    path = tmp_path / "revocation.json"
    path.write_text('[{"id": "X", "id": "Y", "roots": [], "lists": [], "expected": {}}]', encoding="utf-8")
    with pytest.raises(ValueError):
        rd.load_suite(str(path))


# The CLI


def _run(*args):
    return subprocess.run([sys.executable, "-m", "uibc_core.cli", "verify-revocation-delta", *args],
                          capture_output=True, text=True, encoding="utf-8")


def test_the_cli_exits_by_the_decision(tmp_path):
    accepting = _signed(_body("A", 1))
    chain_ok = tmp_path / "ok.json"
    chain_ok.write_text(json.dumps({"roots": [ROOT_A], "lists": [accepting]}), encoding="utf-8")
    ok = _run("--chain", str(chain_ok))
    assert ok.returncode == 0
    assert json.loads(ok.stdout.strip().splitlines()[-1])["decision"] == "accept"

    replay = tmp_path / "replay.json"
    replay.write_text(json.dumps({"roots": [ROOT_A], "lists": [accepting, accepting]}), encoding="utf-8")
    bad = _run("--chain", str(replay))
    assert bad.returncode == 1
    assert json.loads(bad.stdout.strip().splitlines()[-1])["reason"] == "revocation_list_rollback:1<=1"


def test_the_cli_reports_one_line_per_case(tmp_path):
    list1 = _signed(_body("A", 1))
    suite = _write_suite(tmp_path, [{
        "id": "X4", "roots": [ROOT_A], "lists": [list1],
        "expected": {"state": {"head": _digest(list1["body"]), "issuedAt": T0, "listId": LIST_ID,
                               "revoked": {k: [] for k in rd.KINDS}, "roots": [ROOT_A], "seq": 1}},
    }])
    report = tmp_path / "report.jsonl"
    proc = _run("--suite", suite, "--report", str(report))
    assert proc.returncode == 0
    assert "1/1 members conform to the shared answer key" in proc.stdout
    from tools.report_lint import delta_problems
    line = json.loads(report.read_text(encoding="utf-8").strip())
    assert line["format"] == "uibc-revocation-delta-report/1"
    assert delta_problems(line) == []
