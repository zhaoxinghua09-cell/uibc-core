"""The numbers in the claims register must still equal the receipts they cite."""

import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, "tools"))

import audit_claims_receipts as audit  # noqa: E402


def _text():
    with open(audit.CLAIMS, encoding="utf-8") as f:
        return f.read()


def test_every_locked_row_agrees_with_its_receipt():
    rows, problems, stats = audit.audit(_text())
    assert problems == [], problems
    assert stats["locked"] >= 4


def test_the_receipt_backed_rows_are_the_measured_ones():
    rows, _p, _s = audit.audit(_text())
    locked = {r["claim"] for r in rows if r["locked"]}
    assert {"A18", "A19", "A23", "A24"} <= locked


def test_a_stale_prose_figure_fails():
    """Change one figure in the prose and the audit must notice."""
    text = _text()
    # The A24 row is the only place that quotes the ledger's 171; move it there.
    a24 = [ln for ln in text.splitlines() if ln.startswith("| A24 |")][0]
    assert "171" in a24
    rows, problems, _s = audit.audit(text.replace(a24, a24.replace("171", "172")))
    assert any("A24" in p and "does not appear" in p for p in problems)


def test_a_receipt_that_moved_fails(tmp_path, monkeypatch):
    """A regenerated receipt with an unchanged row must also fail."""
    import json
    import shutil

    real = os.path.join(REPO, "docs", "upstream-package", "competitor-defects",
                        "corpus-ledger-39daf704.json")
    fake_root = tmp_path / "root"
    target = fake_root / "docs" / "upstream-package" / "competitor-defects"
    target.mkdir(parents=True)
    shutil.copyfile(real, target / "corpus-ledger-39daf704.json")
    with open(target / "corpus-ledger-39daf704.json", encoding="utf-8") as f:
        data = json.load(f)
    data["totals"]["nothing"] = 15
    with open(target / "corpus-ledger-39daf704.json", "w", encoding="utf-8") as f:
        json.dump(data, f)
    rows, problems, _s = audit.audit(_text(), root=str(fake_root))
    assert any("A24" in p for p in problems)


def test_unlocked_rows_are_counted_not_silently_passed():
    rows, problems, stats = audit.audit("| A99 | plain sentence |\n")
    assert problems == []
    assert stats == {"claims": 1, "locked": 0, "unlocked": 1}
