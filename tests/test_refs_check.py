"""Citations must be clickable today, not just pinned.

Five contracts:

1. the citation list comes from the snapshot - one entry per audited repository,
   and none invented;
2. the report covers exactly that list, so a citation cannot silently drop out;
3. a dead citation (404 / timeout) fails --check and names the repository;
4. a 301 is reported as "moved", not as dead: the repository was renamed, the
   reader can still get there, but the document has to say so;
5. the generated page is a generated page.
"""

import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location("refs_check", os.path.join(ROOT, "tools", "refs_check.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def refs():
    return _load()


@pytest.fixture()
def snap(refs):
    return json.load(open(refs.SNAPSHOT, encoding="utf-8"))


def test_citations_come_from_the_snapshot(refs, snap, monkeypatch):
    monkeypatch.delenv("UIBC_COMMIT", raising=False)
    cites = refs.citations(snap)
    repos = {r["repo"] for r in snap["repos"] if "error" not in r}
    assert {c["repo"] for c in cites} >= repos
    for c in cites:
        assert c["url"] == "https://github.com/%s/tree/%s" % (c["repo"], c["sha"])
        assert len(c["sha"]) == 40, c["repo"]


def test_no_unknown_sha_is_cited(refs, snap, monkeypatch):
    monkeypatch.delenv("UIBC_COMMIT", raising=False)
    for c in refs.citations(snap):
        assert c["sha"] != "unknown"
        assert "unknown" not in c["url"]


def test_report_covers_the_snapshot_exactly(refs, snap):
    report = json.load(open(refs.REPORT, encoding="utf-8"))
    want = {(c["repo"], c["sha"]) for c in refs.citations(snap)}
    got = {(r["repo"], r["sha"]) for r in report["entries"]}
    assert got == want
    assert report["summary"]["citations"] == len(want)
    assert report["summary"]["dead"] == 0


def test_a_dead_citation_fails_the_check(refs, capsys, tmp_path, monkeypatch):
    # Mutating the tracked report and putting it back leaves CRLF behind on
    # Windows, so the working copy and the committed file diverge with no
    # content difference. Work on a copy instead.
    copy = tmp_path / "refs-report.json"
    copy.write_bytes(open(refs.REPORT, "rb").read())
    monkeypatch.setattr(refs, "REPORT", str(copy))
    report = json.load(open(refs.REPORT, encoding="utf-8"))
    victim = dict(report["entries"][0], status=404, error="")
    report["entries"][0] = victim
    with open(refs.REPORT, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(report))
    rc = refs.check()
    assert rc == 1
    out = capsys.readouterr().out
    assert "dead citation" in out
    assert victim["repo"] in out


def test_a_redirect_is_moved_not_dead(refs):
    moved = {"status": 301, "error": "", "final_url": "https://github.com/new/name"}
    assert refs.moved(moved) and not refs.alive(moved)
    assert refs.alive({"status": 200, "error": "", "final_url": ""})
    assert not refs.alive({"status": 0, "error": "timeout"})


def test_a_move_must_be_live_at_the_new_name(refs):
    """301 alone is not enough: the pinned sha has to answer under the new name."""
    if not refs.os.path.exists(refs.REPORT):
        pytest.skip("no report")
    report = json.load(open(refs.REPORT, encoding="utf-8"))
    moves = [e for e in report["entries"] if refs.moved(e)]
    if not moves:
        pytest.skip("this report has no moves")
    for e in moves:
        f = e.get("followed") or {}
        assert f.get("repo_now"), (e["repo"], "moved without recording where to")
        assert refs.alive(f), (e["repo"], "still not reachable at", f.get("repo_now"))


def test_a_moved_citation_that_lands_on_404_fails(refs, capsys, tmp_path, monkeypatch):
    """The WARN about a rename must not paper over a citation that is really gone."""
    if not refs.os.path.exists(refs.REPORT):
        pytest.skip("no report")
    report = json.load(open(refs.REPORT, encoding="utf-8"))
    idx = next((i for i, e in enumerate(report["entries"]) if refs.moved(e)), None)
    if idx is None:
        pytest.skip("this report has no moves")
    report["entries"][idx]["followed"] = {"repo_now": "nowhere/renamed", "url": "u",
                                          "status": 404, "error": "", "final_url": ""}
    copy = tmp_path / "refs-report.json"
    with open(copy, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(report))
    monkeypatch.setattr(refs, "REPORT", str(copy))
    assert refs.check() == 1
    assert "new location is not reachable" in capsys.readouterr().out


def test_the_page_is_generated(refs):
    page = open(refs.PAGE, encoding="utf-8").read()
    assert "条引用" in page
    assert "每次 `--run` 重写本页" in page
