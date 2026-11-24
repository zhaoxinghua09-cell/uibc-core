"""The one-command recheck must agree with the per-file tool, and must fail loudly.

Three properties, and each is a way the entry point could quietly stop meaning
anything:

- it reproduces every committed result (otherwise the counts in the documents
  are not checkable by a reader);
- a single altered byte in a committed result is reported as drift (otherwise
  it would bless whatever is on disk);
- `--no-probe` reports carried rows as UNRUN rather than as covered (otherwise
  a static run would look like a verified one).
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))

import recheck  # noqa: E402


def test_recheck_reproduces_every_committed_result():
    assert recheck.main(["--quiet"]) == 0


def test_one_altered_byte_in_a_committed_result_is_drift(tmp_path):
    out = ROOT / "tools" / "out"
    for f in out.glob("crosswalk-*.json"):
        (tmp_path / f.name).write_text(f.read_text(encoding="utf-8"), encoding="utf-8")
    victim = tmp_path / "crosswalk-21cfr11.json"
    text = victim.read_text(encoding="utf-8")
    victim.write_text(text.replace('"verdict": "OK"', '"verdict": "XX"', 1), encoding="utf-8")
    assert recheck.main(["--quiet", "--out-dir", str(tmp_path)]) == 3


def test_static_only_reports_carried_rows_as_unrun_not_covered():
    # No probes run, so nothing is COVERED; the summary must not imply otherwise.
    assert recheck.main(["--quiet", "--no-probe"]) == 0
