import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import status_page as sp  # noqa: E402


def test_the_facts_come_from_the_repository_not_from_prose():
    f, missing = sp.facts(REPO)
    assert missing == []
    import re
    declared = re.search(r'version *= *"([^"]+)"',
                         open(os.path.join(REPO, "pyproject.toml"), encoding="utf-8").read()).group(1)
    assert f["version"] == declared
    assert len(f["archive_sha256"]) == 64
    declared = re.search(r'version *= *"([^"]+)"',
                         open(os.path.join(REPO, "pyproject.toml"), encoding="utf-8").read()).group(1)
    pin = open(os.path.join(REPO, "anchors", "pins", "uibc-conformance-%s.sha256" % declared),
               encoding="utf-8").read()
    import re as _re
    assert _re.search(r"([0-9a-f]{64})  conformance/", pin).group(1) == f["archive_sha256"]
    # The zip and the manifest must agree: a case added to the tree but not to
    # the archive is a case a downloader cannot run.
    manifest = json.load(open(os.path.join(REPO, "conformance", "manifest.json"), encoding="utf-8"))
    assert f["archive_cases"] == len(manifest["cases"])
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
    sp.render(f, missing)
    stale = sp.render(f, missing).replace(str(f["archive_bytes"]), "227999")
    (tmp_path / "STATUS.md").write_text(stale, encoding="utf-8")
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
    assert "approve the repository-held attestation as v0.4.1's answer" in labels
    assert any("invitation" in x for x in labels)
    assert any("historical" in x for x in labels)
    assert any("historical" in x for x in labels)

def test_the_human_only_list_names_the_three_things():
    labels = [h[0] for h in sp.HUMAN_ONLY]
    assert "approve the repository-held attestation as v0.4.1's answer" in labels
    assert any("invitation" in x for x in labels)
    assert any("historical" in x for x in labels)
    assert any("historical" in x for x in labels)


def test_every_reproduce_command_names_a_tool_that_exists():
    assert sp.REPRODUCE, "the page must list commands"
    for command, comment in sp.REPRODUCE:
        path = sp._tool_path(command)
        assert path.startswith("tools/"), command
        assert os.path.isfile(os.path.join(REPO, path)), command
        assert comment, "a command without a reason is noise"


def test_the_page_reaches_the_anchors_not_only_the_corpus_checks():
    """Measured 2026-11-20: the block was reachable in the repository and unreachable
    from the page a reader lands on -- the reproduce block named four tools and no
    anchor check at all."""
    commands = "\n".join(row[0] for row in sp.REPRODUCE)
    assert "tools/check_release_anchors.py" in commands
    assert "tools/ots_merkle.py" in commands
    assert "tools/check_release_pins.py" in commands
    assert "tools/check_outsider_entry.py" in commands


def test_a_vanished_tool_makes_the_page_stale(tmp_path, monkeypatch):
    f, missing = sp.facts(REPO)
    page = sp.render(f, missing)
    (tmp_path / "STATUS.md").write_text(page, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sp, "facts", lambda root: (f, missing))
    monkeypatch.setattr(sp, "_missing_reproduce_tools", lambda root: ["python tools/gone.py"])
    assert sp.main(["--check"]) == 1


def test_an_unpacked_archive_without_tools_is_not_called_stale(tmp_path, monkeypatch):
    """An sdist ships no `tools/`; a check that invented a failure there would fail
    every archive build for a fact about the archive, not about the page."""
    assert sp._missing_reproduce_tools(str(tmp_path)) == []

