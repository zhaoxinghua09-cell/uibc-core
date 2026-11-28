"""Section 7's five verdicts must be a total, checked partition, not prose.

The failure mode being prevented: someone adds check S20, forgets to assign it,
and a package passes with an unexamined question folded into "the rest passed".
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import dimensions, verify  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO, "examples", "demo.uibc")


def _demo_checks():
    return verify.verify(DEMO)["checks"]


def test_every_dimension_is_named_in_the_draft_order():
    assert dimensions.ORDER == ["signature", "authority", "binding", "status", "evidence"]
    for d in dimensions.ORDER:
        assert d in dimensions.DIMENSIONS, d


def test_the_partition_has_no_overlap():
    seen = {}
    for d, ids in dimensions.DIMENSIONS.items():
        for i in ids:
            assert i not in seen, "%s appears in both %s and %s" % (i, seen.get(i), d)
            seen[i] = d
    assert set(seen) == set("S%d" % n for n in range(1, 20)), "partition must cover S1..S19 exactly"


def test_every_check_the_verifier_emits_lands_in_a_dimension():
    checks = _demo_checks()
    dims = dimensions.record(checks)
    assert "_unassigned" not in dims, dims.get("_unassigned")


def test_one_failure_refuses_only_its_own_dimension():
    fake = [{"id": "S%d" % n, "result": "PASS"} for n in range(1, 20)]
    fake[5]["result"] = "FAIL"                      # S6, the seal
    dims = dimensions.record(fake)
    assert dims["signature"]["verdict"] == dimensions.REFUSED
    for d in ("authority", "binding", "status", "evidence"):
        assert dims[d]["verdict"] == dimensions.CHECKED_PASS, d


def test_a_skipped_member_is_not_a_pass():
    fake = [{"id": "S%d" % n, "result": "PASS"} for n in range(1, 20)]
    fake[15]["result"] = "INCONCLUSIVE"             # S16, the timestamp
    dims = dimensions.record(fake)
    assert dims["evidence"]["verdict"] == dimensions.NOT_CHECKED
    assert dimensions.aggregate(dims) == dimensions.EXPORT_REFUSED


def test_all_five_checked_is_the_only_way_to_exportable():
    fake = [{"id": "S%d" % n, "result": "PASS"} for n in range(1, 20)]
    dims = dimensions.record(fake)
    assert dimensions.aggregate(dims) == "EXPORTABLE"
    fake[2]["result"] = "FAIL"                      # S3
    assert dimensions.aggregate(dimensions.record(fake)) == dimensions.EXPORT_REFUSED


def test_the_shipped_demo_is_refused_not_summarised_as_fine():
    dims = dimensions.record(_demo_checks())
    assert dimensions.aggregate(dims) == dimensions.EXPORT_REFUSED
    # and it says which dimension refused, rather than one grey word
    assert any(v["verdict"] == dimensions.REFUSED for k, v in dims.items() if k != "_unassigned")
