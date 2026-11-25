"""The outsider receipt has to be a witness, not a souvenir.

Contracts:

1. the tree digest is stable and excludes the two files the tool writes;
2. the environment handed to the steps carries no credentials;
3. the receipt validates against the current tree;
4. a single edited byte anywhere in the tree breaks the match - the digest is
   not decorative;
5. the copy the steps run in has no `.git`, so nothing can be resolved from the
   author's history.
"""

import importlib.util
import json
import os
import shutil
import tempfile

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FULL_TREE_MARKERS = ("CHANGELOG.md", "docs/COMPETITOR-GATE-PARITY.md", "tools/mutation_gate.py")


def _require_full_tree():
    """A receipt describes the source tree, not an sdist.

    The packaging job runs these tests inside an extracted sdist, which carries
    less than a clone. There the receipt can never match by design, so say so
    instead of reporting a broken tree.
    """
    missing = [m for m in FULL_TREE_MARKERS if not os.path.exists(os.path.join(ROOT, m))]
    if missing:
        import pytest as _pytest
        _pytest.skip("not the full source tree, missing " + ", ".join(missing))


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "outsider_rerun", os.path.join(ROOT, "tools", "outsider_rerun.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_digest_is_stable_and_ignores_its_own_output(tool):
    _require_full_tree()
    a = tool.tree_digest(ROOT)
    b = tool.tree_digest(ROOT)
    assert a == b
    assert a[1] > 1000            # a real tree, not an empty walk
    for rel in tool.GENERATED:
        assert rel.startswith("docs/")


def test_clean_environment_carries_no_credentials(tool):
    env = tool.clean_env()
    banned = {"GPAT", "GH_TOKEN", "GITHUB_TOKEN", "AWS_SECRET_ACCESS_KEY"}
    assert not (banned & set(env))
    for key in env:
        assert key in tool.ENV_KEEP, key


def test_receipt_matches_this_tree(tool):
    _require_full_tree()
    assert tool.check() == 0


def test_one_edited_byte_breaks_the_match(tool, tmp_path):
    _require_full_tree()
    receipt = json.load(open(tool.RECEIPT, encoding="utf-8"))
    copy = tmp_path / "repo"
    tool.copy_tree(str(copy))
    victim = copy / "CHANGELOG.md"
    text = victim.read_text(encoding="utf-8")
    victim.write_text(text + "\n<!-- one extra line -->\n", encoding="utf-8")
    digest, _ = tool.tree_digest(str(copy))
    assert digest != receipt["tree_sha256"]


def test_copy_has_no_history(tool, tmp_path):
    _require_full_tree()
    copy = tmp_path / "repo"
    tool.copy_tree(str(copy))
    assert not (copy / ".git").exists()
    assert (copy / "tools" / "mutation_gate.py").exists()
    assert not (copy / "__pycache__").exists()
