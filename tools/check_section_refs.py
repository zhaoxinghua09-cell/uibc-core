"""Every "Section N" reference in a draft must name a heading that exists.

Why: a reviewer's cheapest test is to follow a cross-reference. Three rounds of
external review produced "phantom cross-reference" findings (a sentence citing a
strict mode that no section defined), and each cost a full re-read to confirm.
This turns that class into a machine check.

Usage:  python tools/check_section_refs.py drafts/<file>.md
Exit:   0 all references resolve; 1 at least one does not; 2 file unreadable.
"""

import argparse
import re
import sys

HEAD_TOP = re.compile(r"^##\s+(?:(\d+)\.|Appendix\s+([A-Z]))")
HEAD_SUB = re.compile(r"^###\s+(\d+\.\d+)")
REF = re.compile(r"(?:Section|Appendix)\s+(\d+(?:\.\d+)?|[A-Z])(?![\d.])")


def parse(path):
    tops, subs = set(), set()
    lines = open(path, encoding="utf-8").read().splitlines()
    for line in lines:
        m = HEAD_TOP.match(line)
        if m:
            if m.group(1):
                tops.add(m.group(1))
            else:
                subs.add(m.group(2))
            continue
        m = HEAD_SUB.match(line)
        if m:
            subs.add(m.group(1))
    return tops, subs


def check(path):
    tops, subs = parse(path)
    text = open(path, encoding="utf-8").read()
    missing = []
    for m in REF.finditer(text):
        target = m.group(1)
        if target.isdigit():
            ok = (target in tops) or (target in subs)
        else:
            ok = target in subs
        if not ok:
            line_no = text.count("\n", 0, m.start()) + 1
            missing.append((line_no, m.group(0)))
    return missing, len(tops), len(subs)


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("draft")
    a = p.parse_args(argv)
    try:
        missing, ntop, nsub = check(a.draft)
    except OSError as exc:
        print("cannot read: %s" % exc, file=sys.stderr)
        return 2
    if missing:
        print("%d unresolved reference(s) in %s" % (len(missing), a.draft))
        for line_no, ref in missing:
            print("  line %d: %s" % (line_no, ref))
        return 1
    print("all references resolve: %d top-level, %d sub-level headings" % (ntop, nsub))
    return 0


if __name__ == "__main__":
    sys.exit(main())
