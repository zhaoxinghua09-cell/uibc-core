"""Policy artefact resolution (check S18).

`draft-marques-asqav-compliance-receipts-01` section 8 requires the verifier to
reject a receipt whose `policy_digest` does not resolve, and section 4.2.4
requires the value to be `sha256:<hex>` over a retained artefact recomputed as
`SHA-256(JCS(artefact))`. A digest that nobody can resolve is a number, not
evidence: it proves a policy existed only if someone kept the policy.

This module answers two questions:

1. does every digest listed in `evidence/policies.json` actually match the
   artefact shipped next to it? (a wrong hash is FAIL, not a warning)
2. when a chain document is present, does every `policy_digest` a receipt
   declares appear in that map? (an unresolvable digest is FAIL)

Deliberate limits: the artefact must be a JSON document, because the digest is
defined over its JCS encoding. A PDF policy has no JCS form, so it must be
shipped with a JSON projection; that is a real constraint of the draft, not of
this implementation.
"""

import json
import os
import re

from .canonical import hash_obj

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _parse_digest(value):
    """Accept `sha256:<hex>` (draft form) or bare 64-hex for tolerance."""
    if not isinstance(value, str):
        return None
    v = value.strip()
    if v.startswith("sha256:"):
        v = v[len("sha256:"):]
    return v if _HEX64.match(v) else None


def load_artefact(package_dir, rel_path):
    """Return (parsed_document, error). Never raises on a missing file."""
    path = os.path.join(package_dir, rel_path)
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        return (None, "cannot read policy artefact %r (%s)" % (rel_path, exc))
    try:
        return (json.loads(raw.decode("utf-8")), None)
    except (UnicodeDecodeError, ValueError) as exc:
        return (None, "policy artefact %r is not JSON (%s); the draft's digest "
                      "is defined over its JCS encoding, so a non-JSON artefact "
                      "needs a JSON projection shipped alongside" % (rel_path, exc))


def check_policies(package_dir, doc, required_digests=()):
    """Verify the policy map and any digests a receipt declares.

    Returns (problems, resolved_count). `doc` is `evidence/policies.json`:

        {"policies": [{"digest": "sha256:<hex>", "path": "evidence/policy/a.json"}]}
    """
    problems = []
    resolved = 0

    if not isinstance(doc, dict):
        return (["policies document is not an object"], 0)

    items = doc.get("policies")
    if not isinstance(items, list) or not items:
        return (["policies document lists no artefacts"], 0)

    known = {}
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            problems.append("policy %d is not an object" % i)
            continue
        declared = _parse_digest(item.get("digest"))
        rel = item.get("path")
        if not declared:
            problems.append("policy %d: digest is not sha256:<64 hex>" % i)
            continue
        if not isinstance(rel, str) or not rel:
            problems.append("policy %d: no path" % i)
            continue
        body, err = load_artefact(package_dir, rel)
        if err:
            problems.append(err)
            continue
        try:
            actual = hash_obj(body)
        except (TypeError, ValueError) as exc:
            problems.append("policy %d: artefact is not JCS-serializable (%s)"
                            % (i, exc))
            continue
        if actual != declared:
            problems.append(
                "policy %d: declared digest %s... but the artefact hashes to "
                "%s..." % (i, declared[:12], actual[:12]))
            continue
        known[declared] = rel
        resolved += 1

    for digest in required_digests:
        d = _parse_digest(digest)
        if d is None:
            problems.append("a receipt declares a malformed policy_digest %r"
                            % (digest,))
        elif d not in known:
            problems.append("receipt declares policy_digest %s... which does "
                            "not resolve in the package" % d[:12])

    return (problems, resolved)


def declared_digests(chain_doc):
    """Collect every `policy_digest` a chain document's receipts declare."""
    out = []
    if not isinstance(chain_doc, dict):
        return out
    for item in chain_doc.get("receipts") or []:
        if not isinstance(item, dict):
            continue
        env = item.get("envelope")
        if isinstance(env, dict):
            value = env.get("policy_digest")
            if isinstance(value, str) and value:
                out.append(value)
    return out
