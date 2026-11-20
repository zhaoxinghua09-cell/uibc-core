import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import check_scitt_crosswalk as cs  # noqa: E402


def cw():
    with open(os.path.join(REPO, "docs", "SCITT-CROSSWALK.json"), encoding="utf-8") as fh:
        return json.load(fh)


def row(data, needle):
    return [r for r in data["rows"] if needle in r["theirs"]][0]


def test_the_committed_crosswalk_holds():
    reasons, counts, _ = cs.check(cw(), REPO)
    assert reasons == []
    assert counts["have"] >= 2 and counts["absent"] >= 4


def test_the_documents_do_not_claim_scitt_conformance():
    assert cs.scan(REPO) == []


def test_the_source_document_must_exist_in_the_repository():
    data = cw()
    data["source"]["document"] = "docs/spec-sources/not-vendored.txt"
    reasons, _, _ = cs.check(data, REPO)
    assert any("is not in the repository" in r for r in reasons)


def test_a_container_claiming_interop_is_refused():
    data = cw()
    data["container"]["interoperable"] = True
    reasons, _, _ = cs.check(data, REPO)
    assert any("interoperable" in r for r in reasons)


def test_all_three_flags_must_be_false():
    for flag in cs.FLAGS_MUST_BE_FALSE:
        data = cw()
        data["flags"][flag] = True
        reasons, _, _ = cs.check(data, REPO)
        assert any(flag in r for r in reasons), flag


def test_a_partial_row_without_a_note_is_refused():
    data = cw()
    row(data, "agent.id")["note"] = ""
    reasons, _, _ = cs.check(data, REPO)
    assert any("agent.id" in r and "partial" in r for r in reasons)


def test_an_absent_row_must_name_its_cost():
    data = cw()
    row(data, "scope.tenant")["cost"] = ""
    reasons, _, _ = cs.check(data, REPO)
    assert any("no stated cost" in r for r in reasons)


def test_a_have_row_must_name_a_counterpart():
    data = cw()
    row(data, "ts (RFC 3339 UTC)")["ours"] = ""
    reasons, _, _ = cs.check(data, REPO)
    assert any("names nothing of ours" in r for r in reasons)


def test_a_table_in_which_nothing_matches_is_refused():
    data = cw()
    for r in data["rows"]:
        if r["status"] in ("have", "ours_only"):
            r["status"] = "partial"
            r["note"] = "no counterpart"
    reasons, _, _ = cs.check(data, REPO)
    assert any("nothing matches" in r for r in reasons)


def test_a_scitt_claim_in_a_document_is_caught(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("Our receipts are SCITT-compatible.\n", encoding="utf-8")
    monkeypatch.setattr(cs, "SCANNED", ("README.md",))
    assert cs.scan(str(tmp_path)) == [("README.md", "scitt-compatible")]


def test_the_cli_exits_one_on_an_overclaim(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    (tmp_path / "README.md").write_text("conforms to SCITT by design\n", encoding="utf-8")
    path = tmp_path / "docs" / "SCITT-CROSSWALK.json"
    path.write_text(json.dumps(cw()), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(cs, "SCANNED", ("README.md",))
    monkeypatch.setattr(cs, "REPO_PLACEHOLDER", None, raising=False)
    # the vendored draft is not under tmp_path, so point the row check at the real repo:
    data = cw()
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(cs, "check", lambda crosswalk, root: ([], {}, []))
    assert cs.main([]) == 1


def test_the_crosswalk_states_the_equivocation_limit_on_both_sides():
    data = cw()
    rows = [r for r in data["rows"] if "equivocation" in r["theirs"]]
    assert rows and rows[0]["status"] == "have"
    assert "transparency" in rows[0]["theirs"].lower()
