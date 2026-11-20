import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import check_adoption as ca  # noqa: E402


def fake(responses):
    """A `_get` that answers by URL substring, in order, and records the calls."""
    calls = []

    def _get(url, token=None):
        calls.append(url)
        for needle, payload in responses.items():
            if needle in url:
                return payload
        return {"_error": "no route for %s" % url}
    return _get, calls


ZERO = {
    "api.github.com/search/repositories": {"items": []},
    "api.github.com/search/code": {"total_count": 0, "items": []},
    "datatracker.ietf.org": {"objects": []},
    "pypi.org/pypi/agent-action-capsule": {"info": {"summary": "a capsule format"}},
    "pypistats.org": {"data": {"last_month": 3}},
}


def test_every_bucket_that_answered_zero_yields_a_measured_zero():
    get, calls = fake(ZERO)
    buckets, verdict = ca.measure(_get=get)
    assert verdict["state"] == "zero" and verdict["exit"] == 0
    assert all(b["state"] in ("measured", "context") for b in buckets)
    assert [b["found"] for b in buckets if b["state"] == "measured"] == [0, 0, 0, 0]


def test_downloads_are_context_and_never_summed_into_adoption():
    get, _ = fake(ZERO)
    buckets, verdict = ca.measure(_get=get)
    downloads = [b for b in buckets if b["bucket"] == "package downloads"][0]
    assert downloads["state"] == "context"
    assert downloads["found"] == 3
    assert verdict["total"] == 0


def test_a_refused_search_is_incomplete_not_zero():
    responses = dict(ZERO)
    responses["api.github.com/search/code"] = {"_error": "HTTP 401"}
    get, _ = fake(responses)
    buckets, verdict = ca.measure(_get=get)
    assert verdict["state"] == "incomplete"
    assert verdict["exit"] == 3
    assert "could not be measured" in verdict["sentence"]
    assert "HTTP 401" in verdict["sentence"]
    code = [b for b in buckets if b["bucket"] == "another codebase"][0]
    assert code["state"] == "unmeasured" and code["found"] is None


def test_the_401_is_explained_rather_than_left_as_a_number():
    responses = dict(ZERO)
    responses["api.github.com/search/code"] = {"_error": "HTTP 401"}
    get, _ = fake(responses)
    buckets, _ = ca.measure(_get=get)
    code = [b for b in buckets if b["bucket"] == "another codebase"][0]
    assert "needs an authenticated request" in code["error"]


def test_a_signal_exits_one_and_is_counted():
    responses = dict(ZERO)
    responses["api.github.com/search/repositories"] = {
        "items": [{"full_name": "someone-else/uses-uibc"}, {"full_name": "zhaoxinghua09-cell/uibc-core"}]}
    get, _ = fake(responses)
    buckets, verdict = ca.measure(_get=get)
    assert verdict["state"] == "signal" and verdict["total"] == 1
    assert [b for b in buckets if b["bucket"] == "another repository"][0]["sample"] == ["someone-else/uses-uibc"]


def test_our_own_repository_never_counts():
    responses = dict(ZERO)
    responses["api.github.com/search/repositories"] = {
        "items": [{"full_name": "zhaoxinghua09-cell/uibc-core"},
                  {"full_name": "zhaoxinghua09-cell/uibc-anchor"}]}
    get, _ = fake(responses)
    _, verdict = ca.measure(_get=get)
    assert verdict["total"] == 0 and verdict["state"] == "zero"


def test_the_report_carries_a_timestamp_the_verdict_and_its_limits():
    get, _ = fake(ZERO)
    buckets, verdict = ca.measure(_get=get)
    rep = ca.report(buckets, verdict)
    assert rep["kind"] == "uibc-adoption-report-v0"
    assert rep["generated_at"].endswith("Z")
    assert rep["verdict"]["exit"] == 0
    assert len(rep["limits"]) == 4
    assert "downloads are not a party" in json.dumps(rep["limits"])


def test_cli_writes_the_report_and_returns_the_verdict_code(tmp_path, monkeypatch):
    responses = dict(ZERO)
    responses["api.github.com/search/code"] = {"_error": "HTTP 401"}
    inner, _ = fake(responses)
    original = ca.measure
    monkeypatch.setattr(ca, "measure", lambda _get=None: original(_get=inner))
    out = tmp_path / "report.json"
    rc = ca.main(["--out", str(out)])
    assert rc == 3
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["verdict"]["state"] == "incomplete"


def test_the_doc_records_the_401_defect_it_fixed():
    doc = open(os.path.join(REPO, "docs", "ADOPTION-MEASUREMENT.md"), encoding="utf-8").read()
    assert "HTTP 401" in doc
    assert "exit code 3" in doc or "exit 3" in doc
    assert "downloads are not a party" in doc
