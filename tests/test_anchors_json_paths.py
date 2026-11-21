"""A published ANCHORS.json must not carry the machine it was produced on.

Measured 2026-11-20 in a dry run of the release steps: the TSA detail read
`RESULT_JSON=C:\\Users\\ADMINI~1\\AppData\\Local\\Temp\\dryrun_...\\release\\anchor_freetsa.json`.
That file is uploaded to the release, so the value would differ on the CI runner and mean
nothing on a reader's machine.
"""
import importlib.util
import json
import os
import sys

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOL = os.path.join(REPO, "tools", "anchor_release_digests.py")


def load_tool():
    spec = importlib.util.spec_from_file_location("anchor_release_digests", TOOL)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def tool():
    return load_tool()


def test_a_windows_absolute_path_is_reduced_to_a_name(tool):
    line = tool._detail_line("RESULT_JSON=C:\\Users\\x\\Temp\\release\\anchor_freetsa.json")
    assert line == "RESULT_JSON=anchor_freetsa.json"
    assert "C:\\" not in line


def test_a_posix_absolute_path_is_reduced_to_a_name(tool):
    line = tool._detail_line("RESULT_JSON=/home/runner/work/release/anchor_freetsa.json")
    assert line == "RESULT_JSON=anchor_freetsa.json"


def test_a_plain_message_is_left_alone(tool):
    assert tool._detail_line("anchored: token written") == "anchored: token written"


def test_empty_output_becomes_no_output(tool):
    assert tool._detail_line("") == "no output"
    assert tool._detail_line("   \n ") == "no output"


def test_the_last_line_is_the_one_kept(tool):
    text = "working\nmore working\nRESULT_JSON=/tmp/x/anchor_freetsa.json\n"
    assert tool._detail_line(text) == "RESULT_JSON=anchor_freetsa.json"


def test_anchor_writes_no_absolute_path_into_the_published_json(tmp_path, monkeypatch):
    """Drive `anchor` with a stub child that prints an absolute RESULT_JSON."""
    import subprocess

    class Proc:
        def __init__(self, code, out):
            self.returncode = code
            self.stdout = out
            self.stderr = ""

    def fake_run(argv, **kwargs):
        if any("anchor_tsa" in a for a in argv):
            return Proc(0, "RESULT_JSON=%s\n" % str(tmp_path / "anchor_freetsa.json"))
        return Proc(1, "ModuleNotFoundError: No module named 'opentimestamps'\n")

    monkeypatch.setattr(subprocess, "run", fake_run)
    head = tmp_path / "CORPUS-DIGESTS.txt"
    head.write_text("abc  file.zip\n", encoding="utf-8")
    module = load_tool()
    out, status = module.anchor(str(head), str(tmp_path))
    assert status["tsa"]["state"] == "anchored"
    assert status["tsa"]["detail"] == "RESULT_JSON=anchor_freetsa.json"
    assert status["ots"]["state"] == "unavailable"
    written = json.loads(open(out, encoding="utf-8").read())
    flat = json.dumps(written)
    assert str(tmp_path) not in flat

def test_a_missing_asn1crypto_is_a_named_dependency_not_a_nameerror():
    """Measured 2026-11-20 in the release workflow: ANCHORS.json recorded
    `NameError: name 'tsp' is not defined` instead of naming the missing package."""
    import uibc_core.tsa as tsa

    class Stub:
        HAVE_ASN1 = False

    original = tsa.HAVE_ASN1
    try:
        tsa.HAVE_ASN1 = False
        with pytest.raises(RuntimeError) as excinfo:
            tsa.build_request(b"x")
        assert "asn1crypto" in str(excinfo.value)
        assert "pip install" in str(excinfo.value)
    finally:
        tsa.HAVE_ASN1 = original
