import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import status_page as sp  # noqa: E402


def test_the_facts_come_from_the_repository_not_from_prose():
    f, missing = sp.facts(REPO)
    assert missing == []
    assert f["version"] == "0.4.1"
    assert len(f["archive_sha256"]) == 64
    assert f["archive_bytes"] == 228000
    assert f["archive_cases"] == 36
    assert f["archive_carries_verifier"] is True
    assert f["oracle_cases"] >= 25
    assert isinstance(f["external_third_party"], int)
    assert f["adoption_state"] == "zero"
    assert len(f["adoption_states"]) > 1, "both snapshots should be visible"
    assert isinstance(f["downloads_last_month"], int)


def test_every_dimension_with_a_checker_points_at_a_file():
    for _label, _status, tool, _note in sp.DIMENSIONS:
        if tool:
            assert os.path.isfile(os.path.join(REPO, tool)), tool


def test_the_page_has_no_passing_test_count():
    f, missing = sp.facts(REPO)
    page = sp.render(f, missing)
    assert "passed" not in page.lower() or "passing-test count" in page.lower()
    assert "No passing-test count appears here on purpose" in page


def test_adoption_downloads_are_labelled_context():
    f, missing = sp.facts(REPO)
    page = sp.render(f, missing)
    assert "context only — not adoption" in page


def test_the_render_is_deterministic():
    f, missing = sp.facts(REPO)
    assert sp.render(f, missing) == sp.render(f, missing)


def test_a_stale_page_is_detected(tmp_path, monkeypatch):
    f, missing = sp.facts(REPO)
    page = sp.render(f, missing)
    (tmp_path / "STATUS.md").write_text(page.replace("228000", "227999"), encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sp, "facts", lambda root: (f, missing))
    assert sp.main(["--check"]) == 1


def test_a_current_page_passes(tmp_path, monkeypatch):
    f, missing = sp.facts(REPO)
    page = sp.render(f, missing)
    (tmp_path / "STATUS.md").write_text(page, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sp, "facts", lambda root: (f, missing))
    assert sp.main(["--check"]) == 0


def test_a_missing_source_says_missing_rather_than_a_guess(tmp_path, monkeypatch):
    f, missing = sp.facts(REPO)
    f2 = dict(f)
    f2["archive_sha256"] = None
    page = sp.render(f2, ["conformance/uibc-conformance-0.4.1.zip"])
    assert "| archive sha256 | `missing` |" in page
    assert "Unreadable sources on the last generation" in page


def test_an_absent_dimension_is_labelled_absent_and_carries_no_tool():
    row = [d for d in sp.DIMENSIONS if d[1] == "absent"]
    assert row and row[0][2] == ""


def test_the_newest_snapshot_wins_by_timestamp_not_by_filename(tmp_path, monkeypatch):
    # "…-authenticated.json" sorts before "….json" as text; the timestamp decides.
    f, missing = sp.facts(REPO)
    assert f["adoption_report"] == "2026-11-20-authenticated.json"
    assert f["adoption_report"] > "" and f["adoption_state"] == "zero"


def test_disagreeing_snapshots_are_both_visible():
    f, missing = sp.facts(REPO)
    page = sp.render(f, missing)
    assert "An earlier snapshot disagrees with the latest" in page
    assert "history of good news" in page


def test_absent_dimension_row_carries_no_checker_and_status_word_is_literal():
    f, missing = sp.facts(REPO)
    page = sp.render(f, missing)
    assert "| quorum threshold authorisation | **absent** | — |" in page
    labels = [h[0] for h in sp.HUMAN_ONLY]
    assert "configure the release signing key" in labels
    assert any("invitation" in x for x in labels)
    assert any("historical" in x for x in labels)

def test_the_human_only_list_names_the_three_things():
    labels = [h[0] for h in sp.HUMAN_ONLY]
    assert "configure the release signing key" in labels
    assert any("invitation" in x for x in labels)
    assert any("historical" in x for x in labels)
