"""The block-height claim has to rest on arithmetic, not on a record.

Measured before this tool existed: `check_release_anchors.py` printed
"block 976684, merkle root 6fce2db8..." because `BITCOIN-ATTESTATION.json` said
so. Nothing recomputed the merkle path from the digest. These tests hold the
walk to both directions: the real proof must land on the recorded root, and
every way of breaking it -- one flipped byte, the wrong file, the wrong record,
a bare tree -- must be caught.
"""

import json
import os
import sys


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))

import ots_merkle  # noqa: E402

HELD = os.path.join(ROOT, "anchors", "attestations", "v0.4.1")
PROOF = os.path.join(HELD, "CORPUS-DIGESTS.txt.ots")
DATA = os.path.join(HELD, "CORPUS-DIGESTS.txt")
RECORD = os.path.join(HELD, "BITCOIN-ATTESTATION.json")


def _block():
    with open(RECORD, encoding="utf-8") as handle:
        return json.load(handle)["bitcoin"]


def _copy(tmp_path, name, blob):
    path = tmp_path / name
    path.write_bytes(blob)
    return str(path)


def test_the_real_proof_walks_to_the_recorded_root():
    result = ots_merkle.verify(PROOF, DATA, _block())
    assert result["exit"] == 0
    assert result["bound"] is True
    assert result["digest"] == "153f9b898878aaa9da97c7a496dd22af124d9bb3112ec5fede0a04eff94df033"
    assert result["blocks"][0]["height"] == 976684
    assert result["blocks"][0]["order"] == "reversed (as explorers print it)"
    assert "agrees with the recorded root" in result["lines"][-1]


def test_the_walk_reaches_the_root_without_the_ots_library():
    # No `opentimestamps` import anywhere: this module is standard library only.
    source = open(ots_merkle.__file__, encoding="utf-8").read()
    assert "import opentimestamps" not in source
    assert "from opentimestamps" not in source
    with open(PROOF, "rb") as handle:
        digest, root = ots_merkle.parse(handle.read())
    found = ots_merkle.leaves(root)
    kinds = sorted(kind for _path, node in found for kind, _value in node["attestations"])
    assert kinds == ["bitcoin", "other:83dfe30d2ef90c8e"]  # the alice calendar, still pending
    bitcoin = [node["message"].hex() for _path, node in found
               if any(kind == "bitcoin" for kind, _v in node["attestations"])]
    assert bitcoin == ["b4ad94e49cb1951eb2afd7b79207032cbefeed886fba27b9b8500da6b82dce6f"]


def test_one_flipped_byte_in_the_path_changes_the_root(tmp_path):
    with open(PROOF, "rb") as handle:
        blob = bytearray(handle.read())
    blob[100] ^= 0x01
    result = ots_merkle.verify(_copy(tmp_path, "flipped.ots", bytes(blob)), DATA, _block())
    assert result["exit"] == 1
    assert result["blocks"][0]["root"] != _block()["merkle_root"]
    assert "not the recorded root" in result["lines"][-1]


def test_a_proof_for_another_file_is_not_accepted():
    # The record itself is a file on disk; offering it as the data must fail on
    # binding, before any root comparison is believed.
    result = ots_merkle.verify(PROOF, RECORD, _block())
    assert result["exit"] == 1
    assert result["bound"] is False
    assert "NO" in result["lines"][1]


def test_a_record_with_another_root_is_not_accepted():
    result = ots_merkle.verify(PROOF, DATA, {"merkle_root": "00" * 32})
    assert result["exit"] == 1


def test_a_record_that_says_nothing_is_not_a_pass():
    # Absent a block to compare with, the tool must say "not measured" rather
    # than print a height and call it verified.
    result = ots_merkle.verify(PROOF, DATA, None)
    assert result["exit"] == 3
    assert "no block recorded" in result["lines"][-1]


def test_a_bare_tree_is_reported_not_guessed(tmp_path):
    with open(PROOF, "rb") as handle:
        blob = handle.read()
    bare = blob[33:]  # drop the 31-byte magic, version byte and hash-op tag
    result = ots_merkle.verify(_copy(tmp_path, "bare.ots", bare), DATA, _block())
    assert result["exit"] == 3
    assert "bare tree" in result["lines"][0]


def test_a_truncated_proof_is_reported_not_guessed(tmp_path):
    with open(PROOF, "rb") as handle:
        blob = handle.read()
    result = ots_merkle.verify(_copy(tmp_path, "short.ots", blob[:-40]), DATA, _block())
    assert result["exit"] == 3
    assert "truncated" in result["lines"][0]


def test_the_command_line_says_what_it_concluded(capsys):
    code = ots_merkle.main([PROOF, "--data", DATA, "--block-json", RECORD])
    out = capsys.readouterr().out
    assert code == 0
    assert "ACCEPTABLE" in out
    assert "976684" in out


def test_the_checker_prints_the_walk_not_just_the_record():
    source = open(os.path.join(ROOT, "tools", "check_release_anchors.py"),
                  encoding="utf-8").read()
    assert "ots_merkle.verify" in source
