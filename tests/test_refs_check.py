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


def test_a_dead_citation_fails_the_check(refs, capsys):
    report = json.load(open(refs.REPORT, encoding="utf-8"))
    victim = dict(report["entries"][0], status=404, error="")
    report["entries"][0] = victim
    open(refs.REPORT + ".bak", "w", encoding="utf-8").write(json.dumps(report))
    try:
        # swap the report in, run the check, put it back
        original = open(refs.REPORT, encoding="utf-8").read()
        open(refs.REPORT, "w", encoding="utf-8").write(json.dumps(report))
        rc = refs.check()
        assert rc == 1
        out = capsys.readouterr().out
        assert "dead citation" in out
        assert victim["repo"] in out
        open(refs.REPORT, "w", encoding="utf-8").write(original)
    finally:
        if os.path.exists(refs.REPORT + ".bak"):
            os.remove(refs.REPORT + ".bak")


def test_a_redirect_is_moved_not_dead(refs):
    moved = {"status": 301, "error": "", "final_url": "https://github.com/new/name"}
    assert refs.moved(moved) and not refs.alive(moved)
    assert refs.alive({"status": 200, "error": "", "final_url": ""})
    assert not refs.alive({"status": 0, "error": "timeout"})


def test_the_page_is_generated(refs):
    page = open(refs.PAGE, encoding="utf-8").read()
    assert "条引用" in page
    assert "每次 `--run` 重写本页" in page
