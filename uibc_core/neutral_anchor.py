"""A neutral anchor: one RFC 3161 token over a *set* of digests, one per format.

The problem it addresses is measured, not hypothetical. On 2026-11-20 the EATF
vectors were parsed and 12 of 12 readable tokens imprinted the package's payload
digest, while this project's S16 requires a token over the package head. A
byte-perfect conversion between the two containers therefore still fails our
check: the token is valid, and it is about something else. No amount of parser
writing fixes that, because both sides are behaving correctly.

The fix has to be at the level of *what the token is about*. Here the subject is
an ordered list of (format, digest) pairs covering as many formats as the issuer
needs. The token then covers sha256 over the canonical serialization of that
list, so one token witnesses the state of several ecosystems at one instant.

Rules, stated so that an outside verifier can reproduce them without reading
this code:

  canonical bytes = UTF-8, JSON, object keys sorted by code point, no whitespace,
                    no ASCII escaping, subjects in the order given.
  digest          = sha256(canonical bytes of the "subjects" value).
  verdict         = PASS only if the token verifies against the supplied CA bundle
                    AND its imprint equals that digest.

What this does not do: it does not make the two verifiers agree on *checks*. It
makes one timestamp witness two independent statements at once, which is the
precondition for any later comparison of the statements themselves.
"""

import hashlib
import json
import os

SCHEMA = "uibc-neutral-anchor/0.1"


def canonical_bytes(subjects):
    """The bytes the token must cover. Deliberately dependency-free."""
    body = json.dumps(subjects, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False)
    return body.encode("utf-8")


def subject_digest(subjects):
    return hashlib.sha256(canonical_bytes(subjects)).digest()


def entry(fmt, digest_hex, source, what=""):
    return {"format": fmt, "digest": digest_hex, "source": source, "what": what}


def build(subjects, created_at, tsr="timestamps/anchor.tsr",
          cabundle="timestamps/ca.pem", policy=""):
    return {"schema": SCHEMA,
            "created_at": created_at,
            "policy": policy,
            "subjects": subjects,
            "tsr": tsr,
            "cabundle": cabundle,
            "subject_digest_sha256": subject_digest(subjects).hex()}


def verify(envelope, base_dir):
    """Return (verdict, detail). Verdict is PASS / FAIL / INCONCLUSIVE."""
    from uibc_core.tsa import verify_token
    tsr_path = os.path.join(base_dir, envelope.get("tsr", ""))
    ca_path = os.path.join(base_dir, envelope.get("cabundle", ""))
    if not (os.path.isfile(tsr_path) and os.path.isfile(ca_path)):
        return "INCONCLUSIVE", {"why": "token or CA bundle missing"}
    with open(tsr_path, "rb") as f:
        tsr = f.read()
    with open(ca_path, "rb") as f:
        ca = f.read()
    digest = subject_digest(envelope.get("subjects") or [])
    if envelope.get("subject_digest_sha256") not in (None, digest.hex()):
        return "FAIL", {"why": "envelope records a different subject digest",
                        "recomputed": digest.hex()}
    ok, meta, problems = verify_token(tsr, digest, ca)
    if not ok:
        return "FAIL", {"why": "token does not cover these subjects",
                        "token": meta, "problems": problems}
    detail = {"token": meta, "subjects": [s.get("format") for s in envelope["subjects"]],
              "subject_digest": digest.hex()}
    return "PASS", detail


def describe(envelope):
    return "\n".join("%-28s %s  (%s)" % (s.get("format"), (s.get("digest") or "")[:20],
                                         s.get("source")) for s in envelope["subjects"])
