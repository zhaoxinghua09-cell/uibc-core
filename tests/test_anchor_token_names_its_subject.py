"""A timestamp checked against the wrong file is reported as a broken witness.

Measured 2026-11-21 on main: with the published `.sig` unreachable (no gh, no network),
`verify_dir` falls back to the signature held in `anchors/attestations/<tag>/`, and then
verified the stored FreeTSA token against that `.sig` file. The token attests the digest
(`ATTESTATION.json` says `timestamp_on_the_digest`), so the check printed
"the timestamp on the signature does not verify" -- an accusation against a third party
whose evidence was fine. What failed was which bytes we handed the verifier.
"""
import io
import json
import os
import shutil
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))

import check_release_anchors as check  # noqa: E402


def _newest():
    return check._newest_pinned_tag()


def test_the_source_does_not_verify_the_token_against_the_signature_file():
    source = io.open(os.path.join(REPO, "tools", "check_release_anchors.py"),
                     encoding="utf-8").read()
    assert "_verify_token(tok, held" not in source, (
        "the stored token attests the digest; handing it the .sig makes a good token "
        "look broken")
    assert '"CORPUS-DIGESTS.txt"), ca)' in source or "CORPUS-DIGESTS.txt'), ca)" in source, (
        "the token is no longer checked against the digest at all")


def test_the_verifier_is_handed_the_digest(monkeypatch):
    tag = _newest()
    src = os.path.join(REPO, "anchors", "attestations", tag)
    tmp = tempfile.mkdtemp()
    seen = {}

    def fake_token(token, data, cabundle):
        seen["data"] = data
        digest = check._sha256(os.path.join(src, "CORPUS-DIGESTS.txt"))
        return 0, json.dumps({"verified": True,
                              "info": {"gen_time": "2026-11-20T10:42:03+00:00",
                                       "serial": 172269871, "digest_hex": digest}})

    monkeypatch.setattr(check, "_verify_token", fake_token)
    try:
        shutil.copytree(src, tmp, dirs_exist_ok=True)
        os.remove(os.path.join(tmp, "CORPUS-DIGESTS.txt.sig"))  # the page's copy is unreachable
        check.verify_dir(tmp, tag)
        assert seen.get("data", "").endswith("CORPUS-DIGESTS.txt"), (
            "the token was checked against %r, not the digest" % seen.get("data"))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
