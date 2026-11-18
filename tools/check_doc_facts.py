#!/usr/bin/env python3
"""Check the numbers we publish against the numbers we can measure.

Every claim in the README is a promise a reviewer will test. The README said
328 tests while the suite ran 503 -- not a lie, just decay: the number was
true when someone typed it and nothing kept it true afterwards. A document
that drifts is worse than a document that is vague, because it is specific and
wrong.

So: count what can be counted, then read the documents that make numeric
claims about it, and report the mismatches. Historical records under docs/ are
excluded on purpose -- they are dated findings, and rewriting them would be
falsifying a record rather than correcting a claim.

    python3 tools/check_doc_facts.py            # report, exit 1 on a mismatch
    python3 tools/check_doc_facts.py --json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
for p in (_REPO, os.path.join(_REPO, "tools")):
    if p not in sys.path:
        sys.path.insert(0, p)

# Documents a reader is meant to trust as current. Dated findings under docs/
# and CHANGELOG entries describe a moment and are not checked.
TARGETS = ["README.md", "README.en.md", "QUICKSTART.md", "INSTALL.md", "AGENTS.md"]

CLAIMS = (
    # (label, regex, group that holds the number)
    ("tests", re.compile(r"(\d{2,4})\s+tests\b"), 1),
    ("tests", re.compile(r"(\d{2,4})\s+用例"), 1),
    ("checks", re.compile(r"(\d{2,3})\s+checks\b(?!\s*[)]?[^\n]{0,40}independent)"), 1),
    ("attacks", re.compile(r"(\d{2,3})\s+attacks\b"), 1),
    ("cases", re.compile(r"(\d{2,3})\s+red-team cases\b"), 1),
)


def measure():
    loader = unittest.TestLoader()
    suite = loader.discover(os.path.join(_REPO, "tests"), pattern="test_*.py")
    from uibc_core.basis import BASIS
    facts = {"tests": suite.countTestCases(), "checks": len(BASIS)}
    try:
        import check_matrix
        facts["attacks"] = check_matrix.build(check_matrix.audit())["n_attacks"]
    except Exception:
        facts["attacks"] = None
    try:
        import redteam_suite
        facts["redteam_attacks"] = len(getattr(redteam_suite, "CASES", []))
    except Exception:
        facts["redteam_attacks"] = None
    try:
        man = json.load(open(os.path.join(_REPO, "conformance", "manifest.json"),
                             encoding="utf-8"))
        facts["cases"] = len(man["cases"])
    except Exception:
        facts["cases"] = None
    return facts


SKIP_LINE = ("independent_verifier", "cross_check", "second implementation")


def scan(paths):
    findings = []
    for rel in paths:
        full = rel if os.path.isabs(rel) else os.path.join(_REPO, rel)
        if not os.path.isfile(full):
            continue
        with open(full, encoding="utf-8", errors="replace") as fh:
            for lineno, line in enumerate(fh, 1):
                if any(k in line for k in SKIP_LINE) and "checks" in line:
                    continue
                for label, rx, group in CLAIMS:
                    for m in rx.finditer(line):
                        kind = label
                        if label == "attacks" and "redteam_suite" in line:
                            # A different tool with a different count; the line
                            # names it, so the claim is about that one.
                            kind = "redteam_attacks"
                        findings.append({"file": rel, "line": lineno, "kind": kind,
                                         "claimed": int(m.group(group)),
                                         "text": line.strip()[:120]})
    return findings


def check(facts, paths=TARGETS):
    bad = []
    for f in scan(paths):
        actual = facts.get(f["kind"])
        if actual is None or f["claimed"] == actual:
            continue
        # A claim inside a fenced historical quote or a percentage/ratio phrase
        # is not a claim about the current tree; the line text is kept so a
        # reader can judge, and the exit code stays honest either way.
        bad.append(dict(f, actual=actual))
    return bad


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--files", nargs="*", default=None)
    a = ap.parse_args()
    facts = measure()
    bad = check(facts, a.files or TARGETS)
    if a.json:
        print(json.dumps({"facts": facts, "mismatches": bad}, ensure_ascii=False, indent=2))
    else:
        print("measured: %s" % facts)
        if not bad:
            print("all published numbers match")
        for b in bad:
            print("%s:%d  %s claims %d, measured %d\n    %s"
                  % (b["file"], b["line"], b["kind"], b["claimed"], b["actual"], b["text"]))
        print("\n%d mismatch(es)" % len(bad))
    sys.exit(1 if bad else 0)
