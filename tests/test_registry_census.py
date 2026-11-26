"""Offline tests for the full-registry census.

The census exists so that "282 methods" stops being a number people repeat and
starts being a set of entries whose contents can be counted. These tests pin the
parts that make it citable: every method present once, counts that recompute from
the rows, the one national entry the ctid review leans on, and an explicit
statement of what the census does not prove.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tools.registry_census as rc


def _d():
    return json.load(open(rc.OUT, encoding="utf-8"))


def test_every_registry_method_appears_exactly_once():
    rows = _d()["methods"]
    names = [r["method"] for r in rows]
    assert len(names) == len(set(names))
    assert len(names) == _d()["counts"]["methods"]


def test_counts_recompute_from_the_rows():
    d = _d()
    rows, c = d["methods"], d["counts"]
    assert c["vdr_empty"] == sum(1 for r in rows if r["vdr_empty"])
    assert c["spec_on_github"] == sum(1 for r in rows if r["spec_host"] == "github")
    assert c["github_personal"] == sum(1 for r in rows if r["spec_owner_kind"] == "personal-account")
    assert c["spec_on_github"] + c["spec_other_host"] + c["no_specification"] == c["methods"]


def test_owner_kind_comes_from_the_api_not_from_url_depth():
    for r in _d()["methods"]:
        assert r["spec_owner_kind"] in (None, "personal-account", "org-account", "unknown")
        if r["spec_host"] == "none":
            assert r["spec_owner_kind"] is None


def test_ctid_is_one_of_the_empty_vdr_entries():
    d = _d()
    assert "ctid" in d["counts"]["empty_vdr_methods"]
    row = next(r for r in d["methods"] if r["method"] == "ctid")
    assert row["verifiableDataRegistry"] == ""


def test_census_and_national_subset_agree_on_specifications():
    d = _d()
    by = {r["method"]: r for r in d["methods"]}
    nat = json.load(open(rc.NATIONAL, encoding="utf-8"))
    for e in nat["national_related"]:
        assert by[e["method"]]["specification"] == (e["specification"] or "")


def test_census_says_what_it_does_not_prove():
    assert "nothing about whether a method resolves" in _d()["reading"]


def test_checker_passes_on_the_committed_census():
    assert rc.check() == 0
