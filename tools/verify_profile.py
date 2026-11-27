"""The profile's six steps, run against a package and a receipt.

    python tools/verify_profile.py examples/demo.uibc --receipt out/receipt.cose
    python tools/verify_profile.py examples/demo.uibc --selftest

`--selftest` builds a receipt from a throwaway key and shows both a pass and the
three refusals, so a reader can see the difference between "not this value" and
"not my tree" without needing a transparency service.
"""
import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import profile  # noqa: E402


def show(res: dict, as_json: bool) -> int:
    if as_json:
        print(json.dumps(res, ensure_ascii=False, indent=1))
    else:
        for s in res["steps"]:
            print("step %d %-24s %-28s %s" % (s["step"], s["name"], s["outcome"],
                                              str(s["detail"])[:120]))
        print("VERDICT:", res["verdict"])
        for n in res["notes"]:
            print("note:", n)
    return 0 if res["verdict"] in (profile.OK, profile.PARTIAL_INCLUSION_UNCHECKED) else 1


def selftest(pkg: str) -> int:
    seed = b"\x11" * 32
    root, count, agent, problems = profile.package_facts(pkg)
    if problems:
        print("package problems:", problems)
        return 1
    value = profile.registered_value(root, count, agent)
    good = profile.make_receipt(value, seed)
    print("--- a receipt for this package ---")
    show(profile.verify(pkg, good), False)
    print("\n--- same receipt, one entry's bytes changed (root moves, value does not) ---")
    other = profile.registered_value("0" * 64, count, agent)
    wrong = profile.make_receipt(other, seed)
    show(profile.verify(pkg, wrong), False)
    print("\n--- a receipt from a tree we do not implement ---")
    foreign = profile.make_receipt(value, seed, vds=9999)
    show(profile.verify(pkg, foreign), False)
    print("\n--- a receipt whose proof is missing ---")
    noproof = profile.make_receipt(value, seed, vdp=None)
    show(profile.verify(pkg, noproof), False)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("package")
    ap.add_argument("--receipt", help="COSE_Sign1 receipt file (bytes)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest(a.package)
    if not a.receipt:
        ap.error("--receipt or --selftest is required")
    return show(profile.verify(a.package, open(a.receipt, "rb").read()), a.json)


if __name__ == "__main__":
    sys.exit(main())
