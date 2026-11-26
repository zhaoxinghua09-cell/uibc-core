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


def test_line_endings_are_their_own_condition(tool, tmp_path):
    """CRLF and LF of the same text: content digest moves, the folded one does not."""
    t = tmp_path / "t"
    (t / "a").mkdir(parents=True)
    (t / "a" / "one.txt").write_bytes(b"one\r\ntwo\r\n")
    content_crlf, _ = tool.content_digest(str(t))
    lf_crlf, _ = tool.content_lf_digest(str(t))
    (t / "a" / "one.txt").write_bytes(b"one\ntwo\n")
    content_lf, _ = tool.content_digest(str(t))
    lf_lf, _ = tool.content_lf_digest(str(t))
    assert content_crlf != content_lf          # a byte moved
    assert lf_crlf == lf_lf                     # but only line endings moved


def test_a_delivery_difference_is_named_and_not_called_a_blood_edit(tool, tmp_path, monkeypatch, capsys):
    """Archive bytes vs checkout bytes: same commit, two channels.

    This repository stores some blobs with CRLF while `.gitattributes` says
    `text=auto eol=lf`, so a tarball and a clone hand you different bytes for the
    same commit. A tree that differs only that way must be reported as DELIVERY
    MATCH, not as an edit - and the strict digest must still not match.
    """
    _require_full_tree()
    receipt = json.load(open(tool.RECEIPT, encoding="utf-8"))
    copy = tmp_path / "repo"
    tool.copy_tree(str(copy))
    victim = None
    for rel in ("CHANGELOG.md", "README.md", "docs/README.md"):
        p = copy / rel
        if p.exists() and b"\r\n" in p.read_bytes()[:4096]:
            victim = p
            break
    if victim is None:
        pytest.skip("no CRLF text file in this extraction; nothing to fold")
    victim.write_bytes(victim.read_bytes().replace(b"\r\n", b"\n"))
    monkeypatch.setattr(tool, "HERE", str(copy))
    rc = tool.check()
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "DELIVERY MATCH" in out
    assert receipt["tree_sha256"] != tool.tree_digest(str(copy))[0]


def test_without_git_the_commit_view_is_absent(tool, tmp_path):
    """No `.git`: the tool must say so and fall back, not guess."""
    t = tmp_path / "t"
    (t / "a").mkdir(parents=True)
    (t / "a" / "one.txt").write_text("one\n", encoding="utf-8")
    assert tool.commit_blobs(str(t)) is None
    views = tool.all_digests(str(t))
    assert [v[0] for v in views] == ["disk"]
    assert views[0][1][3] == 1

def test_a_stale_receipt_is_named_not_compared(tool, tmp_path, monkeypatch, capsys):
    """A receipt from an older release carries the strict digest only.

    It cannot answer for line endings or for the channel it came from, so it
    must be refused by name instead of being compared and quietly accepted.
    """
    legacy = {"tree_sha256": "0" * 64, "files_hashed": 1, "generated_at": "2026-01-01T00:00:00Z",
              "steps": [], "ok": True}
    path = tmp_path / "receipt.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")
    monkeypatch.setattr(tool, "RECEIPT", str(path))
    assert tool.check() == 1
    out = capsys.readouterr().out
    assert "STALE RECEIPT" in out
    assert "content_lf_sha256" in out and "delivery" in out


def test_scratch_outside_the_inventory_does_not_move_the_digest(tool, tmp_path):
    """A test run materialises `benchmark/corpus/`; the receipt must not notice.

    The membership comes from the published inventory, not from whatever happens
    to be on this disk, so a scratch directory a clone would never hold cannot
    change the number a stranger computes.
    """
    root = tmp_path / "tree"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "TRACKED-FILES.txt").write_text("a.txt\ndocs/TRACKED-FILES.txt\n",
                                                    encoding="utf-8")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    before = tool.tree_digest(str(root))
    (root / "benchmark" / "corpus" / "cases" / "M01").mkdir(parents=True)
    (root / "benchmark" / "corpus" / "cases" / "M01" / "manifest.json").write_text(
        "{}", encoding="utf-8")
    after = tool.tree_digest(str(root))
    assert before == after
    assert before[1] == 2                     # a.txt plus the inventory itself, nothing else


def test_a_listed_path_that_is_gone_is_named(tool, tmp_path, monkeypatch, capsys):
    """The inventory is a claim about a tree; a gap must be reported, not ignored."""
    root = tmp_path / "tree"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "TRACKED-FILES.txt").write_text("gone.txt\n", encoding="utf-8")
    monkeypatch.setattr(tool, "HERE", str(root))
    assert tool.check_inventory() == 1
    out = capsys.readouterr().out
    assert "listed but absent: gone.txt" in out

def test_receipt_carries_a_per_file_manifest(tool):
    """Each file's hash is in the receipt, so a mismatch can name the file."""
    _require_full_tree()
    receipt = json.load(open(tool.RECEIPT, encoding="utf-8"))
    manifest = receipt.get("files_sha256") or {}
    assert len(manifest) == receipt["files_hashed"]
    bad = [k for k, v in manifest.items() if len(v) != 64 or v.lower() != v]
    assert not bad, bad[:3]
    for rel in tool.GENERATED:
        assert rel not in manifest


def test_one_moved_byte_is_named(tool, tmp_path, monkeypatch, capsys):
    """The receipt says wwwich file, not just "something moved"."""
    root = tmp_path / "tree"
    (root / "docs").mkdir(parents=True)
    (root / "docs" / "TRACKED-FILES.txt").write_text(
        "a.txt\nb.txt\ndocs/TRACKED-FILES.txt\n", encoding="utf-8")
    (root / "a.txt").write_text("one\n", encoding="utf-8")
    (root / "b.txt").write_text("two\n", encoding="utf-8")
    monkeypatch.setattr(tool, "HERE", str(root))
    monkeypatch.setattr(tool, "RECEIPT", str(root / "receipt.json"))
    monkeypatch.setattr(tool, "PAGE", str(root / "page.md"))
    digest = tool.tree_digest(str(root))
    content = tool.content_digest(str(root))
    steps = [{"step": n, "cmd": " ".join(a), "rc": 0, "ok": True, "seconds": 0.0}
             for n, a, _expect in tool.STEPS]
    tool.write_receipt(digest[0], digest[1], steps, content=content[0],
                       content_files=content[1],
                       content_lf=tool.content_lf_digest(str(root))[0],
                       delivery="archive", files_sha256=tool.file_manifest(str(root)))
    capsys.readouterr()
    (root / "a.txt").write_text("one!\n", encoding="utf-8")
    assert tool.check() == 1
    out = capsys.readouterr().out
    assert "DRIFT a.txt" in out
    assert "DRIFT b.txt" not in out
