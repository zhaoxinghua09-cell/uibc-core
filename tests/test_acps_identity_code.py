"""Tests: the ten-arc ACPs profile, read without inventing a crosswalk.

Every fixture here is either the specification's own example, the crate's own
example, or one deliberate violation of a stated rule.
"""

import pytest

from uibc_core.acps_identity_code import read_acps_code
from uibc_core.agent_identity_code import detect_profile, parse_agent_code

CRATE_EXAMPLE = "1.2.156.3088.1.0001.00001.ABC123.000001.176F"
SPEC_EXAMPLE = "1.2.156.1234.1.1.34C2.478BDF.3GF546.0H9T"
GBZ_SHAPE = "1.2.156.3088.1.360.360.000000001"


def test_crate_example_reads_as_ten_arcs():
    r = read_acps_code(CRATE_EXAMPLE)
    assert r["state"] == "INCONCLUSIVE"
    assert "ACPs-spec-AIC-v02.01" in r["method"]


def test_checksum_is_never_judged():
    r = read_acps_code(CRATE_EXAMPLE)
    assert "checksum: unverified" in r["detail"]
    assert "unverified (salt not published)" in r["scope"]


def test_spec_example_uses_its_own_prefix_and_says_so():
    r = read_acps_code(SPEC_EXAMPLE)
    assert r["state"] == "INCONCLUSIVE"
    assert "1.2.156.1234" in r["detail"]


def test_unknown_prefix_is_noted_not_refused():
    r = read_acps_code("1.2.156.9999.1.0001.00001.ABC123.000001.176F")
    assert r["state"] == "INCONCLUSIVE"
    assert "neither the default" in r["detail"]


def test_eight_arc_national_code_is_refused_with_a_reason():
    r = read_acps_code(GBZ_SHAPE)
    assert r["state"] == "INVALID"
    assert "different reader" in r["detail"]


def test_nine_arcs_refused():
    r = read_acps_code("1.2.156.3088.1.0001.00001.ABC123.000001")
    assert r["state"] == "INVALID"


@pytest.mark.parametrize("code", [
    "1.2.156.3088.1.0001.00001.ABC123.000001.176",     # checksum 3 chars
    "1.2.156.3088.1.0001.00001.ABC123.000001.176FG",   # checksum 5 chars
    "1.2.156.3088.11.0001.00001.ABC123.000001.176F",   # version 2 chars
    "1.2.156.3088.1.0001000.00001.ABC123.000001.176F", # ARSP 7 chars
    "1.2.156.3088.1.0001.00001.ABC1230000.000001.176F",# ontology 10 chars
    "1.2.156.3088.1.0001.00001.ABC123.0000000001.176F",# instance 10 chars
])
def test_length_rules_are_enforced(code):
    assert read_acps_code(code)["state"] == "INVALID"


def test_lowercase_and_whitespace_normalise():
    r = read_acps_code("  1.2.156.3088.1.0001.00001.abc123.000001.176f  ")
    assert r["state"] == "INCONCLUSIVE"
    assert r["subject"] == CRATE_EXAMPLE


def test_wrong_checksum_stays_inconclusive_because_salt_is_unknown():
    # A deliberately wrong trailer. We refuse to call it valid *or* invalid:
    # the salt a real ARSP would use is not published.
    r = read_acps_code("1.2.156.3088.1.0001.00001.ABC123.000001.9999")
    assert r["state"] == "INCONCLUSIVE"


def test_ontology_aic_is_named():
    r = read_acps_code("1.2.156.3088.1.0001.00001.ABC123.000000.176F")
    assert "ontology AIC" in r["detail"]


def test_non_string_and_empty_are_named():
    assert read_acps_code(None)["subject"] == "<NoneType>"
    assert read_acps_code("")["subject"] == "<empty>"


def test_profiles_do_not_bleed_into_each_other():
    assert detect_profile(CRATE_EXAMPLE) == "aip-acps"
    assert detect_profile(GBZ_SHAPE) == "gbz185.2"
    assert parse_agent_code(CRATE_EXAMPLE)["state"] == "INVALID"
    assert parse_agent_code(GBZ_SHAPE)["state"] == "INCONCLUSIVE"
    assert read_acps_code(GBZ_SHAPE)["state"] == "INVALID"
    assert read_acps_code(CRATE_EXAMPLE)["state"] == "INCONCLUSIVE"


def test_no_path_to_verified():
    for code in (CRATE_EXAMPLE, SPEC_EXAMPLE, GBZ_SHAPE):
        assert read_acps_code(code)["state"] != "VERIFIED"
        assert parse_agent_code(code)["state"] != "VERIFIED"
