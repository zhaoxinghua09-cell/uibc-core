"""Conformance tests against the AIC text itself, not against a crate's copy of it.

Source of the text (fetched 2026-11-24, kept verbatim in `docs/ACPS-SPEC-IN-HAND.md`):

    ACPs-community/acps-specs/02-ACPs-spec-AIC/ACPs-spec-AIC.md
    https://atomgit.com/aip-pub/ACPs-community/blob/main/acps-specs/02-ACPs-spec-AIC/ACPs-spec-AIC.md

Every fixture below is either the document's own worked example, a boundary value the
document itself states, or one deliberate mutation of a stated rule. Nothing here is
invented to make the implementation look good.
"""

import random
import string

import pytest

from uibc_core.acps_identity_code import (
    MIN_SALT_BYTES,
    acps_checksum,
    base36_fixed,
    crc16_ccitt_false,
    read_acps_code,
    verify_acps_code,
)

# §3: the document's own example, including the prefix assigned by the national OID registry
SPEC_BODY = "1.2.156.3088.1.1.34C2.478BDF.3GF546"
SPEC_CODE = SPEC_BODY + ".0JU4"
SPEC_SALT = b"\x12\x34"          # §4.1 step (2): "取 2 字节盐值 SALT = 0x1234"
SPEC_CRC = 0x646C                # §4.1 step (6): "CRC校验码原值为 0x646C"
SPEC_CHECKSUM = "0JU4"           # §4.1 step (7)
ARC10_MAX = "1EKF"               # §3 item (10): "取值范围0000～1EKF"

BASE36 = string.digits + string.ascii_uppercase


def test_spec_worked_example_crc_value():
    assert crc16_ccitt_false((SPEC_BODY + "").encode("ascii") + SPEC_SALT) == SPEC_CRC


def test_spec_worked_example_checksum():
    assert acps_checksum(SPEC_BODY, SPEC_SALT) == SPEC_CHECKSUM


def test_base36_upper_bound_matches_the_stated_range():
    # 0xFFFF is the CRC ceiling; the document caps arc 10 at 1EKF, which must be exactly this.
    assert base36_fixed(0xFFFF) == ARC10_MAX


def test_full_example_verifies_with_the_documented_salt():
    r = verify_acps_code(SPEC_CODE, SPEC_SALT)
    assert r["state"] == "VERIFIED"
    assert "0JU4" in r["detail"]
    assert "allocation unverified" in r["scope"]


def test_verified_carries_reproducible_evidence():
    r = verify_acps_code(SPEC_CODE, SPEC_SALT)
    assert r["evidence"], "VERIFIED without evidence would be a claim, not a result"
    entry = r["evidence"][0]
    assert entry["digest"].startswith("sha256:")
    assert entry["id"] == "acps-arc10:0JU4"


def test_without_a_salt_the_checksum_is_said_to_be_unchecked():
    r = verify_acps_code(SPEC_CODE)
    assert r["state"] == "INCONCLUSIVE"
    assert "NOT checked" in r["detail"]
    assert "no salt supplied" in r["scope"]


def test_wrong_checksum_is_invalid_not_inconclusive():
    r = verify_acps_code(SPEC_BODY + ".9999", SPEC_SALT)
    assert r["state"] == "INVALID"
    assert "0JU4" in r["detail"] and "9999" in r["detail"]


def test_salt_from_another_arsp_reads_as_mismatch():
    r = verify_acps_code(SPEC_CODE, b"\x34\x12")   # the documented salt, byte-swapped
    assert r["state"] == "INVALID"
    assert "different ARSP" in r["detail"]


def test_salt_shorter_than_two_bytes_is_refused():
    # §4.1 step (2): "长度不少于 2 字节"
    r = verify_acps_code(SPEC_CODE, b"\x12")
    assert r["state"] == "INCONCLUSIVE"
    assert "at least %d" % MIN_SALT_BYTES in r["detail"]


def test_salt_must_be_bytes():
    with pytest.raises(TypeError):
        acps_checksum(SPEC_BODY, "1234")


def test_lowercase_code_is_normalized_as_the_document_says():
    # §4.2 step (2): letters are upper-cased before recomputation
    r = verify_acps_code(SPEC_CODE.lower(), SPEC_SALT)
    assert r["state"] == "VERIFIED"


def test_ontology_form_is_named_when_instance_serial_is_all_zero():
    ontology = "1.2.156.3088.1.1.34C2.478BDF.000000000.0JU4"
    r = read_acps_code(ontology)
    assert r["state"] == "INCONCLUSIVE"
    assert "ontology AIC" in r["detail"]


def test_mutating_the_body_changes_the_checksum():
    # One character in arc 7 must move arc 10; this is the property a checksum exists for.
    mutated = "1.2.156.3088.1.1.34C3.478BDF.3GF546"
    assert acps_checksum(mutated, SPEC_SALT) != SPEC_CHECKSUM
    assert verify_acps_code(mutated + "." + SPEC_CHECKSUM, SPEC_SALT)["state"] == "INVALID"


def test_eight_arc_code_is_refused_before_any_checksum_talk():
    r = verify_acps_code("1.2.156.3088.1.360.360.000000001", SPEC_SALT)
    assert r["state"] == "INVALID"
    assert "different reader" in r["detail"]
    # No checksum was computed for a shape this reader does not own.
    assert r["evidence"] == []


@pytest.mark.parametrize("seed", [0, 1, 2])
def test_random_salts_round_trip(seed):
    """Self-consistency at scale: sign then verify, 60 times per seed.

    This cannot prove conformance to the text — only the worked example does that —
    but it does prove the two directions of our own arithmetic agree, and that arc 10
    stays four Base36 characters for arbitrary salts and bodies.
    """
    rng = random.Random(seed)
    for _ in range(60):
        arsp = "".join(rng.choice(BASE36) for _ in range(rng.randint(1, 6)))
        vendor = "".join(rng.choice(BASE36) for _ in range(rng.randint(1, 6)))
        onto = "".join(rng.choice(BASE36) for _ in range(rng.randint(1, 9)))
        inst = "".join(rng.choice(BASE36) for _ in range(rng.randint(1, 9)))
        body = "1.2.156.3088.1.%s.%s.%s.%s" % (arsp, vendor, onto, inst)
        salt = bytes(rng.randrange(256) for _ in range(rng.randint(2, 8)))
        checksum = acps_checksum(body, salt)
        assert len(checksum) == 4 and all(c in BASE36 for c in checksum)
        assert verify_acps_code(body + "." + checksum, salt)["state"] == "VERIFIED"
