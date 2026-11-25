"""Build the deterministic BID document fixture used by the JS cross-check.

Run:  python tools/make_bid_fixture.py
Writes fixtures/bid/signed_document.json (canonical JSON, UTF-8, no BOM).

Fixed seed on purpose: the fixture is committed, so `tools/verify-js/bid.mjs`
can be re-run by anyone and must still verify. A random seed would make the
committed file un-reproducible and the claim un-falsifiable.
"""

import json
import pathlib
import sys

REPO = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from uibc_core import bid_protocol as B

SEED = bytes(range(32))                      # 00 01 02 ... 1f
KEY_HEX = "b0" + B.ed_public_key(SEED).hex()  # BIF-style 0xb0 prefix
DID = "did:bid:ef18F9AVK4SQLZPRrPkrVWwp9kbpdXHx"
KEY_ID = DID + "#key-1"


def build():
    doc = {
        "@context": ["https://w3.org/ns/did/v1"],
        "id": DID,
        "created": "2021-06-24T09:10:09Z",
        "updated": "2021-06-24T09:10:09Z",
        "authentication": [KEY_ID],
        "publicKey": [{
            "controller": DID,
            "id": KEY_ID,
            "publicKeyHex": KEY_HEX,
            "type": "ED25519",
        }],
        "alsoKnownAs": [{"type": 101, "id": "did:bid:efOtherAliasForTheSameKey"}],
        "extension": {
            "recovery": [KEY_ID],
            "ttl": 86400,
            "type": 105,
            "attributes": [{
                "key": "contract",
                "desc": "contract address",
                "encrypt": 1,
                "format": "text",
                "value": "did:bid:efJgt44mNDewKK1VEN454R17cjso3mSG",
            }],
        },
        "service": [{
            "id": DID + "#resolver",
            "type": "DIDSubResolver",
            "version": "1.0",
            "protocol": 2,
            "serverType": 1,
            "serviceEndpoint": "http://sub.example.com/",
        }],
    }
    return B.sign_bid_document(doc, SEED, KEY_ID)


def main():
    doc = build()
    out = REPO / "fixtures" / "bid" / "signed_document.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("wrote", out.relative_to(REPO))
    print("key      ", KEY_HEX)
    print("signing  ", B.signing_bytes(doc).decode("utf-8")[:120], "...")
    print("proof    ", doc["proof"]["signatureValue"][:32], "...")


if __name__ == "__main__":
    main()
