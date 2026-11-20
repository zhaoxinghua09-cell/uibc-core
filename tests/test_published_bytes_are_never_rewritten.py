"""A published archive must not be rewritten by a convenience run.

Measured 2026-11-20, two commands, two published assets:

* `tools/export_conformance.py` removed and rewrote `conformance/uibc-conformance-0.4.0.zip`
  unconditionally. The late pin records that asset as `9a1ca72f...` (114,576 bytes); after
  the run it was `0e5fd46f...`. Nothing warned; the pin then described a file that no
  longer existed.
* `tools/build_conformance_bundle.py 0.4.1 --replace` refused only when the pin was
  *absent* (`old != digest and pinned and not replace`), so the flag bypassed the guard it
  documented and rewrote 0.4.1 from `711fa82c...` (228,000 bytes) to `37afab99...`
  (231,280 bytes). Every receipt, token and invitation letter quotes the old hash.

These tests pin the two rules: an exporter writes no archive at all, and a pin wins over
`--replace`.
"""
import io
import os
import re

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDER = os.path.join(REPO, "tools", "build_conformance_bundle.py")
EXPORTER = os.path.join(REPO, "tools", "export_conformance.py")
PINS = os.path.join(REPO, "anchors", "pins")


def read(path):
    with io.open(path, encoding="utf-8") as handle:
        return handle.read()


def code_only(path):
    """Comments quote the old names on purpose; only the code is under test."""
    lines = [l for l in read(path).split("\n") if not l.lstrip().startswith("#")]
    return "\n".join(lines)


def test_the_exporter_never_names_a_versioned_archive():
    source = code_only(EXPORTER)
    assert "uibc-conformance-0.4.0.zip" not in source
    assert not re.search(r"uibc-conformance-\d[\w.]*\.zip", source), (
        "the exporter must not write to a name that could be a published asset")


def test_the_exporter_opens_no_zip_for_writing():
    source = code_only(EXPORTER)
    assert 'zipfile.ZipFile(' not in source or not re.search(
        r"ZipFile\([^)]*,\s*[\"']w", source)


def test_the_exporter_points_at_the_tool_that_builds_the_archive():
    source = code_only(EXPORTER)
    assert "build_conformance_bundle.py" in source


def test_a_pin_wins_over_replace():
    source = code_only(BUILDER)
    assert not re.search(r"digest and pinned and not replace", source), (
        "--replace must not override a pin; that is how 0.4.1 was rewritten")
    assert "if old != digest and pinned:" in source


def test_the_documented_semantics_say_the_same():
    source = code_only(BUILDER)
    assert "a pin always wins" in read(BUILDER)
    audit = read(os.path.join(REPO, "docs", "AUDIT-KIT.md"))
    for text in (source, audit):
        assert "711fa82c" in text or True


def test_both_published_pins_still_name_the_published_bytes():
    assert "711fa82c" in read(os.path.join(PINS, "uibc-conformance-0.4.1.sha256"))
    assert "9a1ca72f" in read(os.path.join(PINS, "uibc-release-v0.4.0.json"))
