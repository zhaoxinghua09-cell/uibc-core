"""Explainability layer (PROPOSAL, 2026-11-21).

Adds the four fields a reader needs that a verdict alone does not carry:
``evidence`` (which artefacts the rule read, and whether they exist),
``reproduce`` (the command that re-runs this verdict), ``remediation`` (what
to change), ``limitations`` (what this rule does not claim).

Design constraint: **this module adds fields and never changes a verdict**.
It is called once from ``verify()`` after every check has been collected - the
same place and the same reason ``basis`` is filled there. S6 alone has
fourteen branches; a per-branch edit would still miss a path.

Machine-readable output stays ASCII. A report that carries CJK text breaks
any consumer piping it through a cp936 console or a non-UTF-8 pipe: measured
on 2026-11-21, the agreement and decision-vector suites turned a JSON report
into `output was not JSON` purely because the new fields were written in
Chinese. Human-facing Chinese belongs to `uibc explain`, not to the JSON.

Nothing here may raise: an explainability layer that crashes a verifier would
be a new failure mode in exchange for a nicer report.
"""

import os

# Which artefacts each rule read. This is a declaration of the rule's input,
# not a claim about where the offending byte lives - that stays in `detail`.
DECLARED_ARTEFACTS = {
    "S0": ["manifest.json"],
    "S1": ["manifest.json", "evidence/index.json"],
    "S2": ["identity.json", "lifecycle.json"],
    "S3": ["lifecycle.json"],
    "S4": ["evidence/index.json", "evidence/"],
    "S5": ["manifest.json", "evidence/index.json"],
    "S6": ["seal.json"],
    "S7": ["evidence/index.json"],
    "S8": ["manifest.json"],
    "S9": ["manifest.json"],
    "S10": ["manifest.json"],
    "S11": ["manifest.json"],
    "S12": ["manifest.json", "lifecycle.json"],
    "S13": ["evidence/index.json"],
    "S14": ["evidence/index.json"],
    "S15": ["evidence/index.json"],
    "S16": ["evidence/index.json"],
    "S17": ["evidence/index.json"],
    "S18": ["evidence/policies.json"],
    "S19": ["manifest.json"],
}

REMEDIATION = {
    "S0": "Use a verifier build that can process this input, or normalise the input first.",
    "S1": "Declare the missing file or remove the undeclared one, then resubmit.",
    "S2": "Make identity.json's agent_id match every lifecycle event.",
    "S3": "Fix event type, order or time so the state machine can legally transition.",
    "S4": "Rebuild the package from unmodified files; editing the hash table proves nothing.",
    "S5": "Recompute evidence_root from all evidence and write it back to the manifest.",
    "S6": "Re-seal with the party holding the private key; prefer Ed25519 over HMAC in public use.",
    "S7": "Restore index.json metadata, or regenerate the index.",
    "S8": "Make the package state match the sealed checkpoint_head; do not truncate the log.",
    "S9": "Re-observe and pin the current head; do not roll back to an older self-consistent package.",
    "S10": "Declare all six closure components and their digests.",
    "S11": "Serialise strictly per JCS: no duplicate member names, no non-ECMAScript numbers.",
    "S12": "Use a real calendar date and a unique evidence_id.",
    "S13": "Recompute the merkle inclusion proof so it matches the item it proves.",
    "S14": "Restore base64 padding and remove stray characters.",
    "S15": "Make the anchor event resolvable, with a root recomputable from the package.",
    "S16": "Obtain a real third-party RFC 3161 timestamp covering this package's head.",
    "S17": "Keep the receipt chain linear: no forks, no fabricated genesis predecessor.",
    "S18": "Make policies.json digests resolvable and consistent with the shipped artefacts.",
    "S19": "First observation returning INCONCLUSIVE is expected; compare with --state-file afterwards.",
}

LIMITATIONS = {
    "S0": "Answers whether this build can process the input, not whether the input is compliant.",
    "S4": "Checks bytes against declarations; says nothing about whether the evidence is true.",
    "S5": "A matching root is not truth: it binds this list to this root and nothing more.",
    "S6": "A valid signature proves key possession over this content, not that the content is true.",
    "S9": "Out-of-band pinning is the only way to see a rollback; unpinned, that risk is invisible.",
    "S16": "Needs asn1crypto; without it the check is INCONCLUSIVE and never downgrades to PASS.",
    "S19": "PASS here means 'not observed to be stale', not 'authentic'.",
}

DEFAULT_REMEDIATION = "Fix the location named in `detail`, then regenerate the package."
DEFAULT_LIMITATION = "This check answers its own question only; it is not a blanket endorsement."


def _package_paths(package_dir):
    paths = set()
    for root, _dirs, files in os.walk(package_dir):
        for f in files:
            rel = os.path.relpath(os.path.join(root, f), package_dir)
            paths.add(rel.replace(os.sep, "/"))
    return paths


def _resolve(rel, paths):
    """Return (exists, resolved_posix_path). Tolerates subdirectory layouts:
    sealing artefacts may live under signatures/ rather than the package root,
    and a declaration that assumed the root would report a false absence."""
    if rel in paths:
        return True, rel
    if rel.endswith("/"):
        return any(p.startswith(rel) for p in paths), rel
    hits = [p for p in paths if p == rel or p.endswith("/" + rel)]
    if hits:
        return True, sorted(hits)[0]
    return False, rel


def decorate(report, package_dir):
    """Fill evidence/reproduce/remediation/limitations on every check."""
    try:
        paths = _package_paths(package_dir)
        for c in report.get("checks", []):
            cid = c.get("id", "")
            rels = DECLARED_ARTEFACTS.get(cid, ["manifest.json"])
            ev = []
            for rel in rels:
                ok, resolved = _resolve(rel, paths)
                ev.append({"path": resolved, "exists": ok})
            c.setdefault("evidence", ev)
            # Copy-pasteable AND deterministic: an absolute path would make two
            # runs of the same package produce different report bytes, which is
            # exactly what the agreement and decision-vector suites refuse.
            c.setdefault("reproduce",
                         "python -m uibc_core.cli verify <package>")
            if c.get("result") in ("FAIL", "INCONCLUSIVE"):
                c.setdefault("remediation", REMEDIATION.get(cid, DEFAULT_REMEDIATION))
            else:
                c.setdefault("remediation", "none")
            c.setdefault("limitations", LIMITATIONS.get(cid, DEFAULT_LIMITATION))
    except Exception:  # noqa: BLE001 - never let reporting break a verdict
        pass
    return report
