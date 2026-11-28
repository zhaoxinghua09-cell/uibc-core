import json
import os
import sys


REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import check_config_change as cc  # noqa: E402
from uibc_core import ed25519  # noqa: E402

SEED = bytes(range(32))
OTHER = bytes(range(1, 33))
D = "a" * 64


def legs():
    return {"spec": {"sha256": D}, "verifier": {"sha256": D}, "corpus": {"sha256": D}}


def make(**overrides):
    kwargs = dict(
        seed=SEED,
        proposed_by=("Maintainer", "m-1"),
        decided_by=("Decider", "d-2"),
        disposition="adopted",
        normative=True,
        legs=legs(),
    )
    kwargs.update(overrides)
    return cc.issue_record(**kwargs)


def reasons(record, **kwargs):
    return cc.check(record, **kwargs)[0]


def test_a_complete_normative_change_is_accepted():
    assert reasons(make()) == []


def test_a_change_cannot_approve_itself():
    record = make(decided_by=("Maintainer", "m-1"))
    assert any("approve itself" in r for r in reasons(record))


def test_the_disposition_comes_from_a_closed_set():
    record = make(disposition="probably fine")
    assert any("not one of" in r for r in reasons(record))


def test_a_decline_must_carry_a_reason():
    record = make(disposition="declined", reason="")
    assert any("no reason" in r for r in reasons(record))
    assert reasons(make(disposition="declined", reason="it widens acceptance")) == []


def test_a_partial_adoption_must_state_its_residual():
    record = make(disposition="adopted-in-part", residual="")
    assert any("no residual" in r for r in reasons(record))
    assert reasons(make(disposition="adopted-in-part", residual="leg 2 deferred to next record")) == []


def test_an_open_row_must_say_what_would_settle_it():
    record = make(disposition="open", settle_with="")
    assert any("settle" in r for r in reasons(record))


def test_normative_changes_land_in_all_three_legs_or_not_at_all():
    for leg in ("spec", "verifier", "corpus"):
        partial = legs()
        del partial[leg]
        record = make(legs=partial)
        assert any("missing the %s leg" % leg in r for r in reasons(record)), leg


def test_a_non_normative_label_needs_its_reason():
    record = make(normative=False, why_not_normative="")
    assert any("no stated reason" in r for r in reasons(record))
    assert reasons(make(normative=False, why_not_normative="comment typo", legs={})) == []


def test_a_change_that_does_not_say_whether_behaviour_moved_is_refused():
    record = make()
    del record["normative"]
    record["id"] = cc.body_id(record)
    assert any("has to say whether behaviour moved" in r for r in reasons(record))


def test_a_leg_that_is_not_one_of_the_three_is_refused():
    extra = legs()
    extra["changelog"] = {"sha256": D}
    assert any("changelog" in r for r in reasons(make(legs=extra)))


def test_editing_a_row_after_the_fact_breaks_its_id():
    record = make()
    record["residual"] = "actually we adopted it in full"
    assert any("edited after it was recorded" in r for r in reasons(record))


def test_the_ledger_must_chain_and_must_not_repeat():
    a = make()
    b = make(disposition="open", settle_with="a second run on the hostile corpus",
             previous_id=a["id"], proposed_at="2026-11-21T00:00:00Z",
             decided_at="2026-11-21T02:00:00Z")
    assert cc.check_ledger([a, b]) == []
    assert any("repeats id" in r for r in cc.check_ledger([a, a]))
    broken = dict(b)
    broken["previous_id"] = "b" * 64
    broken["id"] = cc.body_id(broken)
    assert any("previous_id" in r for r in cc.check_ledger([a, broken]))


def test_the_decision_cannot_predate_the_proposal():
    record = make(proposed_at="2026-11-20T02:00:00Z", decided_at="2026-11-20T01:00:00Z")
    assert any("before the proposal" in r for r in reasons(record))


def test_a_known_decider_key_binds_the_identity():
    pub = ed25519.publickey(SEED)
    assert cc.check(make(), decider_key=pub) == ([], [])
    assert any("not the decider's known key" in r
               for r in cc.check(make(), decider_key=ed25519.publickey(OTHER))[0])


def test_the_identity_caveat_shows_without_a_known_key():
    notes = cc.check(make())[1]
    assert any("identity unbound" in n for n in notes)


def test_the_cli_reports_a_chain_and_sets_the_exit_code(tmp_path):
    a = make()
    b = make(disposition="declined", reason="it would relax a gate",
             previous_id=a["id"], proposed_at="2026-11-22T00:00:00Z",
             decided_at="2026-11-22T03:00:00Z")
    path = tmp_path / "ledger.json"
    path.write_text(json.dumps([a, b]), encoding="utf-8")
    assert cc.main([str(path), "--decider-key", ed25519.publickey(SEED).hex()]) == 0
    b["reason"] = ""
    b["id"] = cc.body_id(b)
    path.write_text(json.dumps([a, b]), encoding="utf-8")
    assert cc.main([str(path)]) == 1


def test_the_doc_credits_the_rules_to_the_documents_that_stated_them():
    doc = open(os.path.join(REPO, "docs", "CONFIG-CONTROL.md"), encoding="utf-8").read()
    assert "probityai" in doc and "emilia" in doc
    assert "together, or not at all" in doc
    for phrase in ("silence is not agreement", "append-only"):
        assert phrase in doc
