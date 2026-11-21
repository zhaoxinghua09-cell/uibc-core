#!/usr/bin/env python3
"""Emit and compare UIBC capability declarations.

    python tools/capabilities_check.py emit                 # this tree
    python tools/capabilities_check.py emit --out capabilities.json
    python tools/capabilities_check.py compare a.json b.json
    python tools/capabilities_check.py selftest

Output is ASCII JSON, no absolute paths, so two runs on two machines compare
cleanly (failure_corpus F-010 / F-011).

Exit codes: 0 compared cleanly, 1 defects found, 2 usage/read error.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import capabilities  # noqa: E402


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _dump(obj):
    return json.dumps(obj, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def cmd_emit(argv):
    out = None
    if argv and argv[0] == "--out":
        if len(argv) < 2:
            print("emit --out needs a path", file=sys.stderr)
            return 2
        out = argv[1]
    decl = capabilities.declaration()
    text = _dump(decl)
    if out:
        with open(out, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print("wrote %s (%d checks)" % (out, len(decl["checks"])))
    else:
        sys.stdout.write(text)
    return 0


def _summary(cmp_result):
    lines = []
    lines.append("shared checks      : %d" % len(cmp_result["shared_checks"]))
    lines.append("only in A          : %s" % (", ".join(cmp_result["only_in_a"]) or "-"))
    lines.append("only in B          : %s" % (", ".join(cmp_result["only_in_b"]) or "-"))
    gaps = cmp_result["capability_gaps"]
    lines.append("capability gaps    : %d" % len(gaps))
    for g in gaps:
        if g["kind"] == "CHECK":
            lines.append("  - %s absent from %s" % (g["check"], g["absent_from"]))
        else:
            lines.append("  - %s %s absent from %s" % (g["kind"], g["name"], g["absent_from"]))
    lines.append("defects            : %d" % len(cmp_result["defects"]))
    for d in cmp_result["defects"]:
        lines.append("  - %s: %s" % (d["side"], d["detail"]))
    lines.append("comparable         : %s" % cmp_result["comparable"])
    lines.append("compatible         : %s" % cmp_result["compatible"])
    for n in cmp_result["notes"]:
        lines.append("note               : %s" % n)
    return "\n".join(lines)


def cmd_compare(argv):
    if len(argv) < 2:
        print("compare needs two declaration paths", file=sys.stderr)
        return 2
    try:
        a, b = _read(argv[0]), _read(argv[1])
    except (OSError, ValueError) as e:
        print("cannot read declaration: %s" % e, file=sys.stderr)
        return 2
    cmp_result = capabilities.compare(a, b)
    print(_summary(cmp_result))
    return 0 if not cmp_result["defects"] else 1


def cmd_selftest(_argv):
    """A demonstration with its own answers, so the tool is checkable by hand."""
    ok = capabilities.declaration()
    minimal = capabilities.declaration(checks=["S0", "S4", "S6"],
                                       dispositions=["PASS", "FAIL"],
                                       fields=["basis"],
                                       verifier="demo 0.3.0")
    cases = []
    r_same = capabilities.compare(ok, dict(ok))
    cases.append(("identical declarations", r_same["compatible"] and not r_same["defects"]))
    r_gap = capabilities.compare(ok, minimal)
    cases.append(("weak declaration is a gap, not a defect",
                  bool(r_gap["capability_gaps"]) and not r_gap["defects"] and r_gap["comparable"]))
    cases.append(("gap is attributed to B",
                  all(g["absent_from"] == "B" for g in r_gap["capability_gaps"])))
    broken = dict(minimal)
    broken["digest"] = "sha256:" + "0" * 64
    cases.append(("tampered digest is a defect", bool(capabilities.compare(ok, broken)["defects"])))
    alien = capabilities.declaration(checks=["S0", "X99"], verifier="alien 1.0")
    cases.append(("vocabulary neither side knows is a defect",
                  any(d["detail"]["code"] == "UNKNOWN_CHECK" for d in capabilities.compare(ok, alien)["defects"])))
    cases.append(("classify: shared", capabilities.classify_check("S6", ok, ok) == "SHARED"))
    cases.append(("classify: b is silent", capabilities.classify_check("S11", ok, minimal) == "CAPABILITY_GAP_B"))
    failed = [name for name, passed in cases if not passed]
    for name, passed in cases:
        print("%-48s %s" % (name, "ok" if passed else "FAILED"))
    if failed:
        print("\n%d of %d failed" % (len(failed), len(cases)))
        return 1
    print("\n%d/%d ok" % (len(cases), len(cases)))
    return 0


USAGE = __doc__


def main(argv):
    if not argv:
        print(USAGE)
        return 2
    cmd, rest = argv[0], argv[1:]
    if cmd == "emit":
        return cmd_emit(rest)
    if cmd == "compare":
        return cmd_compare(rest)
    if cmd == "selftest":
        return cmd_selftest(rest)
    print(USAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
