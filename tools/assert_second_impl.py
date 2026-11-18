#!/usr/bin/env python3
"""Fail the build when the second implementation drifts away from the first.

`tools/cross_impl_check.py` reports numbers; this asserts what the numbers must
mean. Until this existed, "the JavaScript verifier covers fifteen of nineteen
checks" was a sentence in a document, and nothing stopped it from quietly
becoming false the moment somebody edited `uibc_core/verify.py` without touching
`tools/verify-js/verify.mjs`.

What counts as drift, and why each is a build failure:

* a package the suite expects to ACCEPT, but which the JavaScript verifier
  rejects -- the second implementation refusing something valid is the worst
  failure mode available, because a verifier that cries wolf trains people to
  ignore it;
* a package the suite expects to REFUSE, whose JavaScript verdict names none of
  the expected checks -- failing for an unrelated reason is not coverage, it is
  coincidence;
* a package outside the declared covered set (`out_of_scope > 0`) -- a new
  check was added to the Python side and the second implementation was not
  carried with it.

It deliberately does NOT require the two implementations to produce the
identical FAIL *set*. They legitimately differ: JavaScript reported S5 as well
as S4 on a corrupted file, and both are true statements about that package.
Requiring set equality would force one implementation to under-report to match
the other, which is the opposite of what a cross-check is for.

Exit codes: 0 nothing drifted, 1 drift, 2 cannot run (no node / no cases).
"""

import json
import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(REPO, "tools"))

import cross_impl_check as cic  # noqa: E402


def ensure_cases():
    """The suite ships as a zip; cases/ is not in the repository."""
    cases = os.path.join(REPO, "conformance", "cases")
    if os.path.isdir(cases) and os.listdir(cases):
        return True
    print("conformance/cases is absent; exporting the suite first")
    r = subprocess.run([sys.executable, os.path.join(REPO, "tools", "export_conformance.py")],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stdout[-2000:])
        print(r.stderr[-2000:])
        return False
    return True


def main():
    if not cic.shutil.which("node"):
        print("node is not installed; the second implementation cannot be checked")
        return 2
    if not ensure_cases():
        return 2

    man = json.load(open(cic.MANIFEST, encoding="utf-8"))
    problems = []
    checked = 0

    for case in man["cases"]:
        pkg = os.path.join(REPO, "conformance", case["path"])
        js = cic.run_js(pkg)
        if js is None:
            problems.append("case %s: the JavaScript verifier produced no report" % case["id"])
            continue
        js_fail = cic.failed_ids(js)
        expected = set(case.get("expected_checks") or [])
        checked += 1

        if case.get("expect") == "accept":
            if js_fail:
                problems.append(
                    "case %s (%s): expected to be accepted, JavaScript rejected it "
                    "for %s" % (case["id"], case["attack"], ", ".join(sorted(js_fail))))
            continue

        named = js_fail & expected
        if not named:
            problems.append(
                "case %s (%s): expected one of %s, JavaScript reported %s -- a "
                "failure for another reason is not coverage"
                % (case["id"], case["attack"], ", ".join(sorted(expected)),
                   ", ".join(sorted(js_fail)) or "nothing"))

    in_scope = [c for c in man["cases"]
                if c.get("expect") == "accept"
                or (set(c.get("expected_checks") or []) & set(cic.COVERED))]
    out_of_scope = [c for c in man["cases"] if c not in in_scope]
    for case in out_of_scope:
        problems.append(
            "case %s (%s) expects %s, which the second implementation does not "
            "claim to cover; add it to COVERED only when the checker really "
            "implements it" % (case["id"], case["attack"],
                               ", ".join(sorted(set(case.get("expected_checks") or []))))
        )

    if problems:
        print("second implementation drifted: %d problem(s) across %d cases"
              % (len(problems), len(man["cases"])))
        for p in problems:
            print("  " + p)
        return 1

    print("second implementation agrees on %d/%d packages: every accepted package "
          "is accepted, every refused package names an expected check, %d check(s) "
          "covered, 0 out of scope"
          % (checked, len(man["cases"]), len(cic.COVERED)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
