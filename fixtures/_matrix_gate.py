"""Shared expectation-matrix gate for the UIBC benchmark fixtures.

Both fixture generators follow one discipline:

    the Expected column is a PRIOR, derived by hand from the verifier's control
    flow BEFORE being compared with observed output, and the run FAILS with a
    non-zero exit code the moment observed disagrees.

Prose cannot fail; a matrix can. Keeping the comparison in one place means the
two generators cannot drift apart, and means "the gate is enforced" is a single
claim to test rather than one per generator.
"""


def observed_cell(report: dict) -> dict:
    """Project a verifier report onto the matrix-cell shape."""
    return {"result": report["result"],
            "checks": {c["id"]: c["result"] for c in report["checks"]}}


def compare(expected: dict, observed: dict, fixtures, modes, extra_keys=()) -> list:
    """Return every deviation between the prior and the observations.

    Empty list == the prior holds. Comparison covers:
      - the overall verdict
      - every check id named by the prior (a check missing from the observation
        is reported as <absent>, never skipped)
      - checks present in the observation but NOT in the prior, so a verifier
        that grows a new check silently does not pass unnoticed
      - any `extra_keys` (e.g. a result_code) that the prior also pins
    """
    devs = []
    for name in fixtures:
        for mode in modes:
            exp = expected[name][mode]
            got = observed[(name, mode)]

            if exp["result"] != got["result"]:
                devs.append(f"{name}[{mode}].result  expected={exp['result']:<12} "
                            f"observed={got['result']}")

            for cid, want in exp["checks"].items():
                have = got["checks"].get(cid, "<absent>")
                if want != have:
                    devs.append(f"{name}[{mode}].{cid}       expected={want:<12} "
                                f"observed={have}")

            extra = sorted(set(got["checks"]) - set(exp["checks"]))
            if extra:
                devs.append(f"{name}[{mode}].checks  unexpected extra checks observed: {extra}")

            for k in extra_keys:
                want_k, got_k = exp.get(k), got.get(k)
                if want_k != got_k:
                    devs.append(f"{name}[{mode}].{k}       expected={want_k:<12} "
                                f"observed={got_k}")
    return devs


def render_cell(cell: dict, check_ids) -> str:
    """Compact per-check rendering, e.g. 'S1=P S2=P S3=F'."""
    return " ".join(f"{cid}={cell['checks'].get(cid, '?')[0]}" for cid in check_ids)


def gate(deviations: list, cells_checked: int, label: str = "MATRIX GATE") -> int:
    """Turn a deviation list into an exit code, printing the evidence."""
    if deviations:
        print(f"\n[{label}] {len(deviations)} deviation(s) from the hand-derived prior:")
        for d in deviations:
            print("   !! " + d)
        print(f"[{label}] FAILED - this run is NOT evidence. "
              f"Fix the verifier, or justify and amend the prior.")
        return 1
    print(f"[{label}] OK - all {cells_checked} cells match the prior.")
    return 0
