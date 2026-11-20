"""Every release has to carry a record of what it holds.

A tag whose page can be rewritten with everyone staying green is not a frozen
release, it is a URL. These tests are about the checks that notice, and about the
line between a pin written at publication and one written afterwards.
"""
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import check_release_pins as crp  # noqa: E402
import make_release_pin as mrp  # noqa: E402


def _pin(tag, digest="a" * 64, extra=None, excluded=()):
    assets = [{"name": "uibc-conformance-%s.zip" % tag, "bytes": 10, "sha256": digest}]
    if extra:
        assets.append(extra)
    return {"kind": "uibc-release-pin-v0", "tag": tag, "assets": assets,
            "excluded": list(excluded)}


def test_a_page_that_matches_its_pin_is_quiet():
    blob = _pin("v0.4.2")
    live = {a["name"]: a["sha256"] for a in blob["assets"]}
    assert crp.compare(blob, live, set()) == []


def test_a_rewritten_asset_is_named():
    blob = _pin("v0.4.2")
    live = {a["name"]: "b" * 64 for a in blob["assets"]}
    bad = crp.compare(blob, live, set())
    assert len(bad) == 1
    assert bad[0][0] == "uibc-conformance-v0.4.2.zip"
    assert bad[0][1] == "a" * 64 and bad[0][2] == "b" * 64


def test_an_asset_the_pin_never_saw_is_named():
    blob = _pin("v0.4.2")
    live = {a["name"]: a["sha256"] for a in blob["assets"]}
    live["extra.bin"] = "c" * 64
    bad = crp.compare(blob, live, set())
    assert [b[0] for b in bad] == ["extra.bin"]
    assert bad[0][1] is None


def test_an_asset_that_disappeared_is_named():
    blob = _pin("v0.4.2")
    live = {}
    bad = crp.compare(blob, live, set())
    assert bad and bad[0][2] is None


def test_the_pin_asset_itself_is_not_compared_with_itself():
    blob = _pin("v0.4.2", extra={"name": mrp.PIN_NAME, "bytes": 5, "sha256": "d" * 64},
                excluded=[mrp.PIN_NAME])
    blob["assets"] = [a for a in blob["assets"] if a["name"] != mrp.PIN_NAME]
    live = {a["name"]: a["sha256"] for a in blob["assets"]}
    live[mrp.PIN_NAME] = "e" * 64
    bad = crp.compare(blob, live, set(blob["excluded"]))
    assert bad == []


def test_every_published_release_has_a_pin_in_the_repository():
    pins = os.path.join(ROOT, "anchors", "pins")
    names = [n for n in os.listdir(pins) if n.startswith("uibc-release-")]
    # One tag is published with bytes: v0.4.1. Its pin must be there by name.
    assert "uibc-release-v0.4.1.json" in names
    for tag in ("v0.4.0", "anchor-001", "release-pins-0.4.0"):
        assert "uibc-release-%s.json" % tag in names, tag


def test_a_late_pin_says_it_is_late():
    blob = mrp.build("v0.4.0", [{"name": "x.zip", "bytes": 1, "sha256": "f" * 64}],
                     late=True)
    assert blob["recorded_late"] is True
    assert "does not show what it held when it was published" in blob["meaning"]
    assert "not the publishing process" in blob["recorded_by"]
    assert blob["excluded"] == []


def test_a_pin_written_at_publication_does_not_claim_to_be_late():
    blob = mrp.build("v0.4.2", [{"name": "x.zip", "bytes": 1, "sha256": "f" * 64}])
    assert "recorded_late" not in blob
    assert blob["excluded"] == [mrp.PIN_NAME]
    assert "cannot carry its own digest" in blob["why_excluded"]


def test_writing_over_a_pin_with_other_bytes_is_refused(tmp_path):
    path = os.path.join(str(tmp_path), "pin.json")
    assert mrp.write(path, _pin("v0.4.2")) == 0
    other = _pin("v0.4.2", digest="0" * 64)
    assert mrp.write(path, other) == 3
    kept = json.load(io.open(path, encoding="utf-8"))
    assert kept["assets"][0]["sha256"] == "a" * 64


def test_writing_the_same_content_twice_is_a_no_op(tmp_path):
    path = os.path.join(str(tmp_path), "pin.json")
    blob = _pin("v0.4.2")
    assert mrp.write(path, blob) == 0
    assert mrp.write(path, blob) == 0
