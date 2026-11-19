"""Oracle check: expectations are written down before anything is run.

The difference from `independent_verifier/cross_check.py` is the direction of trust.
Cross-check asks "do two implementations agree?" - which cannot rule out both being wrong
the same way. This asks "does each implementation match a verdict that was written down
from the specification?" - so a shared misreading now fails here even when the two agree.

The table below is derived from `fixtures/EXPECTED.md` (the hand-derived prior) and from
`benchmarks.md` line on `duplicated` (S5 root mismatch). It was written before the runs;
changing it after seeing an output is the exact failure this tool exists to prevent.

Run:  python tools/oracle_check.py
Exit: 0 = both implementations match the oracle, 1 = at least one cell differs.
"""

import json
import os
import shutil
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "independent_verifier"))

from uibc_core.verify import verify                      # noqa: E402
from uibc_core import cli as ucli                        # noqa: E402
from uibc_core.signing import generate_key               # noqa: E402
from iverify import independent_verify                   # noqa: E402

V_TO_S = {"V1": "S1", "V2": "S2", "V3": "S3", "V4": "S4", "V5": "S5", "V6": "S6"}

# case name, mutation, expected top-level verdict, expected FIRST failing check in strict mode
ORACLE = [
    ("oracle-clean",      "none",      "PASS", None),
    ("oracle-tampered",   "tamper",    "FAIL", "S4"),
    ("oracle-deleted",    "delete",    "FAIL", "S4"),
    ("oracle-duplicated", "duplicate", "FAIL", "S5"),
    ("oracle-unsealed",   "unseal",    "FAIL", "S6"),
]


def build(tmp, name, mutation):
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "oracle", "owner": "oracle",
        "agent_type": "software-agent", "version": "1"})())
    src = os.path.join(tmp, f"{name}.txt")
    with open(src, "w", encoding="utf-8") as f:
        f.write(f"oracle {name}\n")
    ucli.cmd_evidence(type("A", (), {
        "path": pkg, "type": "ACTION", "file": src,
        "media_type": "text/plain", "note": "n1"})())
    key = generate_key()
    kf = os.path.join(tmp, f"{name}.key")
    with open(kf, "w", encoding="ascii") as f:
        f.write(key.hex())
    ucli.cmd_submit(type("A", (), {"path": pkg, "key": kf})())
    mutate(pkg, name, mutation)
    return pkg, key


def mutate(pkg, name, mutation):
    idx_path = os.path.join(pkg, "evidence", "index.json")
    if mutation == "none":
        return
    if mutation == "tamper":
        with open(os.path.join(pkg, "evidence", "files", f"{name}.txt"), "a", encoding="utf-8") as f:
            f.write("TAMPERED\n")
        return
    if mutation == "delete":
        os.remove(os.path.join(pkg, "evidence", "files", f"{name}.txt"))
        return
    if mutation == "duplicate":
        idx = json.load(open(idx_path, encoding="utf-8"))
        idx["entries"].append(dict(idx["entries"][0]))
        with open(idx_path, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2, sort_keys=True)
        return
    if mutation == "unseal":
        # EXPECTED.md: strict mode, unsigned package FAILs at S6.
        seal = os.path.join(pkg, "signatures", "seal.json")
        if os.path.exists(seal):
            os.remove(seal)
        return
    raise ValueError(mutation)


def first_fail(checks):
    """First failing check in CHECK-NUMBER order, not in report order.

    The report is not printed in S order (measured: S11, S1, S2, S3, S4, S12, S7, S8,
    S5, S6 on a duplicated package), so "first failure" is undefined unless the ordering
    rule is fixed. This tool fixes it: lowest check number that fails.
    """
    def num(cid):
        digits = "".join(ch for ch in cid if ch.isdigit())
        return int(digits) if digits else 10 ** 6

    failing = [c["id"] for c in checks if c["result"] == "FAIL"]
    return min(failing, key=num) if failing else None


def ref_view(pkg, key):
    rep = verify(pkg, key=key)
    return rep["result"], first_fail(rep["checks"])


def ind_view(pkg, key):
    out = independent_verify(pkg, key=key)
    checks = [{"id": V_TO_S.get(k, k), "result": v} for k, v in out["checks"].items()]
    checks.sort(key=lambda c: c["id"])
    return out["result"], first_fail(checks)


def main():
    rows, bad = [], 0
    with tempfile.TemporaryDirectory() as tmp:
        for name, mutation, want_verdict, want_first in ORACLE:
            pkg, key = build(tmp, name, mutation)
            r_verdict, r_first = ref_view(pkg, key)
            i_verdict, i_first = ind_view(pkg, key)
            r_ok = (r_verdict == want_verdict and r_first == want_first)
            i_ok = (i_verdict == want_verdict and i_first == want_first)
            bad += 0 if (r_ok and i_ok) else 1
            rows.append((name, want_verdict, str(want_first), r_verdict, str(r_first),
                         i_verdict, str(i_first), r_ok, i_ok))

    print(f"{'case':<20}{'oracle':<8}{'o-first':<9}{'ref':<8}{'r-first':<9}"
          f"{'ind':<8}{'i-first':<9}{'ref?':<6}{'ind?'}")
    for name, ov, of, rv, rf, iv, iff, rok, iok in rows:
        print(f"{name:<20}{ov:<8}{of:<9}{rv:<8}{rf:<9}{iv:<8}{iff:<9}"
              f"{'OK' if rok else 'DIFF':<6}{'OK' if iok else 'DIFF'}")

    print(f"\ncases: {len(rows)}, cells disagreeing with the oracle: {bad}")
    print("ORACLE: " + ("PASS - both implementations match the written expectations"
                        if bad == 0 else "FAIL - an implementation disagrees with the oracle"))
    return 0 if bad == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
