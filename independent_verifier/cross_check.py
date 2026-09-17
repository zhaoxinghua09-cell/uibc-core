"""Cross-check: two independent implementations must AGREE on every fixture.

Route step 9 (Independent Verifier). Agreement = spec determinism signal.
Any disagreement is recorded as a spec bug, not a code bug.

Run:  python independent_verifier/cross_check.py
Exit: 0 = full agreement, 1 = disagreement found.
"""

import json
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, HERE)

from iverify import independent_verify                     # noqa: E402
from uibc_core.verify import verify                        # noqa: E402
from uibc_core import cli as ucli                          # noqa: E402  (harness only)
from uibc_core.signing import generate_key                 # noqa: E402  (harness only)

FIXTURES = ["clean", "tampered", "deleted", "duplicated",
            "reordered", "migrated", "malicious", "malicious-keyswap"]

# S1..S6 (reference) <-> V1..V6 (independent) semantic mapping
CHECK_MAP = {"S1": "V1", "S2": "V2", "S3": "V3", "S4": "V4", "S5": "V5", "S6": "V6"}


def reference_checks(report):
    return {c["id"]: c["result"] for c in report["checks"]}


def compare(name, pkg, key=None):
    ref = verify(pkg, key=key)
    ind = independent_verify(pkg, key=key)
    rc = reference_checks(ref)
    rows, agree = [], True
    for s, v in CHECK_MAP.items():
        r_out, i_out = rc.get(s, "-"), ind["checks"].get(v, "-")
        # SKIP/INCONCLUSIVE differences on S6/V6 in open mode are semantically
        # both "not evaluated"; normalize before comparing.
        norm = lambda x: "NE" if x in ("SKIP", "INCONCLUSIVE") else x
        match = norm(r_out) == norm(i_out)
        agree &= match
        rows.append((name, s, v, r_out, i_out, "OK" if match else "MISMATCH"))
    agree &= (ref["result"] == ind["result"])
    rows.append((name, "ALL", "ALL", ref["result"], ind["result"],
                 "OK" if ref["result"] == ind["result"] else "MISMATCH"))
    return agree, rows


def build_strict_cases(tmp):
    """Freshly built signed clean + tampered packages for strict-mode agreement."""
    def build(name, tamper):
        pkg = os.path.join(tmp, name)
        ucli.cmd_init(type("A", (), {"path": pkg})())
        ucli.cmd_register(type("A", (), {
            "path": pkg, "agent_id": "xcheck", "owner": "xcheck",
            "agent_type": "software-agent", "version": "1"})())
        src = os.path.join(tmp, f"{name}.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write(f"cross-check {name}\n")
        ucli.cmd_evidence(type("A", (), {
            "path": pkg, "type": "ACTION", "file": src,
            "media_type": "text/plain", "note": "n1"})())
        key = generate_key()
        kf = os.path.join(tmp, f"{name}.key")
        with open(kf, "w", encoding="ascii") as f:
            f.write(key.hex())
        ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
        if tamper:
            with open(os.path.join(pkg, "evidence", "files", f"{name}.txt"),
                      "a", encoding="utf-8") as f:
                f.write("TAMPERED\n")
        return pkg, key

    return [("xcheck-clean-strict",) + build("clean_s", False),
            ("xcheck-tampered-strict",) + build("tamp_s", True)]


def main():
    all_rows, all_ok = [], True
    for fx in FIXTURES:
        ok, rows = compare(f"fixture:{fx}", os.path.join(ROOT, "fixtures", f"{fx}.uibc"))
        all_ok &= ok
        all_rows.extend(rows)
    import tempfile as tf
    with tf.TemporaryDirectory() as tmp:
        for name, pkg, key in build_strict_cases(tmp):
            ok, rows = compare(name, pkg, key=key)
            all_ok &= ok
            all_rows.extend(rows)

    print(f"{'case':<28}{'ref':<5}{'ind':<5}{'ref result':<12}{'ind result':<12}{'verdict'}")
    for name, s, v, r_out, i_out, verdict in all_rows:
        if s == "ALL":
            print(f"{name:<28}{s:<5}{v:<5}{r_out:<12}{i_out:<12}{verdict}")
        elif verdict == "MISMATCH":
            print(f"{name:<28}{s:<5}{v:<5}{r_out:<12}{i_out:<12}{verdict}")

    mismatches = [r for r in all_rows if r[5] == "MISMATCH"]
    print(f"\nchecks compared: {len(all_rows)}, mismatches: {len(mismatches)}")
    print("AGREEMENT: " + ("PASS - spec determinism holds" if all_ok else "FAIL - SPEC BUG"))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
