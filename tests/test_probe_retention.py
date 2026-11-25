"""The retention probe must pass on a clean package and fail on an altered one.

A probe that only ever passes is a paragraph with a shebang. The second test
copies the clean fixture to a temporary directory, changes one byte of an
evidence file, and expects the probe to notice - without touching the fixture in
the repository.
"""
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import probe_retention  # noqa: E402

CLEAN = ROOT / "fixtures" / "clean.uibc"
TAMPERED = ROOT / "fixtures" / "tampered.uibc"


def test_the_clean_package_passes_all_four():
    assert probe_retention.main([]) == 0


def test_an_altered_evidence_file_is_noticed(tmp_path):
    copy = tmp_path / "clean.uibc"
    shutil.copytree(CLEAN, copy)
    victim = copy / "evidence" / "files" / "action-log.txt"
    victim.write_text(victim.read_text(encoding="utf-8") + "one more line\n", encoding="utf-8")
    # Same clean package, one altered evidence file: the intact check must fail.
    assert probe_retention.main(["--package", str(copy), "--tampered", str(TAMPERED)]) == 1


def test_a_package_that_cleans_up_after_itself_is_refused(tmp_path):
    """A format that sets its own retention period is deciding someone else's policy."""
    copy = tmp_path / "clean.uibc"
    shutil.copytree(CLEAN, copy)
    manifest = copy / "manifest.json"
    doc = manifest.read_text(encoding="utf-8").replace(
        '"status": "SUBMITTED"', '"status": "SUBMITTED",\n  "retention_days": 365')
    manifest.write_text(doc, encoding="utf-8")
    assert probe_retention.main(["--package", str(copy), "--tampered", str(TAMPERED)]) == 1
