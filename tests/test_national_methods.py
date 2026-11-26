"""Offline tests for the national-methods snapshot and its checker.

The snapshot is a record of what the registry says. These tests pin the properties
that make it worth citing: the subset is fixed and named, an empty VDR stays empty,
and the file says what it does not prove.
"""
import json, os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import tools.national_methods_snapshot as snap


def _load():
    return json.load(open(snap.OUT, encoding="utf-8"))


def test_snapshot_has_the_eight_named_methods():
    d = _load()
    assert [e["method"] for e in d["national_related"]] == snap.CANDIDATES == [
        "cn", "bid", "cndid", "ioa", "ctid", "kr", "andorra", "pki"]


def test_snapshot_records_a_registry_total_above_two_hundred():
    assert _load()["total_methods"] >= 200


def test_ctid_vdr_stays_empty_and_spec_owner_is_a_user_account():
    for e in _load()["national_related"]:
        if e["method"] == "ctid":
            assert e["vdr"] in ("", None)
            assert e["spec_owner_kind"] == "personal-account"


def test_every_entry_carries_owner_kind_not_a_url_guess():
    for e in _load()["national_related"]:
        assert e["spec_owner_kind"] in ("personal-account", "org-account", "gitlab-host", "unknown")


def test_snapshot_says_what_it_does_not_prove():
    assert "not proof" in _load()["reading"]


def test_checker_passes_on_the_committed_snapshot():
    assert snap.check() == 0
