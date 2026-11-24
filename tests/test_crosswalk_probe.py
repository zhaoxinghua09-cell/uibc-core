# -*- coding: utf-8 -*-
"""Tests for tools/crosswalk_probe.py.

The point of these is the exit-code rule, not the rendering: a declared gap must
stay green, and an unproven claim must turn the run red. If that inverts, the
crosswalk becomes a document that always passes, which is the failure mode the
tool was written to avoid.
"""
import importlib.util
import json
import pathlib
import sys

import pytest

REPO = pathlib.Path(__file__).resolve().parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "crosswalk_probe", REPO / "tools" / "crosswalk_probe.py")
cp = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(cp)


def _probe(ok=True):
    return {"ok": ok, "exit": 0 if ok else 1, "cmd": "x", "tail": []}


# --- classify: the pure decision function --------------------------------

def test_classify_carried_with_passing_probe_is_covered():
    assert cp.classify("carried", "", _probe(True))[0] == "COVERED"


def test_classify_carried_without_probe_is_overclaim():
    state, note = cp.classify("carried", "we cover it", None)
    assert state == "OVERCLAIM"
    assert "no probe" in note


def test_classify_carried_with_failing_probe_is_overclaim():
    state, _ = cp.classify("carried", "", _probe(False))
    assert state == "OVERCLAIM"


def test_classify_carried_when_not_run_is_unrun():
    state, _ = cp.classify("carried", "", None, ran=False)
    assert state == "UNRUN"


def test_classify_partial_with_reason_is_partial():
    assert cp.classify("partial", "we record the file, not its adequacy", None)[0] == "PARTIAL"


def test_classify_partial_without_reason_is_undeclared():
    assert cp.classify("partial", "   ", None)[0] == "UNDECLARED"


def test_classify_gap_with_reason_is_gap():
    assert cp.classify("gap", "device firmware, not a record layer", None)[0] == "GAP"


def test_classify_gap_without_reason_is_undeclared():
    state, note = cp.classify("gap", "", None)
    assert state == "UNDECLARED"
    assert "bare gap" in note


def test_classify_unknown_strength_is_undeclared():
    assert cp.classify("almost", "x", None)[0] == "UNDECLARED"


# --- the run-level rule -------------------------------------------------

def _write(tmp_path, clauses):
    doc = {"schema": cp.SCHEMA,
           "standard": {"id": "T", "title": "test", "url": ""},
           "clauses": clauses}
    p = tmp_path / "cw.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return str(p)


def test_declared_gap_keeps_run_green(tmp_path):
    path = _write(tmp_path, [{
        "id": "G-1", "strength": "gap", "probe": None,
        "reason": "process requirement; this layer cannot carry it"}])
    assert cp.main([path, "--quiet"]) == 0


def test_overclaim_without_probe_fails(tmp_path):
    path = _write(tmp_path, [{
        "id": "C-1", "strength": "carried", "probe": None,
        "reason": ""}])
    assert cp.main([path, "--quiet"]) == 1


def test_overclaim_on_failing_probe_fails(tmp_path):
    script = tmp_path / "fail.py"
    script.write_text("import sys\nsys.exit(1)\n", encoding="utf-8")
    path = _write(tmp_path, [{
        "id": "C-2", "strength": "carried",
        "probe": {"cmd": '"%s" "%s"' % (sys.executable, script), "expect": {"exit": 0}},
        "reason": ""}])
    assert cp.main([path, "--quiet"]) == 1


def test_covered_with_passing_probe_is_green(tmp_path):
    script = tmp_path / "ok.py"
    script.write_text("print('fine')\n", encoding="utf-8")
    path = _write(tmp_path, [{
        "id": "C-3", "strength": "carried",
        "probe": {"cmd": '"%s" "%s"' % (sys.executable, script),
                  "expect": {"exit": 0, "stdout_contains": "fine"}},
        "reason": ""}])
    assert cp.main([path, "--quiet"]) == 0


def test_no_probe_flag_marks_unrun_and_stays_green(tmp_path):
    path = _write(tmp_path, [{
        "id": "C-4", "strength": "carried",
        "probe": {"cmd": "python -c \"print(1)\"", "expect": {"exit": 0}},
        "reason": ""}])
    assert cp.main([path, "--quiet", "--no-probe"]) == 0
    out = tmp_path / "r.json"
    cp.main([path, "--quiet", "--no-probe", "--json", str(out)])
    res = json.loads(out.read_text(encoding="utf-8"))
    assert res["rows"][0]["state"] == "UNRUN"
    assert res["verdict"] == "PARTIAL-RUN"


def test_schema_mismatch_is_refused(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"schema": "other/1", "clauses": []}), encoding="utf-8")
    assert cp.main([str(bad), "--quiet"]) == 2


# --- identity -----------------------------------------------------------

def test_manifest_digest_changes_when_clause_text_changes():
    a = [{"id": "X", "text": "one", "strength": "gap", "reason": "r"}]
    b = [{"id": "X", "text": "two", "strength": "gap", "reason": "r"}]
    assert cp.manifest_digest(a) != cp.manifest_digest(b)


def test_manifest_digest_is_stable_across_key_order():
    a = [{"id": "X", "strength": "gap", "reason": "r"}]
    b = [{"reason": "r", "strength": "gap", "id": "X"}]
    assert cp.manifest_digest(a) == cp.manifest_digest(b)


# --- the shipped crosswalks --------------------------------------------

@pytest.mark.parametrize("name", ["eu-mdr-2017-745.json", "tool-contract.json"])
def test_shipped_crosswalks_evaluate_without_bad_states(name):
    doc = json.loads((REPO / "crosswalk" / name).read_text(encoding="utf-8"))
    assert doc["schema"] == cp.SCHEMA
    res = cp.evaluate(doc, run=False)  # static pass: schema + declarations only
    assert res["bad"] == 0, res["rows"]


def test_mdr_crosswalk_has_no_carried_clause():
    """Deliberate: no MDR clause is fully carried by a record layer.

    If this test starts failing because someone promoted a row to 'carried',
    that is the moment the file turns into an overclaim. Change the row back,
    or bring a probe that actually demonstrates the clause.
    """
    doc = json.loads((REPO / "crosswalk" / "eu-mdr-2017-745.json").read_text(encoding="utf-8"))
    assert all(c["strength"] != "carried" for c in doc["clauses"])


def test_every_mapped_clause_quotes_a_url():
    for name in ["eu-mdr-2017-745.json", "tool-contract.json"]:
        doc = json.loads((REPO / "crosswalk" / name).read_text(encoding="utf-8"))
        for c in doc["clauses"]:
            assert c.get("url", "").startswith("https://"), c["id"]


# --- the 4(d) probe: identities recompute or they do not ----------------

def _run_probe(pkg):
    import subprocess
    return subprocess.run(
        [sys.executable, str(REPO / "tools" / "probe_evidence_identity.py"),
         str(REPO / "fixtures" / pkg)],
        capture_output=True, text=True, encoding="utf-8", errors="replace")


def test_evidence_identity_probe_recomputes_clean_package():
    r = _run_probe("clean.uibc")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "2/2 evidence identities recompute" in r.stdout


def test_evidence_identity_probe_names_the_tampered_entry():
    r = _run_probe("tampered.uibc")
    assert r.returncode == 1
    assert "digest mismatch" in r.stdout
