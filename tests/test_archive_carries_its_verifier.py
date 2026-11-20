"""The archive must not borrow a verifier it does not carry.

Measured 2026-11-20 in CI: the "no verifier available" control went green on a runner
where `uibc-core` was pip-installed, because `run.py` fell back to
`python -m uibc_core.cli`. The control was measuring the runner, not the archive: it
could not fail on any machine that did not need the archive.
"""
import io
import os
import shutil
import subprocess
import sys
import tempfile
import zipfile

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUNNER = os.path.join(REPO, "tools", "conformance_bundle_run.py")
ARCHIVE = os.path.join(REPO, "conformance", "uibc-conformance-0.4.1.zip")


def _extract(tmp):
    """Unpack the corpus, and put the runner under test next to it.

    The published archives carry the runner as it was on the day they were built, and
    those bytes are frozen; what is checked here is the runner this tree would ship.
    """
    with zipfile.ZipFile(ARCHIVE) as z:
        z.extractall(tmp)
    shutil.copy2(RUNNER, os.path.join(tmp, "run.py"))
    return tmp


def _stub_package(root):
    pkg = os.path.join(root, "uibc_core")
    os.makedirs(pkg)
    with io.open(os.path.join(pkg, "__init__.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write('__version__ = "9.9.9"\n')
    return root


@pytest.mark.skipif(not os.path.isfile(ARCHIVE), reason="needs a published archive")
def test_the_runner_refuses_to_substitute_an_installed_package():
    tmp = tempfile.mkdtemp()
    try:
        _extract(tmp)
        os.remove(os.path.join(tmp, "uibc_core.pyz"))
        shim = _stub_package(os.path.join(tmp, "shim"))
        env = dict(os.environ)
        env["PYTHONPATH"] = shim
        env.pop("SOURCE_DATE_EPOCH", None)
        proc = subprocess.run([sys.executable, "run.py"], cwd=tmp, env=env,
                              capture_output=True, text=True, timeout=300)
        assert proc.returncode == 3, (
            "with no bundled verifier and an importable stand-in, the runner exited %d; "
            "borrowing it would make 'the archive carries its verifier' unfalsifiable"
            % proc.returncode)
        assert "carries no verifier of its own" in proc.stderr
        assert not os.path.isfile(os.path.join(tmp, "receipt.json")), (
            "a receipt was written, so a setup failure is publishable as a corpus result")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


@pytest.mark.skipif(not os.path.isfile(ARCHIVE), reason="needs a published archive")
def test_the_escape_hatch_says_which_verifier_answered():
    tmp = tempfile.mkdtemp()
    try:
        _extract(tmp)
        os.remove(os.path.join(tmp, "uibc_core.pyz"))
        stub = os.path.join(tmp, "accept_all.py")
        with io.open(stub, "w", encoding="utf-8", newline="\n") as f:
            f.write('import json\nprint(json.dumps({"result": "PASS", "checks": []}))\n')
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        env.pop("SOURCE_DATE_EPOCH", None)
        proc = subprocess.run([sys.executable, "run.py", "--allow-installed",
                               "--verify", '"%s" "%s" verify {pkg}' % (sys.executable, stub)],
                              cwd=tmp, env=env, capture_output=True, text=True, timeout=300)
        # an accept-all verifier fails some cases, so the exit code is 1 -- the point
        # here is only that the receipt exists and says where the verifier came from
        assert proc.returncode == 1, proc.stderr[-500:]
        import json
        with io.open(os.path.join(tmp, "receipt.json"), encoding="utf-8") as f:
            rec = json.load(f)
        assert rec["verifier_source"].startswith("installed in the Python"), rec["verifier_source"]
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
