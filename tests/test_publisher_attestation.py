"""A publisher can identify itself without rewriting a frozen page.

v0.4.1 carries UNSIGNED.txt and is frozen; re-signing it would rewrite the bytes its
pin, its receipt and two invitation letters quote. That leaves "nothing identifies the
publisher", which is true but not a resting place.

So the signature lives in the repository: the release key signs the digest list the
page served, the served bytes are committed beside it, and the checker prefers that
when the page carries no signature of its own.
"""
import io
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import anchor_release_digests as ard  # noqa: E402
import check_release_anchors as cra  # noqa: E402

ATT = os.path.join(ROOT, "anchors", "attestations", "v0.4.1")
DIGESTS = os.path.join(ATT, "CORPUS-DIGESTS.txt")
SIG = os.path.join(ATT, "CORPUS-DIGESTS.txt.sig")
ATTESTATION = os.path.join(ATT, "ATTESTATION.json")


def test_the_frozen_digest_is_committed_with_its_signature():
    assert os.path.isfile(DIGESTS), "the signed bytes must be here, or the signature " \
                                    "cannot be checked without the network"
    assert os.path.isfile(SIG)
    assert os.path.isfile(ATTESTATION)
    blob = json.load(io.open(ATTESTATION, encoding="utf-8"))
    assert blob["kind"] == "uibc-publisher-attestation-v0"
    assert blob["attests"]["sha256"] == "153f9b898878aaa9da97c7a496dd22af124d9bb3112ec5fede0a04eff94df033"
    assert blob["attests"]["bytes"] == 287
    assert blob["key_id"] == "179c615aef27cbcd"


def test_the_attestation_verifies_offline_against_the_committed_bytes():
    assert ard.verify_file(SIG, DIGESTS) == []


def test_the_attestation_names_the_key_the_repository_records():
    sidecar = json.load(io.open(SIG, encoding="utf-8"))
    pinned = json.load(io.open(os.path.join(ROOT, "anchors", "release-signing-key.json"),
                               encoding="utf-8"))
    assert sidecar["key_id"] == pinned["key_id"]


def test_verify_speaks_json_so_another_check_can_read_it():
    """`verify` used to print prose only, so a caller parsing JSON saw nothing and
    read success as failure. Measured 2026-11-20: the first run of the signature
    branch reported "does not verify" for a signature that had just verified."""
    proc = subprocess.run([sys.executable, os.path.join(ROOT, "tools",
                                                       "anchor_release_digests.py"),
                           "verify", "--sig", SIG, "--file", DIGESTS, "--json"],
                          capture_output=True, text=True, timeout=90)
    assert proc.returncode == 0, proc.stdout + proc.stderr
    blob = json.loads(proc.stdout)
    assert blob["verified"] is True
    assert blob["problems"] == []
    assert blob["key_id"] == "179c615aef27cbcd"


def test_a_tampered_digest_list_is_a_reason():
    blob = json.load(io.open(SIG, encoding="utf-8"))
    tmp = os.path.join(os.environ.get("TEMP", "/tmp"), "tampered_digests.txt")
    io.open(tmp, "w", encoding="utf-8", newline="\n").write(
        io.open(DIGESTS, encoding="utf-8").read() + "0000  extra\n")
    reasons = ard.verify_file(SIG, tmp)
    assert reasons
    assert any("no longer hashes" in r for r in reasons)
    assert blob["file_sha256"] != __import__("hashlib").sha256(
        open(tmp, "rb").read()).hexdigest()


def test_checker_uses_the_repository_signature_when_the_page_has_none():
    code, out = cra._verify_sig(SIG, DIGESTS)
    assert code == 0, out
    blob = cra._json_block(out)
    assert blob and blob["verified"] is True


# --- when, not only who -----------------------------------------------------------

TSR = os.path.join(ATT, "anchor_freetsa.tsr")
CA = os.path.join(ATT, "anchor_freetsa_ca.pem")


def test_the_signature_carries_a_third_party_timestamp():
    """The attestation says "signed after publication". Without a token that is a
    sentence written by the same party that benefits from it."""
    assert os.path.isfile(TSR) and os.path.isfile(CA)
    code, out = cra._verify_token(TSR, SIG, CA)
    assert code == 0, out
    blob = cra._json_block(out)
    assert blob["verified"] is True
    assert blob["info"]["gen_time"] == "2026-11-20T07:00:46+00:00"
    assert blob["info"]["serial"] == "172106544"


def test_the_recorded_time_is_the_time_the_token_says():
    recorded = json.load(io.open(ATTESTATION, encoding="utf-8"))[
        "timestamp_on_the_signature"]
    code, out = cra._verify_token(TSR, SIG, CA)
    blob = json.loads(out[out.index("{"):])
    assert recorded["gen_time"] == blob["info"]["gen_time"]
    assert recorded["serial"] == str(blob["info"]["serial"])
    assert recorded["digest_hex"] == blob["info"]["digest_hex"]


def test_the_signature_comes_after_the_freeze_not_before():
    pin = json.load(io.open(os.path.join(ROOT, "anchors", "pins",
                                       "uibc-release-v0.4.1.json"), encoding="utf-8"))
    assert not cra._before_freeze("2026-11-20T07:00:46+00:00", pin["frozen_at"])


def test_a_time_before_the_freeze_is_flagged():
    pin = json.load(io.open(os.path.join(ROOT, "anchors", "pins",
                                       "uibc-release-v0.4.1.json"), encoding="utf-8"))
    assert cra._before_freeze("2026-11-20T04:00:00Z", pin["frozen_at"]) is True
