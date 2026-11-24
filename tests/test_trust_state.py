import json
import os

from uibc_core import interop_result as ir
from uibc_core import trust_state as ts

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_JSON = os.path.join(REPO, "docs", "TRUST-STATE-TRANSITIONS.json")

EV = [{"id": "e1", "type": "decision-record", "issuer": "did:key:z6Mkissuer",
       "digest": "sha256:" + "a" * 64}]


def test_nothing_goes_up_without_evidence():
    for prior in ir.STATES:
        if prior == "VERIFIED":
            continue
        if ts.RULES[(prior, "VERIFIED")] == "forbidden":
            with open(os.devnull, "w"):
                pass
            try:
                ts.transition(prior, "VERIFIED", evidence=[])
            except Exception:
                pass
            else:
                raise AssertionError("%s -> VERIFIED passed without evidence" % prior)


def test_verified_cannot_be_created_from_invalid():
    assert ts.RULES[("INVALID", "VERIFIED")] == "forbidden"
    try:
        ts.transition("INVALID", "VERIFIED", evidence=EV)
    except ts.TransitionError:
        pass
    else:
        raise AssertionError("INVALID -> VERIFIED was allowed with evidence")


def test_revocation_can_only_be_lifted_explicitly():
    assert ts.RULES[("REVOKED", "VERIFIED")] == "with_evidence_and_reinstatement"
    try:
        ts.transition("REVOKED", "VERIFIED", evidence=EV)
    except ts.TransitionError as exc:
        assert "policy act" in str(exc)
    else:
        raise AssertionError("REVOKED -> VERIFIED without reinstated=True")
    rec = ts.transition("REVOKED", "VERIFIED", evidence=EV, reinstated=True)
    assert rec["rule"] == "with_evidence_and_reinstatement" and rec["reinstated"]


def test_bad_news_needs_no_permission():
    for new in ("INVALID", "REVOKED", "EXPIRED", "INCONCLUSIVE"):
        rec = ts.transition("VERIFIED", new, reason="fresh re-check says so")
        assert rec["rule"] == "allowed"
    # ...but a revocation or expiry still has to state why.
    try:
        ts.transition("VERIFIED", "REVOKED")
    except ir.ResultError:
        pass
    else:
        raise AssertionError("REVOKED without a reason was accepted")


def test_cannot_fall_from_unsupported_into_verified_by_re_running():
    assert ts.RULES[("UNSUPPORTED", "VERIFIED")] == "with_evidence"
    try:
        ts.transition("UNSUPPORTED", "VERIFIED", evidence=[])
    except ir.ResultError:
        pass
    else:
        raise AssertionError("UNSUPPORTED -> VERIFIED without evidence")


def test_lateral_moves_are_free_but_do_not_touch_verified():
    assert ts.RULES[("UNSUPPORTED", "UNRESOLVED")] == "allowed"
    assert ts.RULES[("UNRESOLVED", "UNSUPPORTED")] == "allowed"
    assert ts.RULES[("UNSUPPORTED", "INVALID")] == "forbidden"


def test_no_op_is_legal_and_claims_nothing():
    for state in ir.STATES:
        assert ts.transition(state, state)["rule"] == "no-op"


def test_unknown_states_are_refused():
    for bad in ("verified", "PASS", ""):
        try:
            ts.transition(bad, "VERIFIED")
        except ir.ResultError:
            pass
        else:
            raise AssertionError("unknown state %r accepted" % (bad,))


def test_the_documented_table_is_the_computed_one():
    body = ts.transitions_document()
    assert len(body["rows"]) == 49
    with open(DOC_JSON, encoding="utf-8") as fh:
        on_disk = json.load(fh)
    assert on_disk == body, (
        "docs/TRUST-STATE-TRANSITIONS.json is stale: regenerate it from "
        "trust_state.transitions_document()")
