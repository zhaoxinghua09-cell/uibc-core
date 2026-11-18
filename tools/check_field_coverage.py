"""For every field the package writes, change it and see who notices.

F-007 came from asking a question about a check by name and getting a surprise:
the `agent_id` on lifecycle events was written by every package, declared by the
schema, and read by no check at all. This tool asks that question for every leaf
field in the package, by measurement rather than by reading the code.

For each leaf: copy the clean fixture, replace that value with a different but
still well-formed one, run verify, and record the set of checks that turn FAIL.

An empty set does not mean the field is unprotected by accident. Descriptive
fields (a note, a media type) legitimately change nothing. The point of printing
them is to make the distinction visible instead of assumed: every field now has
an answer, and a reviewer can disagree with the answer.

Usage:  python3 tools/check_field_coverage.py [--json]
"""
from __future__ import annotations

import copy
import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
BASE = os.path.join(REPO, "fixtures", "clean.uibc")
sys.path.insert(0, REPO)
sys.path.insert(0, HERE)

from uibc_core.verify import verify  # noqa: E402

JSON_FILES = ("manifest.json", "identity.json", "lifecycle.json",
              "evidence/index.json", "signatures/seal.json")


def leaves(obj, prefix=""):
    if isinstance(obj, dict):
        for k in obj:
            yield from leaves(obj[k], prefix + "/" + k)
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from leaves(v, prefix + "[%d]" % i)
    else:
        yield prefix, obj


def _set(obj, path, value):
    tokens = []
    buf = ""
    for ch in path:
        if ch == "/" and not buf:
            continue
        if ch in "/[":
            if buf:
                tokens.append(buf)
                buf = ""
            if ch == "[":
                tokens.append("[")
            continue
        if ch == "]":
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append("]")
            continue
        buf += ch
    if buf:
        tokens.append(buf)

    cur = obj
    idx = 0
    while idx < len(tokens):
        tok = tokens[idx]
        if tok == "[":
            n = int(tokens[idx + 1])
            if idx + 2 == len(tokens):
                cur[n] = value
                return
            cur = cur[n]
            idx += 3
            continue
        if idx + 1 < len(tokens) and tokens[idx + 1] == "[":
            cur = cur[tok]
            idx += 1
            continue
        if idx == len(tokens) - 1:
            cur[tok] = value
            return
        cur = cur[tok]
        idx += 1


def flip(name, old):
    """A different value that is still the right shape."""
    if isinstance(old, bool):
        return not old
    if isinstance(old, int):
        return old + 1
    if old is None:
        return "altered"
    text = str(old)
    if len(text) == 64 and all(c in "0123456789abcdef" for c in text):
        return ("0" if text[0] != "0" else "1") + text[1:]
    if len(text) == 36 and text.count("-") == 4:
        return ("0" if text[0] != "0" else "1") + text[1:]
    return text + "-altered"


def _results(pkg):
    verdict = verify(pkg)
    return verdict, {c["id"]: c["result"] for c in verdict["checks"]}


def probe():
    """Returns (baseline, per-field changes). A change is any check whose
    result moved, in either direction, not only a FAIL: a field that turns
    PASS into INCONCLUSIVE was noticed too, and calling it 'unprotected' would
    be wrong."""
    tmp0 = tempfile.mkdtemp()
    try:
        base_pkg = os.path.join(tmp0, "pkg")
        shutil.copytree(BASE, base_pkg)
        base_verdict, base = _results(base_pkg)
    finally:
        shutil.rmtree(tmp0, ignore_errors=True)

    results = []
    for rel in JSON_FILES:
        path = os.path.join(BASE, rel)
        if not os.path.exists(path):
            continue
        doc = json.load(open(path, encoding="utf-8"))
        for leaf, value in list(leaves(doc)):
            tmp = tempfile.mkdtemp()
            try:
                pkg = os.path.join(tmp, "pkg")
                shutil.copytree(BASE, pkg)
                new = copy.deepcopy(doc)
                _set(new, leaf, flip(leaf, value))
                json.dump(new, open(os.path.join(pkg, rel), "w", encoding="utf-8"),
                          ensure_ascii=False)
                try:
                    verdict, after = _results(pkg)
                    moved = {cid: (base.get(cid), res) for cid, res in after.items()
                             if base.get(cid) != res}
                    fails = sorted(cid for cid, pair in moved.items()
                                   if pair[1] == "FAIL")
                    outcome = verdict.get("result")
                except Exception as e:  # noqa: BLE001
                    moved, fails, outcome = {}, ["<raised %s>" % type(e).__name__], "raised"
                results.append({"field": rel + leaf, "changed_to": flip(leaf, value),
                                "verdict": outcome, "fails": fails,
                                "moved": {k: list(v) for k, v in moved.items()}})
            finally:
                shutil.rmtree(tmp, ignore_errors=True)
    return (base_verdict, base), results


def main():
    as_json = "--json" in sys.argv
    (base_verdict, base), results = probe()
    if as_json:
        json.dump(results, sys.stdout, indent=2, ensure_ascii=False)
        print()
        return 0

    silent = [r for r in results if not r["moved"]]
    print("baseline verdict: %s (%d of %d checks PASS)"
          % (base_verdict.get("result"),
             sum(1 for v in base.values() if v == "PASS"), len(base)))
    print("fields changed: %d" % len(results))
    print("field alterations that moved no check, in either direction: %d\n"
          % len(silent))
    print("| field | changed to | any check moved | checks that said FAIL |")
    print("|---|---|---|---|")
    for r in results:
        moved = ", ".join("%s %s->%s" % (cid, p[0], p[1])
                          for cid, p in sorted(r["moved"].items()))
        print("| `%s` | `%s` | %s | %s |"
              % (r["field"], str(r["changed_to"])[:40], moved or "**nothing**",
                 ", ".join(r["fails"]) or "-"))
    print()
    if silent:
        print("Silent alterations:")
        for r in silent:
            print("  " + r["field"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
