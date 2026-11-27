"""Bring-your-own cases: the judging rules, the setup refusals, and the receipt.

Contracts, because a runner that flatters itself is worse than none:

1. a case that behaves as its expectation says counts as passed, and one that
   does not counts as failed - the exit code is not the verdict;
2. an `accept` case is failed when any check reports FAIL, even if the verdict
   line is not FAIL;
3. a `reject` case is failed when the refusal names none of the expected checks,
   because "refused something" is not "refused for the reason stated";
4. a setup problem exits 3 and writes no receipt - the run either happened or it
   did not;
5. the receipt records `run_by` verbatim, so an author's run and a stranger's run
   are distinguishable.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ARCHIVE = os.path.join(ROOT, "conformance", "uibc-conformance-0.5.8.zip")
TOOL = os.path.join(ROOT, "tools", "bring_your_own.py")


@pytest.fixture(scope="module")
def kit():
    if not os.path.isfile(ARCHIVE):
        pytest.skip("published archive not in this tree")
    tmp = tempfile.mkdtemp(prefix="byo-kit-")
    with zipfile.ZipFile(ARCHIVE) as z:
        z.extractall(tmp)
    yield tmp
    shutil.rmtree(tmp, ignore_errors=True)


def _subset(kit, ids):
    """Copy a few cases into a fresh directory, with a table naming them."""
    src = os.path.join(kit, "cases")
    table = json.load(open(os.path.join(kit, "expected.json"), encoding="utf-8"))["cases"]
    by_id = {c["id"]: c for c in table}
    work = tempfile.mkdtemp(prefix="byo-cases-")
    rows = []
    for cid in ids:
        case = by_id[cid]
        name = os.path.basename(str(case["path"]).rstrip("/"))
        shutil.copytree(os.path.join(src, name), os.path.join(work, name))
        rows.append(case)
    expect = os.path.join(work, "expected.json")
    with open(expect, "w", encoding="utf-8", newline="\n") as f:
        json.dump({"cases": rows}, f, ensure_ascii=False, indent=1)
    return work, expect


def _run(work, expect, out=None, pyz=None, run_by=None):
    cmd = [sys.executable, TOOL, "--cases", work, "--expect", expect,
           "--pyz", pyz or os.path.join(work, os.pardir, "does-not-exist")]
    if out:
        cmd += ["--out", out]
    if run_by:
        cmd += ["--run-by", run_by]
    return subprocess.run(cmd, capture_output=True, text=True, timeout=600)


def test_two_accept_and_one_refuse_pass(kit):
    work, expect = _subset(kit, ["01", "02", "03"])
    out = os.path.join(work, "r.json")
    pyz = os.path.join(kit, "uibc_core.pyz")
    proc = _run(work, expect, out=out, pyz=pyz, run_by="selftest")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    receipt = json.load(open(out, encoding="utf-8"))
    assert receipt["kind"] == "uibc-bring-your-own-receipt"
    assert receipt["cases"] == 3 and receipt["passed"] == 3
    assert receipt["run_by"] == "selftest"
    assert all(r["ok"] and r["parsed"] for r in receipt["rows"])


def test_a_table_that_misdescribes_the_case_fails(kit):
    """If the table says a broken package is correct, the run must not be green."""
    work, expect = _subset(kit, ["07"])
    table = json.load(open(expect, encoding="utf-8"))
    table["cases"][0]["expect"] = "accept"
    table["cases"][0]["expected_checks"] = []
    with open(expect, "w", encoding="utf-8", newline="\n") as f:
        json.dump(table, f, ensure_ascii=False)
    proc = _run(work, expect, out=os.path.join(work, "r.json"),
                pyz=os.path.join(kit, "uibc_core.pyz"))
    assert proc.returncode == 1, proc.stdout + proc.stderr
    receipt = json.load(open(os.path.join(work, "r.json"), encoding="utf-8"))
    assert receipt["passed"] == 0
    assert "refused a package" in receipt["rows"][0]["note"]


def test_a_missing_case_directory_is_a_setup_problem(kit):
    work, expect = _subset(kit, ["01", "02"])
    shutil.rmtree(os.path.join(work, os.path.basename(
        json.load(open(expect, encoding="utf-8"))["cases"][1]["path"].rstrip("/"))))
    out = os.path.join(work, "r.json")
    proc = _run(work, expect, out=out, pyz=os.path.join(kit, "uibc_core.pyz"))
    assert proc.returncode == 3, proc.stdout + proc.stderr
    assert "setup problem" in proc.stderr
    assert not os.path.exists(out), "a run that cannot be set up must not leave a receipt"


def test_verifier_can_be_taken_from_the_archive(kit):
    work, expect = _subset(kit, ["01", "02", "03"])
    out = os.path.join(work, "r.json")
    proc = _run(work, expect, out=out, pyz=ARCHIVE + ":uibc_core.pyz")
    assert proc.returncode == 0, proc.stdout + proc.stderr
    receipt = json.load(open(out, encoding="utf-8"))
    assert receipt["passed"] == receipt["cases"] == 3
    assert receipt["run_by"] is None, "an anonymous run must not invent an author"
