"""RFC 3161 tokens: request, parse, and offline verification.

Lives in the package (not only in tools/) so `verify.py` can judge an external
timestamp as a package-level check. `asn1crypto` and `cryptography` are optional
on purpose: without them the token cannot be judged, and the caller must report
"could not judge", never "passed".
"""

import hashlib

try:
    from asn1crypto import cms, tsp, x509  # noqa: F401
    HAVE_ASN1 = True
except Exception:  # pragma: no cover - environment dependent
    HAVE_ASN1 = False


def build_request(digest: bytes, sha_alg: str = "sha256") -> bytes:
    # Without asn1crypto there is no `tsp` to name. Say so, instead of raising
    # NameError: measured on 2026-11-20 in the release workflow, whose job installed
    # no extras - the anchor step recorded `NameError: name 'tsp' is not defined`
    # as the reason a token was missing, which reads like a code defect rather than
    # a missing dependency.
    if not HAVE_ASN1:
        raise RuntimeError("asn1crypto is unavailable: pip install asn1crypto")
    req = tsp.TimeStampReq({
        "version": "v1",
        "message_imprint": {
            "hash_algorithm": {"algorithm": sha_alg},
            "hashed_message": digest,
        },
        "cert_req": True,
        "nonce": int.from_bytes(hashlib.sha256(digest).digest()[:8], "big"),
    })
    return req.dump()


def parse_response(body: bytes):
    """Return (ok, info, problems). Never raises on malformed input."""
    if not HAVE_ASN1:
        return False, {}, ["asn1crypto is unavailable; cannot parse a timestamp token"]
    problems = []
    try:
        resp = tsp.TimeStampResp.load(body)
    except Exception as e:
        return False, {}, ["response is not a TimeStampResp (%s)" % e]

    try:
        status = resp["status"]["status"].native
    except Exception as e:
        return False, {}, ["response has no readable status (%s)" % e]
    if status not in ("granted", "granted_with_mods"):
        fail = resp["status"]["fail_info"]
        return False, {}, ["TSA refused: %s" % (fail.native if fail else status)]

    try:
        sd = resp["time_stamp_token"]["content"]
        tst = sd["encap_content_info"]["content"]
        tst = tst.parsed if not isinstance(tst, tsp.TSTInfo) else tst
    except Exception as e:
        return False, {}, ["cannot read TSTInfo from token (%s)" % e]

    digest = tst["message_imprint"]["hashed_message"].native
    gen_time = tst["gen_time"].native
    serial = tst["serial_number"].native
    info = {
        "gen_time": gen_time.isoformat() if hasattr(gen_time, "isoformat") else str(gen_time),
        "digest_hex": digest.hex() if isinstance(digest, bytes) else str(digest),
        "serial": str(serial),
        "policy": tst["policy"].native,
        "tsa": tst["tsa"].native if "tsa" in tst else None,
    }
    return True, info, problems


def verify_token(tsr_bytes: bytes, data_digest: bytes, cabundle_pem: bytes):
    """Offline checks: parse, messageImprint match, chain to CA, signature.

    Returns (ok, info, problems). Anything that cannot be judged yields ok=False
    plus a problem string - the caller decides whether that is FAIL or UNKNOWN.
    """
    ok, info, problems = parse_response(tsr_bytes)
    if not ok:
        return False, info, problems
    if info["digest_hex"] != data_digest.hex():
        problems.append("token's messageImprint is not the digest we asked about")

    try:
        from cryptography import x509 as cx509
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, padding
    except Exception as e:
        return False, info, problems + ["cryptography is unavailable (%s)" % e]

    try:
        sd = tsp.TimeStampResp.load(tsr_bytes)["time_stamp_token"]["content"]
        certs = [c.chosen for c in sd["certificates"] if c.name == "certificate"]
    except Exception as e:
        return False, info, problems + ["cannot read certificates (%s)" % e]

    ca_certs = []
    for chunk in cabundle_pem.split(b"-----END CERTIFICATE-----"):
        if b"-----BEGIN CERTIFICATE-----" in chunk:
            try:
                ca_certs.append(cx509.load_pem_x509_certificate(
                    chunk + b"-----END CERTIFICATE-----\n"))
            except Exception:
                pass

    signer = None
    for cert in certs:
        try:
            c = cx509.load_der_x509_certificate(cert.dump())
        except Exception:
            continue
        for ca in ca_certs:
            try:
                c.verify_directly_issued_by(ca)
                signer = c
                break
            except Exception:
                continue
        if signer:
            break
    if not signer:
        problems.append("no certificate in the token chains to the supplied CA bundle")

    if signer:
        try:
            sig = sd["signer_infos"][0]
            attrs = sig["signed_attrs"]
            if attrs:
                # CMS signs the SET OF signed attrs: same bytes with the [0]
                # IMPLICIT wrapper replaced by SEQUENCE (0xA0 -> 0x31).
                tbs = attrs.dump()
                if tbs and tbs[0] == 0xA0:
                    tbs = b"\x31" + tbs[1:]
            else:
                tbs = sd["encap_content_info"]["content"].dump()
            signature = sig["signature"].native
            digest_alg = sig["digest_algorithm"]["algorithm"].native
            pub = signer.public_key()
            h = {"sha256": hashes.SHA256(), "sha384": hashes.SHA384(),
                 "sha512": hashes.SHA512()}.get(digest_alg, hashes.SHA256())
            key_name = type(pub).__name__.lower()
            if "rsa" in key_name:
                pub.verify(signature, tbs, padding.PKCS1v15(), h)
            elif "ed25519" in key_name:
                pub.verify(signature, tbs)
            else:
                pub.verify(signature, tbs, ec.ECDSA(h))
            info["signature_verified"] = True
        except Exception as e:
            problems.append("signature check failed (%s: %s)"
                            % (type(e).__name__, str(e) or "no message"))
            info["signature_verified"] = False

    return (not problems), info, problems
