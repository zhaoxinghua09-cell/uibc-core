"""The outsider receipt has to be a witness, not a souvenir.

Contracts:

1. the tree digest is stable and excludes the two files the tool writes;
2. the environment handed to the steps carries no credentials;
3. the receipt validates against the current tree;
4. a single edited byte anywhere in the tree breaks the match - the digest is
   not decorative;
5. the copy the steps run in has no `.git`, so nothing can be resolved from the
   author's history.
6. the receipt answers *why* a tree moved: a rename changes the strict digest
   but not the content digest, and `--check` then says `NAMES-ONLY` instead of
   blaming the repository for an extractor's mojibake.
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


def test_content_digest_ignores_names(tool, tmp_path):
    """A rename must move the strict digest and leave the content digest alone.

    Built on a synthetic tree on purpose. Copying the real tree is not a safe
    way to test this: a suite run leaves untracked files behind, the source is
    read through `git ls-files` while a copy is read by walking, so the two
    listings can legitimately differ and the assertion would test the runner's
    leftovers rather than the digest.
    """
    t = tmp_path / "t"
    (t / "a").mkdir(parents=True)
    (t / "a" / "one.txt").write_text("one\n", encoding="utf-8")
    (t / "a" / "two.md").write_text("two\n", encoding="utf-8")

    tree1, n1 = tool.tree_digest(str(t))
    content1, c1 = tool.content_digest(str(t))
    (t / "a" / "one.txt").rename(t / "a" / "one-renamed.txt")
    tree2, n2 = tool.tree_digest(str(t))
    content2, c2 = tool.content_digest(str(t))

    assert (tree1, n1) != (tree2, n2)
    assert (content1, c1) == (content2, c2)


def test_names_only_mismatch_is_named_as_such(tool, tmp_path, monkeypatch, capsys):
    """A receipt whose strict digest is stale but whose bytes match says NAMES-ONLY."""
    _require_full_tree()
    receipt = json.load(open(tool.RECEIPT, encoding="utf-8"))
    forged = dict(receipt)
    forged["tree_sha256"] = "0" * 64
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(forged), encoding="utf-8")
    monkeypatch.setattr(tool, "RECEIPT", str(path))
    rc = tool.check()
    out = capsys.readouterr().out
    assert rc == 2, rc
    assert "NAMES-ONLY" in out
    assert "HOW TO FIX" in out


def test_a_real_byte_move_is_not_excused_as_names(tool, tmp_path, monkeypatch, capsys):
    """Editing a file must degrade to CONTENT, never be waved through as NAMES-ONLY."""
    _require_full_tree()
    receipt = json.load(open(tool.RECEIPT, encoding="utf-8"))
    copy = tmp_path / "repo"
    tool.copy_tree(str(copy))
    victim = copy / "CHANGELOG.md"
    victim.write_text(victim.read_text(encoding="utf-8") + "\n<!-- edited -->\n", encoding="utf-8")
    monkeypatch.setattr(tool, "HERE", str(copy))
    rc = tool.check()
    out = capsys.readouterr().out
    assert rc == 1, rc
    assert "CONTENT" in out
    assert "NAMES-ONLY" not in out
    assert receipt["content_sha256"] != tool.content_digest(str(copy))[0]
