"""The base image pin: one reference, two files, and it has to be a digest.

What is being defended here: a Dockerfile that says `FROM python:3.13-slim-bookworm`
builds one machine today and another machine on the next upstream push, and nothing
in the repository would say so. The pin file exists so that reference is a digest,
and this module checks the parser refuses a tag, refuses a short digest, and notices
when the Dockerfile and the pin have drifted apart. The registry half of the check
needs the network, so it is exercised by the workflow job, not here.
"""

import importlib.util
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODULE = os.path.join(ROOT, "tools", "check_base_image_pin.py")


def _load():
    spec = importlib.util.spec_from_file_location("check_base_image_pin", MODULE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


pin = _load()


def _tree(tmp_path, pin_text, dockerfile_text):
    (tmp_path / "docker").mkdir()
    (tmp_path / "docker" / "base-image.pin").write_text(pin_text, encoding="utf-8")
    (tmp_path / "docker" / "Dockerfile").write_text(dockerfile_text, encoding="utf-8")
    return str(tmp_path)


DIGEST = "sha256:" + "0" * 64
REF = "python:3.13-slim-bookworm@" + DIGEST
DOCKERFILE_OK = f"ARG PYTHON_IMAGE={REF}\nFROM ${{PYTHON_IMAGE}}\n"


def test_the_repository_itself_is_consistent():
    """The shipped files must agree - this is the one assertion about the real repo."""
    ref, err = pin.read_pin(ROOT)
    assert err is None, err
    df_ref, err = pin.read_dockerfile_ref(ROOT)
    assert err is None, err
    assert ref == df_ref
    assert pin.REF_RE.match(ref).group("digest") not in ("0" * 64,)


def test_a_tag_alone_is_not_a_pin(tmp_path):
    root = _tree(tmp_path, "python:3.13-slim-bookworm\n", DOCKERFILE_OK)
    ref, err = pin.read_pin(root)
    assert ref is None
    assert "does not pin anything" in err


def test_a_short_digest_is_not_a_pin(tmp_path):
    root = _tree(tmp_path, "python:3.13-slim-bookworm@sha256:abc123\n", DOCKERFILE_OK)
    ref, err = pin.read_pin(root)
    assert ref is None and "does not pin anything" in err


def test_two_pins_are_ambiguous_and_refused(tmp_path):
    root = _tree(tmp_path, REF + "\n" + REF + "\n", DOCKERFILE_OK)
    ref, err = pin.read_pin(root)
    assert ref is None and "exactly one reference" in err


def test_a_dockerfile_without_the_arg_is_refused(tmp_path):
    root = _tree(tmp_path, REF + "\n", "FROM python:3.13-slim-bookworm\n")
    df_ref, err = pin.read_dockerfile_ref(root)
    assert df_ref is None and "no `ARG PYTHON_IMAGE=" in err


def test_drift_between_the_two_files_is_red(tmp_path):
    other = "python:3.13-slim-bookworm@sha256:" + "1" * 64
    root = _tree(tmp_path, REF + "\n", f"ARG PYTHON_IMAGE={other}\nFROM ${{PYTHON_IMAGE}}\n")
    proc = subprocess.run([sys.executable, MODULE, "--root", root],
                          capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "disagrees with the pin" in proc.stdout


def test_the_local_half_of_the_check_passes_on_a_consistent_tree(tmp_path):
    root = _tree(tmp_path, REF + "\n", DOCKERFILE_OK)
    proc = subprocess.run([sys.executable, MODULE, "--root", root],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "VERDICT: PIN CONSISTENT" in proc.stdout
    assert "registry not checked" in proc.stdout


def test_the_dockerfile_is_a_digest_not_a_tag_in_the_build_stage():
    """The ARG is quoted by FROM, not re-typed: a FROM with a bare tag would slip past."""
    text = open(os.path.join(ROOT, "docker", "Dockerfile"), encoding="utf-8").read()
    from_lines = [l for l in text.splitlines() if l.upper().startswith("FROM ")]
    assert from_lines, "no FROM line"
    for line in from_lines:
        assert "@sha256:" in line or "$" in line, line
