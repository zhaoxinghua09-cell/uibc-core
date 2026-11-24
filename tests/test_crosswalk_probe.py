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


def test_classify_carried_requires_a_verbatim_clause():
    """Reading a summary is not the same as reading the clause."""
    state, note = cp.classify("carried", "", _probe(True), verbatim=False)
    assert state == "OVERCLAIM"
    assert "verbatim" in note


def test_classify_partial_is_allowed_without_verbatim():
    assert cp.classify("partial", "paid standard, titles only", None, verbatim=False)[0] == "PARTIAL"


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


def test_classify_partial_with_a_failing_probe_is_overclaim():
    # A partial row may cite a probe for the part it carries. If that probe
    # stops passing, the row must stop looking carried-and-checked.
    state, note = cp.classify("partial", "we record the file, not its adequacy", _probe(False))
    assert state == "OVERCLAIM"
    assert "did not pass" in note


def test_classify_partial_with_a_passing_probe_stays_partial():
    assert cp.classify("partial", "we record the file, not its adequacy", _probe(True))[0] == "PARTIAL"


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

@pytest.mark.parametrize("name", ["eu-mdr-2017-745.json", "tool-contract.json", "iec-62304-2006-a1.json", "iso-14971-2019.json", "21cfr11.json", "nist-sp800-53r5-au.json"])
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
    for name in ["eu-mdr-2017-745.json", "tool-contract.json", "iec-62304-2006-a1.json", "iso-14971-2019.json", "21cfr11.json", "nist-sp800-53r5-au.json"]:
        doc = json.loads((REPO / "crosswalk" / name).read_text(encoding="utf-8"))
        for c in doc["clauses"]:
            assert c.get("url", "").startswith("https://"), c["id"]


def test_part_11_clauses_are_verbatim_from_ecfr():
    """Part 11 is public on eCFR, so there is no excuse for quoting a title.

    If a row drops to verbatim=False, it was probably re-written from memory -
    which is exactly the case the OVERCLAIM gate exists for.
    """
    doc = json.loads((REPO / "crosswalk" / "21cfr11.json").read_text(encoding="utf-8"))
    for c in doc["clauses"]:
        assert c.get("verbatim") is True, c["id"]
        assert "ecfr.gov" in c["url"], c["id"]
        if c["strength"] == "carried":
            # The one carried row must rest on the record-binding probe: a
            # carried row whose evidence is a demo would defeat the point.
            assert c["probe"]["cmd"].endswith("probe_record_binding.py"), c["id"]


def test_part_11_carries_exactly_the_record_binding_row():
    doc = json.loads((REPO / "crosswalk" / "21cfr11.json").read_text(encoding="utf-8"))
    carried = [c["id"] for c in doc["clauses"] if c["strength"] == "carried"]
    assert carried == ["21 CFR 11.70"], carried


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


# --- determinism: the same input must produce the same bytes ------------

def test_result_is_byte_identical_across_two_runs(tmp_path):
    """SLSA calls this "reproducible"; DriftLab asserts it; SPARC gates on it.

    Two runs of one crosswalk must produce identical bytes, or a CI drift gate
    cannot tell a real change from a timing. Diagnostics are excluded on purpose
    and land in --diag instead.
    """
    script = tmp_path / "ok.py"
    script.write_text("print('fine')\n", encoding="utf-8")
    path = _write(tmp_path, [{
        "id": "D-1", "strength": "carried",
        "probe": {"cmd": '"%s" "%s"' % (sys.executable, script),
                  "expect": {"exit": 0, "stdout_contains": "fine"}},
        "reason": ""}])
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    assert cp.main([path, "--quiet", "--json", str(a)]) == 0
    assert cp.main([path, "--quiet", "--json", str(b)]) == 0
    assert a.read_bytes() == b.read_bytes()


def test_check_mode_passes_on_a_fresh_result(tmp_path):
    path = _write(tmp_path, [{"id": "G-2", "strength": "gap", "probe": None, "reason": "not ours"}])
    committed = tmp_path / "committed.json"
    assert cp.main([path, "--quiet", "--json", str(committed)]) == 0
    assert cp.main([path, "--quiet", "--check", str(committed)]) == 0


def test_check_mode_detects_drift_when_a_clause_changes(tmp_path):
    path = _write(tmp_path, [{"id": "G-3", "strength": "gap", "probe": None, "reason": "first reason"}])
    committed = tmp_path / "committed.json"
    assert cp.main([path, "--quiet", "--json", str(committed)]) == 0
    _write(tmp_path, [{"id": "G-3", "strength": "gap", "probe": None, "reason": "second reason"}])
    assert cp.main([path, "--quiet", "--check", str(committed)]) == 3


def test_check_mode_reports_a_missing_baseline(tmp_path):
    path = _write(tmp_path, [{"id": "G-4", "strength": "gap", "probe": None, "reason": "r"}])
    assert cp.main([path, "--quiet", "--check", str(tmp_path / "absent.json")]) == 3


def test_verdict_digest_moves_with_state_not_with_timing():
    clauses = [{"id": "V-1", "strength": "gap", "reason": "r", "text": "t"}]
    doc = {"schema": cp.SCHEMA, "standard": {}, "clauses": clauses}
    a = cp.evaluate(doc, run=False)
    b = cp.evaluate(doc, run=False)
    assert a["verdict_sha256"] == b["verdict_sha256"]
    doc2 = {"schema": cp.SCHEMA, "standard": {},
            "clauses": [{"id": "V-1", "strength": "partial", "reason": "r", "text": "t"}]}
    assert cp.evaluate(doc2, run=False)["verdict_sha256"] != a["verdict_sha256"]


def test_diagnostics_do_not_leak_into_the_result():
    clauses = [{"id": "V-2", "strength": "gap", "reason": "r"}]
    res = cp.evaluate({"schema": cp.SCHEMA, "clauses": clauses}, run=False)
    assert "duration_s" not in cp.dumps_result(res)
    assert "tail" not in cp.dumps_result(res)
