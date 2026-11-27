"""The per-package report is the interface a foreign harness reads.

Contracts:

1. one JSON line per package, and the line names the vector, the verdict, the
   checks that failed, and which verifier produced it - a report whose producer
   is unnamed is a claim without a claimant;
2. `--report` appends, so a harness can collect many runs in one file and no
   earlier line is lost when a later package fails;
3. the line is written whatever happens: a failing package is exactly the case a
   harness needs a line for, and so is an input we cannot read at all - "no
   line" is indistinguishable from "this vector was silently dropped", which is
   what a foreign rail reported as external-output-absent;
4. `verify-dir` exits non-zero when any child is not PASS, and prints the count;
5. an empty directory is a setup problem (exit 3) and writes nothing, because
   "nothing was judged" must never read as "everything passed".
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURES = os.path.join(ROOT, "fixtures")


def _run(args, env_extra=None):
    env = dict(os.environ)
    env["PYTHONPATH"] = ROOT + os.pathsep + env.get("PYTHONPATH", "")
    if env_extra:
        env.update(env_extra)
    return subprocess.run([sys.executable, "-m", "uibc_core.cli"] + args,
                          capture_output=True, text=True, timeout=600, env=env,
                          cwd=ROOT)


def _lines(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


pytestmark = pytest.mark.skipif(not os.path.isdir(FIXTURES),
                                reason="fixtures directory absent")


def test_one_line_names_the_vector_and_the_verifier():
    out = os.path.join(tempfile.mkdtemp(prefix="rpt-"), "r.jsonl")
    proc = _run(["verify", os.path.join(FIXTURES, "clean.uibc"),
                 "--report", out, "--vector-id", "v-clean"])
    lines = _lines(out)
    assert len(lines) == 1, proc.stderr
    line = lines[0]
    assert line["format"] == "uibc-verify-report/1"
    assert line["vector"] == "v-clean"
    assert line["verifier_id"] == "uibc-core-verifier"
    assert line["verifier_version"]
    assert line["exit"] == (0 if line["result"] == "PASS" else 1)
    assert line["exit"] == proc.returncode
    assert line["checks_failed"] == []


def test_a_failing_package_still_gets_a_line_that_names_its_checks():
    out = os.path.join(tempfile.mkdtemp(prefix="rpt-"), "r.jsonl")
    proc = _run(["verify", os.path.join(FIXTURES, "duplicated.uibc"),
                 "--report", out, "--vector-id", "v-dup"])
    assert proc.returncode == 1, proc.stdout[-400:]
    line = _lines(out)[0]
    assert line["result"] == "FAIL"
    assert line["checks_failed"], "a FAIL line with no failing check names nothing"
    assert line["exit"] == 1


def test_the_report_appends_rather_than_rewrites():
    out = os.path.join(tempfile.mkdtemp(prefix="rpt-"), "r.jsonl")
    for i, name in enumerate(("clean.uibc", "duplicated.uibc")):
        _run(["verify", os.path.join(FIXTURES, name), "--report", out,
              "--vector-id", "v-%d" % i])
    lines = _lines(out)
    assert [l["vector"] for l in lines] == ["v-0", "v-1"]


def test_verify_dir_counts_and_refuses_to_flatter():
    work = tempfile.mkdtemp(prefix="rpt-dir-")
    for name in ("clean.uibc", "duplicated.uibc"):
        shutil.copytree(os.path.join(FIXTURES, name), os.path.join(work, name))
    out = os.path.join(work, "r.jsonl")
    proc = _run(["verify-dir", work, "--report", out])
    assert proc.returncode == 1, proc.stdout[-400:]
    lines = _lines(out)
    assert len(lines) == 2
    assert any(l["result"] == "FAIL" and l["checks_failed"] for l in lines)
    passes = sum(1 for l in lines if l["result"] == "PASS")
    assert "%d/2 packages PASS" % passes in proc.stdout


def test_an_unreadable_input_still_gets_a_line():
    """A statement file is not a package: the verdict is ERROR, but the line exists.

    This is the shape a foreign rail hands over - single statements, not package
    directories - and "exit 2, no line" is what it named as external-output-absent.
    """
    out = os.path.join(tempfile.mkdtemp(prefix="rpt-"), "r.jsonl")
    proc = _run(["verify", os.path.join(ROOT, "README.md"), "--report", out,
                 "--vector-id", "v-not-a-package"])
    assert proc.returncode == 3, proc.stdout + proc.stderr
    line = _lines(out)[0]
    assert line["vector"] == "v-not-a-package"
    assert line["result"] == "ERROR"
    assert line["exit"] == 3
    assert line["checks_failed"] == []
    assert "error" in line and line["error"]
    # An ERROR line must still name who wrote it, or it reads as an anonymous
    # complaint: the verifier's identity is knowable even when the input is not.
    assert line["verifier_id"] == "uibc-core-verifier"
    assert line["verifier_version"]


def test_an_empty_directory_is_a_setup_problem():
    work = tempfile.mkdtemp(prefix="rpt-empty-")
    out = os.path.join(work, "r.jsonl")
    proc = _run(["verify-dir", work, "--report", out])
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert not os.path.exists(out)
