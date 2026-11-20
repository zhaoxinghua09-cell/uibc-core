import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import settlement_boundary as sb  # noqa: E402


def boundary(**overrides):
    with open(os.path.join(REPO, "docs", "SETTLEMENT-BOUNDARY.json"), encoding="utf-8") as fh:
        data = json.load(fh)
    data.update(overrides)
    return data


def q(data, qid):
    return [x for x in data["questions"] if x["id"] == qid][0]


def test_the_committed_boundary_holds():
    reasons, _ = sb.check(boundary(), REPO)
    assert reasons == []


def test_the_committed_documents_do_not_read_as_payment_claims():
    assert sb.scan(REPO) == []


def test_a_boundary_that_claims_to_process_payments_is_refused():
    reasons, _ = sb.check(boundary(we_process_payments=True), REPO)
    assert any("we_process_payments" in r for r in reasons)
    reasons, _ = sb.check(boundary(we_authorize_charges=True), REPO)
    assert any("we_authorize_charges" in r for r in reasons)


def test_a_supported_answer_must_point_at_a_file_that_exists():
    data = boundary()
    q(data, "Q1")["evidence"] = "docs/NOT-A-REAL-FILE.md"
    reasons, _ = sb.check(data, REPO)
    assert any("Q1 points at" in r for r in reasons)


def test_a_supported_answer_without_an_evidence_file_is_refused():
    data = boundary()
    q(data, "Q1")["evidence"] = ""
    reasons, _ = sb.check(data, REPO)
    assert any("Q1 is 'supported' with no evidence file" in r for r in reasons)


def test_a_partial_answer_must_state_its_limit():
    data = boundary()
    q(data, "Q2")["limit"] = ""
    reasons, _ = sb.check(data, REPO)
    assert any("Q2 is partial with no stated limit" in r for r in reasons)


def test_answers_outside_the_three_values_are_refused():
    data = boundary()
    q(data, "Q4")["answer"] = "probably fine"
    reasons, _ = sb.check(data, REPO)
    assert any("not one of" in r for r in reasons)


def test_the_six_questions_cannot_be_renumbered_or_dropped():
    data = boundary()
    data["questions"] = data["questions"][:4]
    reasons, _ = sb.check(data, REPO)
    assert any("expected six questions" in r for r in reasons)
    data = boundary()
    q(data, "Q6")["id"] = "Q7"
    reasons, _ = sb.check(data, REPO)
    assert any("renumbering" in r for r in reasons)


def test_a_payment_claim_in_a_scanned_document_is_caught(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("This guarantees payment to the seller.\n", encoding="utf-8")
    monkeypatch.setattr(sb, "SCANNED", ("README.md",))
    hits = sb.scan(str(tmp_path))
    assert hits == [("README.md", "guarantees payment")]


def test_the_cli_exits_one_on_an_overclaim(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("we settle the payment instantly\n", encoding="utf-8")
    bpath = tmp_path / "docs" / "SETTLEMENT-BOUNDARY.json"
    bpath.write_text(json.dumps(boundary()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sb, "SCANNED", ("README.md",))
    assert sb.main([]) == 1


def test_two_flags_say_plainly_that_we_do_not_move_money():
    data = boundary()
    assert data["we_process_payments"] is False
    assert data["we_authorize_charges"] is False
    assert any(x["answer"] == "not_ours" for x in data["questions"])
