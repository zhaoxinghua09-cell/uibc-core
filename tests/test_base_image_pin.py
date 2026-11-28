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


# --- the second interpreter -------------------------------------------------
#
# The one test that shell-outs to node skips itself when node is missing, so the
# first container run reported "40 passed, 1 skipped" and passed the fourth step
# on a narrower set than the host. Installing node from a pinned tarball is what
# closes that, and these tests are about the pin being a digest rather than a
# version string.

NODE_SHA = "a" * 64
NODE_URL = ("https://nodejs.org/dist/v26.13.1/node-v26.13.1-linux-x64.tar.xz")
NODE_OK = (f"v26.13.1\n{NODE_URL}\nsha256 {NODE_SHA}\n")
DF_WITH_NODE = (DOCKERFILE_OK + f'ARG NODE_TARBALL={NODE_URL}\nARG NODE_SHA256={NODE_SHA}\n')


def _tree2(tmp_path, pin_text, dockerfile_text, node_text=None):
    root = _tree(tmp_path, pin_text, dockerfile_text)
    if node_text is not None:
        (tmp_path / "docker" / "node.pin").write_text(node_text, encoding="utf-8")
    return root


def test_the_repository_pins_node_by_digest_too():
    url, sha, err = pin.read_node_pin(ROOT)
    assert err is None, err
    assert url and len(sha) == 64
    args, err = pin.read_dockerfile_args(ROOT)
    assert err is None, err
    assert args["NODE_TARBALL"] == url and args["NODE_SHA256"] == sha


def test_a_node_version_without_a_digest_is_refused(tmp_path):
    root = _tree2(tmp_path, REF + "\n", DOCKERFILE_OK,
                  "v26.13.1\n" + NODE_URL + "\n")
    _, _, err = pin.read_node_pin(root)
    assert err and "pins nothing" in err


def test_a_node_url_whose_version_disagrees_with_the_pin_is_refused(tmp_path):
    root = _tree2(tmp_path, REF + "\n", DOCKERFILE_OK,
                  "v26.13.0\n" + NODE_URL + f"\nsha256 {NODE_SHA}\n")
    _, _, err = pin.read_node_pin(root)
    assert err and "URL points at v26.13.1" in err


def test_the_dockerfile_must_quote_the_node_pin(tmp_path):
    other = "https://nodejs.org/dist/v24.0.0/node-v24.0.0-linux-x64.tar.xz"
    root = _tree2(tmp_path, REF + "\n",
                  DOCKERFILE_OK + f"ARG NODE_TARBALL={other}\nARG NODE_SHA256={NODE_SHA}\n",
                  NODE_OK)
    proc = subprocess.run([sys.executable, MODULE, "--root", root],
                          capture_output=True, text=True)
    assert proc.returncode == 1, proc.stdout + proc.stderr
    assert "disagrees with docker/node.pin" in proc.stdout


def test_a_tree_without_the_node_pin_is_merely_a_note(tmp_path):
    root = _tree2(tmp_path, REF + "\n", DOCKERFILE_OK, None)
    proc = subprocess.run([sys.executable, MODULE, "--root", root],
                          capture_output=True, text=True)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "does not claim a second interpreter" in proc.stdout

