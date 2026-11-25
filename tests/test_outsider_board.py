"""The outsider board is one page, and it has to keep saying what the receipt says."""

import importlib.util
import json
import os
import re
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def load_tool():
    spec = importlib.util.spec_from_file_location(
        "render_outsider_board", os.path.join(HERE, "tools", "render_outsider_board.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture()
def tool():
    return load_tool()


def _require_board():
    if not os.path.exists(os.path.join(HERE, "docs", "OUTSIDER-BOARD.html")):
        pytest.skip("the board has not been generated in this extraction")


def test_the_page_matches_the_receipt(tool, capsys):
    _require_board()
    assert tool.check() == 0


def test_one_flipped_character_is_caught(tool, tmp_path, monkeypatch, capsys):
    """A hand-edited number must not survive --check."""
    _require_board()
    text = open(os.path.join(HERE, "docs", "OUTSIDER-BOARD.html"), encoding="utf-8").read()
    snap = json.loads(re.search(r'<script id="snap" type="application/json">\s*(.*?)\s*</script>',
                                text, re.S).group(1))
    digits = snap["tree_sha256"]
    snap["tree_sha256"] = ("f" if digits[0] != "f" else "0") + digits[1:]
    edited = text.replace(digits, snap["tree_sha256"], 1)
    path = tmp_path / "board.html"
    path.write_text(edited, encoding="utf-8")
    monkeypatch.setattr(tool, "BOARD", str(path))
    assert tool.check() == 1
    out = capsys.readouterr().out
    assert "tree_sha256" in out


def test_the_page_links_nowhere(tool):
    """Offline is a property, not a promise: no stylesheet, no script, no URL."""
    _require_board()
    text = open(os.path.join(HERE, "docs", "OUTSIDER-BOARD.html"), encoding="utf-8").read()
    assert "https://" not in text and "http://" not in text
    assert "<link" not in text and "<img" not in text
    assert 'src="' not in text
    # the gate names are read out of the checker, not retyped
    names = [g["name"] for g in tool.snapshot()["gates"]]
    assert len(names) == 10
    for n in names:
        assert n in text
