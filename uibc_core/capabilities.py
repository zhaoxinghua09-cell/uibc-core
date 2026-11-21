"""Capability declaration, and the difference between "we disagree" and "we are not comparable".

The problem this exists for. When two verifiers look at the same package and
produce different verdicts, the comparison report today can only say one thing:
someone is wrong. That is not always true, and the false accusation is the
expensive half of the mistake:

    A says FAIL on S11. B does not implement S11 at all, so B says PASS.

B is not lying and A is not broken. They are not comparable on that check.
Without a declaration there is no way to tell that case apart from "B has
S11, S11 says PASS, and one of them is wrong" - which is a real defect.

So: each implementation publishes what it can do (a declaration), and a
comparison is made between declarations before it is made between verdicts.

    checks in both declarations -> comparable; a disagreement there is a DEFECT
    check in one declaration  -> CAPABILITY GAP; a disagreement there is ATTRIBUTED
    check in neither vocabulary -> UNKNOWN; the comparison assumes a shared spec

Three honest limits, stated rather than implied:

  1. A declaration is a claim. Nothing here checks that a verifier which
     declares S11 actually implements S11 - that direction is the conformance
     suite's job, not this module's.
  2. Attribution works at declaration level: it explains a per-check difference
     where one side is silent because it never looked. It cannot explain two
     verdicts that differ on a check both declarations carry.
  3. Everything here is PROPOSAL until a second implementation publishes a
     declaration against the same schema.

Machine-readable output is ASCII only (failure_corpus F-010: CJK in the JSON
broke cp936 pipes), and contains no absolute paths (F-011: two runs of one
package must emit identical bytes).
"""

import hashlib
import json

from . import SPEC_VERSION, VERIFIER_ID, __version__  # noqa: F401
from . import basis as _basis

__all__ = [
    "DECLARATION_NAME",
    "DISPOSITIONS",
    "REPORT_FIELDS",
    "declaration",
    "digest",
    "compare",
    "classify_check",
    "check_declaration",
]

DECLARATION_NAME = "capabilities.json"

# What this verifier can say about a package. A closed set on purpose: a new
# verdict has to be added to the spec before it can be declared.
DISPOSITIONS = ("PASS", "FAIL", "INCONCLUSIVE")

# The fields each per-check entry carries in the report. Added in 0.5.0;
# a verifier from an earlier version genuinely cannot produce them, and the
# comparison should say exactly that instead of calling the difference a bug.
REPORT_FIELDS = ("basis", "evidence", "reproduce", "remediation", "limitations")

_ATTRIBUTION = ("SHARED", "CAPABILITY_GAP_A", "CAPABILITY_GAP_B", "UNKNOWN")


def _canonical(obj) -> bytes:
    """JCS-style: sorted keys, no whitespace, ASCII only."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True).encode("utf-8")


def digest(payload: dict) -> str:
    """sha256 over the declaration minus its own digest field."""
    core = {k: v for k, v in payload.items() if k != "digest"}
    return "sha256:" + hashlib.sha256(_canonical(core)).hexdigest()


def declaration(checks=None, dispositions=None, fields=None, verifier=None,
                spec_version=None) -> dict:
    """Build a declaration for this implementation, or a described one.

    Every argument defaults to what this tree actually has, measured from
    basis.BASIS rather than typed out here: a hand-written list of check ids
    is a claim that decays the moment a check is added.
    """
    checks = sorted(_basis.BASIS if checks is None else list(checks))
    dispositions = sorted(DISPOSITIONS if dispositions is None else list(dispositions))
    fields = sorted(REPORT_FIELDS if fields is None else list(fields))
    body = {
        "declaration_version": "1",
        "verifier": verifier or ("%s %s" % (VERIFIER_ID, __version__)),
        "spec_version": spec_version if spec_version is not None else SPEC_VERSION,
        "checks": checks,
        "dispositions": dispositions,
        "fields": fields,
    }
    body["digest"] = digest(body)
    return body


def check_declaration(decl) -> list:
    """Return a list of schema problems (empty when the declaration is usable).

    A declaration that cannot be read is not a capability gap: it is a broken
    input, and treating it as a gap would let a malformed file excuse a real
    disagreement.
    """
    problems = []
    if not isinstance(decl, dict):
        return [{"code": "NOT_AN_OBJECT", "detail": "declaration must be a JSON object"}]
    for key, kind in (("verifier", str), ("spec_version", str),
                      ("checks", list), ("dispositions", list), ("fields", list)):
        if key not in decl:
            problems.append({"code": "MISSING_FIELD", "detail": key})
        elif not isinstance(decl[key], kind):
            problems.append({"code": "WRONG_TYPE", "detail": key})
    if problems:
        return problems
    if not decl["checks"]:
        problems.append({"code": "NO_CHECKS", "detail": "a verifier that checks nothing cannot be compared"})
    for c in decl["checks"]:
        if not isinstance(c, str) or not c:
            problems.append({"code": "BAD_CHECK_ID", "detail": repr(c)})
    for d in decl["dispositions"]:
        if d not in DISPOSITIONS:
            problems.append({"code": "UNKNOWN_DISPOSITION", "detail": str(d)})
    if "digest" in decl:
        if digest(decl) != decl["digest"]:
            problems.append({"code": "DIGEST_MISMATCH",
                             "detail": "declaration changed after it was digested"})
    return problems


def classify_check(check_id: str, a: dict, b: dict) -> str:
    """Where does this check live: both sides, one side, or neither vocabulary.

    Returns one of SHARED / CAPABILITY_GAP_A / CAPABILITY_GAP_B / UNKNOWN.
    "GAP_A" means B alone lacks it: a difference on this check is attributable
    to B being silent, and is not evidence that either implementation is wrong.
    """
    in_a = check_id in set(a.get("checks") or ())
    in_b = check_id in set(b.get("checks") or ())
    if in_a and in_b:
        return "SHARED"
    if in_a:
        return "CAPABILITY_GAP_B"
    if in_b:
        return "CAPABILITY_GAP_A"
    return "UNKNOWN"


def compare(a: dict, b: dict) -> dict:
    """Compare two declarations.

    The return value separates three things that a single boolean would blur:

        attributable  differences explained by one side not implementing a rule
        defects       schema problems, or a check neither side's vocabulary
                      contains - a disagreement here cannot be excused
        compatible    True only when the two can be compared check by check
                      without leaving anything unexplained
    """
    result = {
        "comparable": False,
        "compatible": False,
        "shared_checks": [],
        "only_in_a": [],
        "only_in_b": [],
        "capability_gaps": [],
        "defects": [],
        "notes": [],
    }
    for side, decl in (("A", a), ("B", b)):
        for p in check_declaration(decl):
            result["defects"].append({"side": side, "detail": p})

    if result["defects"]:
        return result

    ca, cb = sorted(set(a["checks"])), sorted(set(b["checks"]))
    shared = sorted(set(ca) & set(cb))
    only_a = sorted(set(ca) - set(cb))
    only_b = sorted(set(cb) - set(ca))
    result["shared_checks"] = shared
    result["only_in_a"] = only_a
    result["only_in_b"] = only_b

    known = set(_basis.BASIS)
    for cid in only_a + only_b:
        side = "A" if cid in only_a else "B"
        if cid in known:
            result["capability_gaps"].append({
                "check": cid, "absent_from": "B" if side == "A" else "A",
                "kind": "CHECK",
                "attributed_to": "declaration, not defect",
            })
        else:
            result["defects"].append({
                "side": side, "detail": {"code": "UNKNOWN_CHECK", "detail": cid},
            })

    for side, decl in (("A", a), ("B", b)):
        missing = sorted(set(DISPOSITIONS) - set(decl["dispositions"]))
        for d in missing:
            result["capability_gaps"].append({
                "check": None, "absent_from": side,
                "kind": "DISPOSITION", "name": d,
                "attributed_to": "declaration, not defect",
            })
        for f in sorted(set(REPORT_FIELDS) - set(decl["fields"])):
            result["capability_gaps"].append({
                "check": None, "absent_from": side,
                "kind": "FIELD", "name": f,
                "attributed_to": "declaration, not defect",
            })

    if a["spec_version"] != b["spec_version"]:
        result["defects"].append({
            "side": "both",
            "detail": {"code": "SPEC_VERSION_DIFFERS",
                       "detail": "%s vs %s" % (a["spec_version"], b["spec_version"])},
        })

    result["comparable"] = bool(shared) and not result["defects"]
    result["compatible"] = bool(result["comparable"] and not result["capability_gaps"])
    if result["capability_gaps"] and result["comparable"]:
        result["notes"].append(
            "%d difference(s) attributed to the declaration; verdicts on "
            "unshared checks are not disagreements" % len(result["capability_gaps"]))
    return result
