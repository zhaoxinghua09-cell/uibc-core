"""Discipline: a measured number in a doc must name the commit it was measured at.

Why this exists
---------------
`tools/check_doc_facts.py` verifies the numbers it can recompute from the tree
(test functions, checks, modules, attacks, cases). It cannot recompute "1,865
files" or "1471 passed": those are properties of one commit and one machine, and
they go stale the moment `main` moves. A stale but unmarked number is exactly how
a document starts lying without anyone editing it.

So this test does not check the value. It checks that the document says **where**
the value came from: any doc quoting a measured-constant marker must also carry a
seven-character commit id in the same sentence group.
"""

import pathlib
import re

DOCS = pathlib.Path(__file__).resolve().parent.parent / "docs"

# Markers that are measurements at a commit, not derivations from the tree.
MEASURED_MARKERS = re.compile(r"1,865 files|1471 passed|2,568,257 bytes")

COMMIT = re.compile(r"`[0-9a-f]{7}`|\b[0-9a-f]{7}\b")

# Phrases that tie a number to a commit.
PIN = ("at commit", "measured at", "Commit under test", "(at `", "at `")


def _docs_with_measurements():
    for p in sorted(DOCS.glob("*.md")):
        text = p.read_text(encoding="utf-8")
        if MEASURED_MARKERS.search(text):
            yield p, text


def test_every_measured_number_names_its_commit():
    offenders = []
    for path, text in _docs_with_measurements():
        for line_no, line in enumerate(text.splitlines(), 1):
            if MEASURED_MARKERS.search(line):
                if not (COMMIT.search(line) or any(p in line for p in PIN)):
                    offenders.append(f"{path.name}:{line_no}: {line.strip()[:90]}")
    assert not offenders, (
        "measured number without a commit: "
        + "; ".join(offenders)
    )


def test_the_pin_is_actually_a_commit_sha():
    """A seven-hex code anywhere is weak evidence; require it in the pin sites."""
    text = (DOCS / "REPRODUCTION.md").read_text(encoding="utf-8")
    assert "Commit under test" in text
    m = re.search(r"\*\*Commit under test: `([0-9a-f]{7})`\*\*", text)
    assert m, "REPRODUCTION.md must state the commit under test explicitly"
    assert len(m.group(1)) == 7
