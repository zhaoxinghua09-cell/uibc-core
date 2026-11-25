"""The two digests have a second implementation, and the tests make it stay honest.

Contracts:

1. on this tree, Python and Node compute the same `tree_sha256`,
   `content_sha256` and file count - the number is not one program's convention;
2. membership is handed over, not re-derived: both implementations hash exactly
   the list Python passes, so they cannot pass by agreeing on different files;
3. a renamed file moves the strict digest in both, and the content digest in
   neither - the two axes keep their meaning across implementations;
4. one flipped byte moves both digests in both.

If Node is absent the tests skip rather than fail: a missing runtime is not a
disagreement, and the CI job that owns this has Node by construction.
"""

import importlib.util
import os
import shutil

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FULL_TREE_MARKERS = ("CHANGELOG.md", "tools/mutation_gate.py", "docs/claims-register.md")


def _require_full_tree():
    missing = [m for m in FULL_TREE_MARKERS if not os.path.exists(os.path.join(ROOT, m))]
    if missing:
        pytest.skip("not the full source tree, missing " + ", ".join(missing))


@pytest.fixture(scope="module")
def tool():
    spec = importlib.util.spec_from_file_location(
        "tree_digest_second_impl", os.path.join(ROOT, "tools", "tree_digest_second_impl.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not (os.environ.get("NODE") or shutil.which("node")):
        pytest.skip("no node binary on PATH")
    return mod


def _mini(tmp_path):
    t = tmp_path / "t"
    (t / "a").mkdir(parents=True)
    (t / "a" / "one.txt").write_text("file 0\n", encoding="utf-8")
    (t / "a" / "two.md").write_text("file 1\n", encoding="utf-8")
    return t


def _by_name(rows):
    return {n: p for n, p, _ in rows}


def test_agrees_on_this_tree(tool):
    _require_full_tree()
    out = tool.compare()
    assert out["ok"], out["disagreements"]
    assert out["rows"][0][1] > 1000


def test_membership_is_handed_over(tool):
    """A subset list must produce a subset digest on both sides, not a surprise."""
    _require_full_tree()
    rerun = tool._load_rerun()
    files = tool.files_here(rerun, ROOT)
    subset = files[: len(files) // 2]
    out = tool.compare(ROOT, subset)
    assert out["ok"], out["disagreements"]
    assert out["rows"][0][1] == len(subset)


def test_rename_moves_tree_and_not_content(tool, tmp_path):
    t = _mini(tmp_path)
    before = tool.compare(str(t))
    assert before["ok"], before["disagreements"]
    (t / "a" / "one.txt").rename(t / "a" / "one-renamed.txt")
    after = tool.compare(str(t))
    assert after["ok"], after["disagreements"]
    assert _by_name(before["rows"])["tree_sha256"] != _by_name(after["rows"])["tree_sha256"]
    assert _by_name(before["rows"])["content_sha256"] == _by_name(after["rows"])["content_sha256"]


def test_one_flipped_byte_moves_both(tool, tmp_path):
    t = _mini(tmp_path)
    (t / "a" / "three.txt").write_text("third\n", encoding="utf-8")
    before = tool.compare(str(t))
    assert before["ok"], before["disagreements"]
    victim = t / "a" / "one.txt"
    victim.write_text(victim.read_text(encoding="utf-8") + "x", encoding="utf-8")
    after = tool.compare(str(t))
    assert after["ok"], after["disagreements"]
    for field in ("tree_sha256", "content_sha256"):
        assert _by_name(before["rows"])[field] != _by_name(after["rows"])[field], field
