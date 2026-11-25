"""This repository's own row has to be produced, not declared.

Five contracts:

1. the row in the snapshot equals what score_ours() computes right now;
2. remove a probe and that dimension drops - the row is falsifiable;
3. remove the gate and D4 drops, because there is no single exit code to read;
4. a row typed into the snapshot that disagrees with the artefacts is caught
   by --check and named;
5. the generated document says where the row comes from.
"""

import importlib.util
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load():
    spec = importlib.util.spec_from_file_location(
        "competitor_gate_parity", os.path.join(ROOT, "tools", "competitor_gate_parity.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def parity():
    return _load()


@pytest.fixture()
def snap(parity):
    return json.load(open(parity.SNAPSHOT, encoding="utf-8"))


def test_the_row_equals_what_the_artefacts_produce(parity, snap):
    computed = parity.score_ours()
    stored = {k: snap["ours"]["dims"][k] for k in computed}
    assert computed == stored
    assert sum(computed.values()) == 10


def test_removing_a_probe_drops_that_dimension(parity, monkeypatch):
    monkeypatch.setitem(parity.PROBES, "D2", os.path.join("tools", "does-not-exist.py"))
    dims = parity.score_ours()
    assert dims["D2"] == 0, "a dimension must fall when its probe is gone"
    assert dims["D1"] == 2 and dims["D4"] == 2


def test_removing_the_gate_drops_the_cross_layer_dimension(parity, monkeypatch):
    monkeypatch.setattr(parity, "GATE", os.path.join(parity.HERE, "tools", "no-gate.py"))
    dims = parity.score_ours()
    assert dims["D4"] == 0
    assert dims["D1"] == 0 and dims["D2"] == 0 and dims["D3"] == 0, (
        "the three evidence dimensions are gate-read too: without the gate nothing "
        "shows the sweeps are systematic")


def test_a_typed_in_row_is_caught(parity, snap, capsys):
    snap["ours"]["dims"]["D5"] = 1
    assert parity.check(snap) == 1
    out = capsys.readouterr().out
    assert "not what its artefacts produce" in out


def test_the_document_says_the_row_is_computed(parity):
    doc = open(parity.DOC, encoding="utf-8").read()
    assert "computed" in doc or "同一套证据" in doc
