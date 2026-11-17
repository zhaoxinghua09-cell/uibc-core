"""Linear receipt chain (check S17).

Why this exists: `S8` commits the state of the package and `S13` proves a leaf
is inside the tree we built. Both answer "was this byte changed since we
committed it". Neither answers the question a regulator actually asks when a
single record is pulled out of the middle of a stream: *is this record the
successor of that record?* That answer comes from a linear link, not from a
tree.

`draft-marques-asqav-compliance-receipts-01` section 4.3 makes the link
mandatory: every receipt carries `previousReceiptHash`, the lowercase hex
SHA-256 of the RFC 8785 (JCS) encoding of its predecessor's signed envelope,
and the first receipt in a chain carries 64 zeros. Section 8 then requires the
verifier to recompute the predecessor digest and compare.

Scope, stated so it can be argued with:

* we verify the LINK, not the receipt schema. A chain document can carry any
  envelope shape; what is checked is that the declared predecessor digest is
  the digest of the actual predecessor.
* JCS comes from `canonical.canonicalize`, the same code that produces every
  other digest in this package, so a chain cannot be valid under one
  canonicalization and invalid under another. Numbers follow the RFC 8785
  number rule there, so a float does not silently disagree across languages.
* a value JCS cannot encode at all (e.g. a byte string reaching the API) is a
  FAIL, not a skip: an unjudgeable link is not an intact link.
* the genesis value is 64 zeros, and a non-zero genesis is reported, not
  ignored: an appended chain must not be able to claim a predecessor it does
  not have.
"""

import re

from .canonical import hash_obj

GENESIS = "0" * 64
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def receipt_digest(envelope) -> str:
    """Lowercase hex SHA-256 over the JCS encoding of one signed envelope."""
    return hash_obj(envelope)


def check_chain(doc) -> tuple:
    """Verify a chain document. Returns (problems, checked_count).

    `doc` is the parsed `evidence/chain.json`:

        {"schema": "...", "receipts": [
            {"envelope": {...}, "previous_receipt_hash": "<64 hex>"},
            ...]}
    """
    problems = []
    checked = 0

    if not isinstance(doc, dict):
        return (["chain document is not an object"], 0)

    receipts = doc.get("receipts")
    if not isinstance(receipts, list) or not receipts:
        return (["chain document carries no receipts"], 0)

    prev_digest = None
    for i, item in enumerate(receipts):
        if not isinstance(item, dict):
            problems.append("receipt %d is not an object" % i)
            continue

        envelope = item.get("envelope")
        declared = item.get("previous_receipt_hash")

        if not isinstance(envelope, dict):
            problems.append("receipt %d carries no envelope object" % i)
            continue

        if not isinstance(declared, str) or not _HEX64.match(declared):
            problems.append(
                "receipt %d: previous_receipt_hash is not 64 lowercase hex "
                "characters" % i)
            continue

        expected = GENESIS if i == 0 else prev_digest

        if i == 0 and declared != GENESIS:
            problems.append(
                "receipt 0: previous_receipt_hash is %s..., but the first "
                "receipt of a chain must carry 64 zeros" % declared[:12])
        elif i > 0 and declared != expected:
            problems.append(
                "receipt %d: previous_receipt_hash is %s..., but the "
                "predecessor's digest is %s..."
                % (i, declared[:12], (expected or "")[:12]))

        try:
            prev_digest = receipt_digest(envelope)
        except TypeError as exc:
            problems.append(
                "receipt %d: envelope cannot be canonicalized (%s); a chain "
                "is FAIL rather than inconclusive because the value is "
                "unjudgeable, not merely absent" % (i, exc))
            prev_digest = None
            continue
        except ValueError as exc:
            problems.append("receipt %d: envelope is not JCS-serializable (%s)"
                            % (i, exc))
            prev_digest = None
            continue

        checked += 1

    return (problems, checked)
