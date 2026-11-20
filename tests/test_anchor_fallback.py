import io
import json
import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__))
                      ) if "__file__" in dir() else os.getcwd()
import sys
sys.path.insert(0, ROOT)

from tools import anchor_ots, check_release_anchors as cra  # noqa: E402


def _write(tmp_path, name, body):
    path = os.path.join(str(tmp_path), name)
    with io.open(path, "wb") as handle:
        handle.write(body)
    return path


def test_two_calendars_down_and_one_up_still_stamps_the_digest(tmp_path):
    """Measured 2026-11-20: alice and finney answered 503 while bob answered."""
    target = _write(tmp_path, "digests.txt", b"hello\n")
    seen = []

    class FakeTimestamp:
        def serialize(self, ctx):
            ctx.write(b"proof")

    class FakeContext:
        def __init__(self):
            self.buf = b""

        def write(self, data):
            self.buf += data

        def getbytes(self):
            return self.buf

    def submit(calendar, digest):
        seen.append(calendar)
        if "bob" not in calendar:
            raise RuntimeError("HTTP Error 503: Service Unavailable")
        return FakeTimestamp()

    class FakeModule:
        BytesSerializationContext = FakeContext

    # The real serializer is only needed on the path that succeeds; the stub stands
    # in for it here so the test does not depend on the library being installed.
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "opentimestamps", FakeModule)
        mp.setitem(sys.modules, "opentimestamps.core", FakeModule)
        mp.setitem(sys.modules, "opentimestamps.core.serialize", FakeModule)
        info = anchor_ots.stamp(target, calendars=("https://alice", "https://bob"), submit=submit)

    assert info["calendar"] == "https://bob"
    assert [t["calendar"] for t in info["tried"]] == ["https://alice", "https://bob"]
    assert info["tried"][0]["error"].startswith("RuntimeError")
    assert os.path.isfile(info["out"])


def test_no_calendar_answering_names_every_attempt(tmp_path):
    target = _write(tmp_path, "digests.txt", b"hello\n")

    def submit(calendar, digest):
        raise RuntimeError("HTTP Error 503: Service Unavailable")

    with pytest.raises(RuntimeError) as excinfo:
        anchor_ots.stamp(target, calendars=("https://alice", "https://finney"), submit=submit)
    message = str(excinfo.value)
    assert "https://alice" in message and "https://finney" in message
    assert "503" in message


def test_a_token_attesting_a_different_digest_is_refused(tmp_path):
    _write(tmp_path, "CORPUS-DIGESTS.txt", b"the published list\n")
    _write(tmp_path, "anchor_freetsa.tsr", b"token")
    _write(tmp_path, "anchor_freetsa_ca.pem", b"pem")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cra, "_verify_token", lambda *a: (0, json.dumps({
            "verified": True,
            "info": {"digest_hex": "0" * 64, "gen_time": "2026-11-20T04:05:27+00:00",
                     "serial": "1"},
            "problems": []})))
        code, lines = cra.verify_dir(str(tmp_path))

    assert code == 1
    assert any("different digest" in line for line in lines)


def test_an_unrunnable_verifier_is_not_measured_not_refused(tmp_path):
    for name, body in (("CORPUS-DIGESTS.txt", b"x"), ("anchor_freetsa.tsr", b"t"),
                       ("anchor_freetsa_ca.pem", b"p")):
        _write(tmp_path, name, body)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cra, "_verify_token", lambda *a: (None, "ModuleNotFoundError: cryptography"))
        code, lines = cra.verify_dir(str(tmp_path))

    assert code == 3
    assert "could not run the verifier" in lines[0]


def _token_json(digest_hex):
    return json.dumps({"verified": True, "info": {"digest_hex": digest_hex,
                                                  "gen_time": "2026-11-20T04:24:44+00:00",
                                                  "serial": "172003659"}, "problems": []})


def test_a_signature_under_the_recorded_key_is_accepted(tmp_path):
    _write(tmp_path, "CORPUS-DIGESTS.txt", b"list\n")
    _write(tmp_path, "anchor_freetsa.tsr", b"t")
    _write(tmp_path, "anchor_freetsa_ca.pem", b"p")
    _write(tmp_path, "CORPUS-DIGESTS.txt.sig", b"sig")
    digest = cra._sha256(str(tmp_path / "CORPUS-DIGESTS.txt"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cra, "_verify_token", lambda *a: (0, _token_json(digest)))
        mp.setattr(cra, "_verify_sig", lambda *a: (0, json.dumps(
            {"key_id": "179c615aef27cbcd", "file_sha256": digest})))
        mp.setattr(cra, "_pinned_key", lambda: "179c615aef27cbcd")
        code, lines = cra.verify_dir(str(tmp_path))
    assert code == 0
    assert any("key_id 179c615aef27cbcd" in line for line in lines)


def test_a_signature_under_a_different_key_is_refused(tmp_path):
    _write(tmp_path, "CORPUS-DIGESTS.txt", b"list\n")
    _write(tmp_path, "anchor_freetsa.tsr", b"t")
    _write(tmp_path, "anchor_freetsa_ca.pem", b"p")
    _write(tmp_path, "CORPUS-DIGESTS.txt.sig", b"sig")
    digest = cra._sha256(str(tmp_path / "CORPUS-DIGESTS.txt"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cra, "_verify_token", lambda *a: (0, _token_json(digest)))
        mp.setattr(cra, "_verify_sig", lambda *a: (0, json.dumps(
            {"key_id": "deadbeefdeadbeef", "file_sha256": digest})))
        mp.setattr(cra, "_pinned_key", lambda: "179c615aef27cbcd")
        code, lines = cra.verify_dir(str(tmp_path))
    assert code == 1
    assert any("records 179c615aef27cbcd" in line for line in lines)


def test_a_signature_with_no_recorded_key_says_the_signer_is_unidentified(tmp_path):
    _write(tmp_path, "CORPUS-DIGESTS.txt", b"list\n")
    _write(tmp_path, "anchor_freetsa.tsr", b"t")
    _write(tmp_path, "anchor_freetsa_ca.pem", b"p")
    _write(tmp_path, "CORPUS-DIGESTS.txt.sig", b"sig")
    digest = cra._sha256(str(tmp_path / "CORPUS-DIGESTS.txt"))
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(cra, "_verify_token", lambda *a: (0, _token_json(digest)))
        mp.setattr(cra, "_verify_sig", lambda *a: (0, json.dumps(
            {"key_id": "179c615aef27cbcd", "file_sha256": digest})))
        mp.setattr(cra, "_pinned_key", lambda: None)
        code, lines = cra.verify_dir(str(tmp_path))
    assert code == 1
    assert any("unidentified" in line for line in lines)


def test_the_repository_records_a_signing_key():
    path = os.path.join(ROOT, "anchors", "release-signing-key.json")
    assert os.path.isfile(path)
    key = json.load(open(path, encoding="utf-8"))
    assert key["alg"] == "ed25519"
    assert len(key["key_id"]) == 16
    assert "nowhere in this repository" in key["where_the_private_half_is"]
