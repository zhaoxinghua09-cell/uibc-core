import base64
import datetime
import hashlib
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import check_delegation as cd  # noqa: E402
from uibc_core.canonical import canonicalize  # noqa: E402

SEED = bytes(range(32))
OTHER_SEED = bytes(range(1, 33))
CORPUS = "711fa82c9f183066cfae6441a4fe3fc27fcc516b25f2a976cad5e0dd61b5135f"
INSIDE = datetime.datetime(2026, 11, 25, tzinfo=datetime.timezone.utc)


def make(**overrides):
    kwargs = dict(
        seed=SEED,
        delegator=("Lab A", "lab-a"),
        delegatee=("Node B", "node-b"),
        corpus_sha256=CORPUS,
        not_before="2026-11-20T00:00:00Z",
        not_after="2026-12-20T00:00:00Z",
        cases="all",
        cases_total=294,
        max_runs=1,
        directed=False,
    )
    kwargs.update(overrides)
    return cd.issue_record(**kwargs)


def reasons(record, **kwargs):
    return cd.check(record, at=kwargs.pop("at", INSIDE), **kwargs)[0]


def notes(record, **kwargs):
    return cd.check(record, at=kwargs.pop("at", INSIDE), **kwargs)[1]


def test_a_well_formed_record_is_accepted_but_the_identity_is_unbound():
    assert reasons(make()) == []
    assert any("identity unbound" in n for n in notes(make()))


def test_a_known_delegator_key_binds_the_identity_and_removes_the_caveat():
    from uibc_core import ed25519
    pub = ed25519.publickey(SEED)
    assert cd.check(make(), at=INSIDE, delegator_key=pub) == ([], [])
    other = ed25519.publickey(OTHER_SEED)
    assert any("not the delegator's known key" in r
               for r in cd.check(make(), at=INSIDE, delegator_key=other)[0])


def test_the_delegator_cannot_authorize_themselves():
    record = make(delegatee=("Lab A", "lab-a"))
    assert any("same id" in r for r in reasons(record))


def test_a_borrowed_name_with_another_id_is_refused():
    record = make(delegatee=("Lab A", "node-c"))
    assert any("share a name" in r for r in reasons(record))


def test_a_window_longer_than_a_quarter_is_refused():
    record = make(not_after="2027-06-01T00:00:00Z")
    assert any("longer than 90 days" in r for r in reasons(record))


def test_the_window_is_judged_at_the_moment_asked():
    record = make()
    before = datetime.datetime(2026, 11, 19, tzinfo=datetime.timezone.utc)
    after = datetime.datetime(2026, 12, 25, tzinfo=datetime.timezone.utc)
    assert any("not opened" in r for r in reasons(record, at=before))
    assert any("window closed" in r for r in reasons(record, at=after))
    assert reasons(record, at=INSIDE) == []


def test_a_case_number_beyond_the_corpus_is_refused():
    record = make(cases=[1, 2, 500], cases_total=294)
    assert any("beyond cases_total" in r for r in reasons(record))


def test_a_case_named_twice_is_refused():
    record = make(cases=[7, 7], cases_total=294)
    assert any("twice" in r for r in reasons(record))


def test_a_second_hop_is_refused():
    record = make()
    record["chain"] = {"depth": 2}
    assert any("one hop" in r for r in reasons(record))
    record2 = make()
    record2["parent"] = {"id": "lab-z"}
    assert any("second hop" in r for r in reasons(record2))


def test_a_directed_run_must_say_so():
    record = make()
    del record["scope"]["directed"]
    assert any("directed is absent" in r for r in reasons(record))


def test_a_corpus_name_is_refused_because_names_drift():
    record = make()
    record["scope"]["corpus_name"] = "uibc-conformance-0.4.1.zip"
    assert any("corpus_name" in r for r in reasons(record))


def test_one_byte_in_the_signed_body_breaks_the_signature():
    record = make()
    record["scope"]["max_runs"] = 50
    assert any("signature does not verify" in r for r in reasons(record))


def test_a_record_re_signed_with_another_key_is_caught_by_the_known_key():
    record = make(seed=OTHER_SEED)
    # On its own the record is internally consistent: the key is inside it.
    assert reasons(record) == []
    from uibc_core import ed25519
    pub = ed25519.publickey(SEED)
    assert any("not the delegator's known key" in r
               for r in cd.check(record, at=INSIDE, delegator_key=pub)[0])


def test_a_receipt_from_someone_else_is_refused():
    record = make()
    good = {"corpus_sha256": CORPUS, "run_by": {"name": "Node B"}}
    assert reasons(record, receipt=good) == []
    wrong_runner = {"corpus_sha256": CORPUS, "run_by": {"name": "Node C"}}
    assert any("not by the delegatee" in r for r in reasons(record, receipt=wrong_runner))
    wrong_corpus = {"corpus_sha256": "0" * 64, "run_by": {"name": "Node B"}}
    assert any("different corpus" in r for r in reasons(record, receipt=wrong_corpus))


def test_the_cli_prints_a_verdict_and_sets_the_exit_code(tmp_path):
    record = make()
    path = tmp_path / "delegation.json"
    path.write_text(json.dumps(record), encoding="utf-8")
    assert cd.main([str(path), "--at", "2026-11-25T00:00:00Z"]) == 0
    from uibc_core import ed25519
    key = ed25519.publickey(SEED).hex()
    assert cd.main([str(path), "--at", "2026-11-25T00:00:00Z", "--delegator-key", key]) == 0
    record["scope"]["max_runs"] = 99
    path.write_text(json.dumps(record), encoding="utf-8")
    assert cd.main([str(path), "--at", "2026-11-25T00:00:00Z"]) == 1


def test_the_doc_keeps_the_limits_in_words():
    doc = open(os.path.join(REPO, "docs", "DELEGATION.md"), encoding="utf-8").read()
    for phrase in ("one signature, not a threshold", "no revocation registry",
                   "a string, not a credential", "travels inside the record"):
        assert phrase in doc
    assert "no one has been delegated anything" in doc
