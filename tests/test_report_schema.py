"""Our lines must satisfy the schema we published, and the linter must bite.

The schema in `interop/` is a promise to a consumer outside this repository.
Two failures are possible and both are pinned here:

1. we emit a line the schema does not allow (our own promise broken);
2. the linter accepts a line that is not a report (the promise is unusable,
   because anyone can satisfy a rule set that enforces nothing).
"""

import json
import os
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LINT = os.path.join(ROOT, "tools", "report_lint.py")
SCHEMA = os.path.join(ROOT, "interop", "verify-report.schema.json")
FIXTURES = os.path.join(ROOT, "fixtures")


def _run_cli(args):
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run([sys.executable, "-m", "uibc_core.cli"] + args,
                          capture_output=True, text=True, timeout=600, env=env, cwd=ROOT)


def _lint(path):
    return subprocess.run([sys.executable, LINT, path], capture_output=True,
                          text=True, timeout=120)


def _lines(tmp):
    out = os.path.join(tmp, "r.jsonl")
    return out


pytestmark = pytest.mark.skipif(not os.path.isdir(FIXTURES), reason="no fixtures")


def test_the_schema_is_a_file_a_stranger_can_read():
    with open(SCHEMA, encoding="utf-8") as fh:
        schema = json.load(fh)
    assert schema["$schema"].startswith("https://json-schema.org/draft/2020-12")
    assert set(schema["required"]) == {"format", "vector", "result", "checks_failed",
                                       "verifier_id", "verifier_version", "when_utc",
                                       "exit"}
    assert schema["properties"]["format"]["const"] == "uibc-verify-report/1"
    # The three verdicts a consumer must not confuse are named in the description,
    # not silently merged: INCONCLUSIVE and ERROR are both "not a pass".
    desc = schema["properties"]["result"]["description"]
    assert "INCONCLUSIVE" in desc and "ERROR" in desc and "Neither is a pass" in desc


def test_our_own_lines_satisfy_the_schema():
    tmp = tempfile.mkdtemp(prefix="lint-")
    out = _lines(tmp)
    for name, vid in (("clean.uibc", "v-clean"), ("duplicated.uibc", "v-dup")):
        _run_cli(["verify", os.path.join(FIXTURES, name), "--report", out, "--vector-id", vid])
    # plus the unreadable-input shape
    _run_cli(["verify", os.path.join(ROOT, "README.md"), "--report", out, "--vector-id", "v-file"])
    proc = _lint(out)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "REPORT LINT OK: 3 line(s)" in proc.stdout


def test_the_schema_itself_is_valid_jsonschema():
    """Optional: only when `jsonschema` is installed. The linter is the fallback.

    A schema nobody validated can be invalid JSON Schema and still look fine to
    us, so where the library exists, use it.
    """
    js = pytest.importorskip("jsonschema")
    with open(SCHEMA, encoding="utf-8") as fh:
        schema = json.load(fh)
    js.Draft202012Validator.check_schema(schema)
    validator = js.Draft202012Validator(schema)
    tmp = tempfile.mkdtemp(prefix="lint-js-")
    out = os.path.join(tmp, "r.jsonl")
    for name, vid in (("clean.uibc", "v-clean"), ("duplicated.uibc", "v-dup")):
        _run_cli(["verify", os.path.join(FIXTURES, name), "--report", out, "--vector-id", vid])
    _run_cli(["verify", os.path.join(ROOT, "README.md"), "--report", out, "--vector-id", "v-file"])
    with open(out, encoding="utf-8") as fh:
        for raw in fh:
            if raw.strip():
                assert not list(validator.iter_errors(json.loads(raw)))


def test_the_linter_refuses_a_line_that_names_no_check():
    tmp = tempfile.mkdtemp(prefix="lint-bad-")
    path = os.path.join(tmp, "bad.jsonl")
    good = {"format": "uibc-verify-report/1", "vector": "v", "result": "FAIL",
            "checks_failed": [], "verifier_id": "x", "verifier_version": "1",
            "when_utc": "2026-11-27T00:00:00Z", "exit": 1}
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(good) + "\n")
    proc = _lint(path)
    assert proc.returncode == 1
    assert "a FAIL line with no failing check" in proc.stdout


def test_the_linter_refuses_an_error_line_without_a_reason():
    tmp = tempfile.mkdtemp(prefix="lint-bad2-")
    path = os.path.join(tmp, "bad.jsonl")
    line = {"format": "uibc-verify-report/1", "vector": "v", "result": "ERROR",
            "checks_failed": [], "verifier_id": "x", "verifier_version": "1",
            "when_utc": "2026-11-27T00:00:00Z", "exit": 3}
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(line) + "\n")
    proc = _lint(path)
    assert proc.returncode == 1
    assert "must say why" in proc.stdout


def test_the_linter_refuses_a_pass_that_carries_failed_checks():
    tmp = tempfile.mkdtemp(prefix="lint-bad3-")
    path = os.path.join(tmp, "bad.jsonl")
    line = {"format": "uibc-verify-report/1", "vector": "v", "result": "PASS",
            "checks_failed": ["S4"], "verifier_id": "x", "verifier_version": "1",
            "when_utc": "2026-11-27T00:00:00Z", "exit": 0}
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(line) + "\n")
    proc = _lint(path)
    assert proc.returncode == 1
    assert "must not carry failed checks" in proc.stdout
