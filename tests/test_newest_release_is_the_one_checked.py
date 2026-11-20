"""v0.5.0 is the first release the signing key covers, so its evidence must be reachable.

Three defects surfaced while checking the release that had just been published:

1. `check_release_anchors.py` defaulted `--tag` to the literal `v0.4.1`, so after v0.5.0
   existed the tool verified the previous release and printed the current numbers under
   the old tag.
2. The pin written by `make_release_pin.py` records that the page's own
   `uibc-release-pin.json` is `excluded`, but `check_pin` ignored the key and reported the
   asset as unpinned -- an error about a convention it had itself produced.
3. The published page carries `CORPUS-DIGESTS.txt.sig`; the repository held no v0.5.0
   attestation, so with `--dir` the signature had nothing in-repo to be compared with.
"""
import io
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import check_release_anchors as check  # noqa: E402


def test_the_default_tag_is_the_newest_pin_not_a_literal():
    source = io.open(os.path.join(REPO, "tools", "check_release_anchors.py"),
                     encoding="utf-8").read()
    assert 'default="v0.4.1"' not in source
    tag = check._newest_pinned_tag()
    assert tag.startswith("v")
    assert os.path.isfile(os.path.join(REPO, "anchors", "pins",
                                       "uibc-release-%s.json" % tag))


def test_the_pin_of_the_newest_release_holds_its_own_pin_file_as_excluded():
    tag = check._newest_pinned_tag()
    blob = json.loads(io.open(os.path.join(REPO, "anchors", "pins",
                                           "uibc-release-%s.json" % tag),
                              encoding="utf-8").read())
    assert blob["excluded"], "the page's own pin file is not an asset the pin pins"


def test_an_excluded_asset_is_not_reported_as_unpinned(monkeypatch, tmp_path):
    tag = "v-test"
    pin_file = tmp_path / "uibc-release-v-test.json"
    pin_file.write_text(json.dumps({"tag": tag,
                                    "assets": [{"name": "a", "sha256": "0" * 64}],
                                    "excluded": ["uibc-release-pin.json"]}),
                        encoding="utf-8")
    monkeypatch.setattr(check, "PIN", str(pin_file).replace("v-test", "{tag}"))
    bad, lines, unsure = check.check_pin(
        tag, {"a": "0" * 64, "uibc-release-pin.json": "1" * 64})
    assert bad == 0 and unsure == 0
    assert not [l for l in lines if "uibc-release-pin.json" in l]


def test_the_repository_holds_the_attestation_for_the_newest_release():
    tag = check._newest_pinned_tag()
    d = os.path.join(REPO, "anchors", "attestations", tag)
    for name in ("CORPUS-DIGESTS.txt", "CORPUS-DIGESTS.txt.sig",
                 "CORPUS-DIGESTS.txt.ots", "ATTESTATION.json"):
        assert os.path.isfile(os.path.join(d, name)), name
    att = json.loads(io.open(os.path.join(d, "ATTESTATION.json"), encoding="utf-8").read())
    assert att["release"] == tag
    assert att["digest_file_sha256"]
