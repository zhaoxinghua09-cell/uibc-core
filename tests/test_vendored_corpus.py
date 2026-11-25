"""The vendored corpus is the evidence under 171/69/88/14 -- keep it honest."""
import hashlib
import json
import os
import shutil
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(HERE, "tools"))

import verify_vendored_corpus as vv  # noqa: E402

CORPUS = vv.CORPUS
MANIFEST = vv.MANIFEST
SNAPSHOT = vv.SNAPSHOT

pytestmark = pytest.mark.skipif(
    not os.path.isdir(CORPUS),
    reason="docs/ is not shipped in the sdist; the vendored corpus lives there")


def _manifest():
    with open(MANIFEST, encoding="utf-8") as f:
        return json.load(f)


def test_the_corpus_on_disk_matches_the_manifest():
    out = vv.run(verbose=False)
    assert out["code"] == 0, out["problems"]
    assert out["files"] == 171


def test_its_digest_is_the_one_the_snapshot_receipt_carried():
    out = vv.run(verbose=False)
    with open(SNAPSHOT, encoding="utf-8") as f:
        snapshot = json.load(f)
    assert out["digest"] == snapshot["b_digest"]
    assert out["digest"] == _manifest()["manifest_digest"]


def test_the_digest_is_the_sweep_convention_not_a_convention_we_invented():
    """`corpus/` prefix, tab, sha256, newline, sorted -- the same lines the
    sweep and the ledger hash. Recomputing it here is what makes the vendored
    bytes comparable with the receipts."""
    m = _manifest()
    body = "".join("%s\t%s\n" % (e["path"], e["sha256"])
                   for e in sorted(m["files"], key=lambda e: e["path"]))
    assert all(e["path"].startswith("corpus/") for e in m["files"])
    assert hashlib.sha256(body.encode("utf-8")).hexdigest() == m["manifest_digest"]


def test_one_flipped_byte_is_caught_and_named(tmp_path):
    work = tmp_path / "corpus"
    shutil.copytree(CORPUS, work)
    victim = sorted(vv.scan(str(work)), key=lambda e: e["local"])[0]["local"]
    path = work / victim
    blob = bytearray(path.read_bytes())
    blob[-1] ^= 0x01
    path.write_bytes(bytes(blob))
    out = vv.run(str(work), verbose=False)
    assert out["code"] == 1
    assert victim in out["changed"]


def test_an_extra_vector_is_not_silently_adopted(tmp_path):
    work = tmp_path / "corpus"
    shutil.copytree(CORPUS, work)
    (work / "canonical" / "ZZZ-smuggled.json").write_text('{"id": "ZZZ"}', encoding="utf-8")
    out = vv.run(str(work), verbose=False)
    assert out["code"] == 1
    assert "canonical/ZZZ-smuggled.json" in out["extra"]


def test_the_competitor_check_runs_offline_on_the_vendored_copy():
    """No --dir, no network: the default must be the shipped bytes."""
    proc = subprocess.run([sys.executable, os.path.join(HERE, "tools", "stranger_competitor_check.py")],
                          cwd=HERE, capture_output=True, text=True, timeout=300)
    assert proc.returncode == 0, proc.stdout[-800:] + proc.stderr[-800:]
    assert "VERDICT: REPRODUCED" in proc.stdout
    assert "the vendored copy" in proc.stdout
