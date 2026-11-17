"""Verifier (archive SS16): PASS / FAIL / INCONCLUSIVE, scoped report.

Report discipline (archive SS16/SS17):
  - report MUST state scope, limitations, checked, not_checked
  - result is a scoped proof: "No unauthorized action was detected within the
    observed evidence boundary" - never a claim of absolute trustworthiness.
"""

import json
import os
import re

from .canonical import evidence_root, hash_file
from .lifecycle import validate_lifecycle, validate_lifecycle_strict
from .signing import (ALGORITHM, ALGORITHM_ED25519, b64decode_strict,
                      ed_key_id, ed_seal_verify_scoped, key_id, seal_verify)
from . import SPEC_VERSION, VERIFIER_ID, __version__, spec_id

# Computed once per process: the label plus the bytes it names (see
# __init__.spec_id). Reported so a reader can tell two builds of the same
# version string apart.
_SPEC_ID = spec_id()

REQUIRED_FILES = ["manifest.json", "identity.json", "lifecycle.json", "evidence/index.json"]

# draft-noa-scitt-ai-agent-receipt-00 Section 3 fixes this vocabulary; adopting
# it verbatim means a uibc principal_type maps 1:1 into a NOA receipt.
PRINCIPAL_TYPES = {"HUMAN", "SERVICE", "POLICY", "SANDBOX_SIM"}

_POLICY_HASH_RE = re.compile(r"^(sha256:)?[0-9a-f]{64}$")

EVIDENCE_TYPES = {
    "IDENTITY", "LIFECYCLE", "INPUT", "ACTION", "TOOL", "MEMORY", "OUTPUT",
    "EVALUATION", "HUMAN_DECISION", "VERIFICATION", "INCIDENT", "RETIREMENT",
}

# draft-maintainer-1f916-agent-record-01 Section 3.1: a signature proves
# exactly what its custody disclosure permits it to prove, and verifiers MUST
# surface custody alongside the signature result. Enum copied verbatim (with
# "threshold(k,n)" kept as the literal family name).
KEY_CUSTODY = {"self_held", "platform_held", "household_held", "threshold",
               "kms", "hsm", "session_delegated"}


def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _verify_impl(package_dir: str, key: bytes = None, pubkey: bytes = None,
                expect_head: str = None) -> dict:
    """Verify a submission.uibc package directory. Returns a report dict.

    Seal v0.3 verdict semantics (docs/verdict-and-seal-semantics.md):

    - The top-level result is three-valued: FAIL if any check FAILs, else
      INCONCLUSIVE if any check is INCONCLUSIVE, else PASS. An unverifiable
      seal can therefore no longer hide under a top-level PASS (the v0.2
      behaviour an external review flagged in 2026-11).
    - An Ed25519 seal is verified PUBLICLY in every mode: the public key
      travels with the package, so anyone can check provenance.
      ``pubkey`` optionally pins the expected public key - a substituted
      key then FAILS S6.
    - key=...  : strict owner mode for HMAC seals. A missing/invalid seal
               or a key_id that does not match the provided owner key
               FAILS S6. This is the mode that closes the 'malicious'
               self-consistent forgery for symmetric seals.
    - An unsigned package is INCONCLUSIVE at S6 in open mode: its evidence
      chain is internally consistent, but its provenance is unattested.
    """
    checks = []
    ok = True

    def record(cid, name, passed, detail=""):
        nonlocal ok
        checks.append({"id": cid, "name": name, "result": "PASS" if passed else "FAIL", "detail": detail})
        if not passed:
            ok = False

    # S1 structure: required files present AND nothing undeclared inside the
    # package directory (v1.1 fix F4). Before this, a notes.md / README that
    # contradicted the evidence could sit in the package root and no check
    # noticed - one of the 18 mutations was accepted that way.
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(package_dir, f))]

    manifest = _load_json(os.path.join(package_dir, "manifest.json")) if not missing else {}
    identity = _load_json(os.path.join(package_dir, "identity.json")) if not missing else {}
    lifecycle = _load_json(os.path.join(package_dir, "lifecycle.json")) if not missing else {}
    index = _load_json(os.path.join(package_dir, "evidence", "index.json")) if not missing else {"entries": []}

    declared = set(REQUIRED_FILES) | {"signatures/seal.json"}
    for e in index.get("entries", []):
        declared.add("evidence/" + str(e.get("path", "")).replace("\\", "/"))
    os_junk = {"thumbs.db", ".ds_store", "desktop.ini"}
    undeclared = []
    if not missing and not manifest.get("allow_extra_files"):
        for root, _dirs, files in os.walk(package_dir):
            for name in files:
                rel = os.path.relpath(os.path.join(root, name),
                                      package_dir).replace("\\", "/")
                if rel in declared or name.lower() in os_junk:
                    continue
                undeclared.append(rel)
    # A stray file at the package root can contradict the evidence it sits
    # next to, so it fails S1. Auxiliary files in sub-directories (e.g. the
    # runtime hook's snapshots/ copies) are not evidence and are reported as
    # "not covered by the evidence root" instead of failing the package.
    root_extras = [u for u in undeclared if "/" not in u]
    nested_extras = [u for u in undeclared if "/" in u]
    s1_detail = []
    if missing:
        s1_detail.append(f"missing: {missing}")
    if root_extras:
        s1_detail.append(f"undeclared files at package root: {sorted(root_extras)}")
    if nested_extras:
        s1_detail.append(f"note: {sorted(nested_extras)} not covered by the evidence root")
    record("S1", "package structure", not missing and not root_extras,
           "; ".join(s1_detail) if s1_detail
           else f"all required files present, no undeclared files "
                f"({len(declared)} declared)")

    # S2 identity consistency (+ v1.1 identity fields: principal_type enum
    # aligned to draft-noa-scitt-ai-agent-receipt-00 Section 3, optional
    # policy_hash which maps to GAR's cap_profile_hash, and the
    # long-term-identity / single-run separation)
    agent_id_ok = bool(identity.get("agent_id")) and \
        manifest.get("agent_id") == identity.get("agent_id")
    s2_problems = []
    if not agent_id_ok:
        s2_problems.append(f"identity.agent_id={identity.get('agent_id')!r}, "
                           f"manifest.agent_id={manifest.get('agent_id')!r}")
    principal = identity.get("principal_type")
    if principal is not None and principal not in PRINCIPAL_TYPES:
        s2_problems.append(f"identity.principal_type={principal!r} not in "
                           f"{sorted(PRINCIPAL_TYPES)}")
    policy_hash = manifest.get("policy_hash")
    if policy_hash is not None and not _POLICY_HASH_RE.match(str(policy_hash)):
        s2_problems.append(f"manifest.policy_hash={policy_hash!r} is not "
                           f"'sha256:<64 hex>'")
    logical = identity.get("logical_agent_id")
    if logical is not None and str(identity.get("agent_id") or "") != str(logical) \
            and not str(identity.get("agent_id") or "").startswith(str(logical)):
        s2_problems.append(f"identity.agent_id={identity.get('agent_id')!r} does not "
                           f"derive from logical_agent_id={logical!r}")
    custody = identity.get("key_custody")
    if custody is not None and custody not in KEY_CUSTODY:
        s2_problems.append(f"identity.key_custody={custody!r} not in "
                           f"{sorted(KEY_CUSTODY)}")
    record("S2", "identity consistency", not s2_problems,
           "; ".join(s2_problems) if s2_problems else
           f"agent_id={identity.get('agent_id')!r} consistent"
           + (f", principal_type={principal}" if principal else "")
           + (f", policy_hash={str(policy_hash)[:16]}..." if policy_hash else ""))

    # S3 lifecycle state machine + chain, plus the v1.1 semantic layer
    # (L8 timestamps monotonic & plausible, L10 actor allow-list, L11 once-only
    # ACTIVATE). Those three closed the last lifecycle blind spots measured by
    # tools/mutation_benchmark.py.
    events = lifecycle.get("events", [])
    l_errors = validate_lifecycle(events)
    principals = {identity.get("owner"), identity.get("agent_id")} - {None}
    l_strict = validate_lifecycle_strict(
        events,
        created_at=manifest.get("created_at") or identity.get("created_at"),
        allowed_actors=principals or None,
    )
    record("S3", "lifecycle state machine + semantics", not (l_errors or l_strict),
           "; ".join(l_errors + l_strict) or
           f"{len(events)} events, chain valid, timestamps monotonic, actors authorised")

    # S4 evidence integrity: recompute content hashes from files
    entries = index.get("entries", [])
    s4_failures = []
    recomputed_hashes = []
    for e in entries:
        p = os.path.join(package_dir, "evidence", e.get("path", ""))
        if not os.path.isfile(p):
            s4_failures.append(f"missing file {e.get('path')!r}")
            continue
        actual = hash_file(p)
        recomputed_hashes.append(actual)
        if actual != e.get("content_hash"):
            s4_failures.append(f"hash mismatch on {e.get('path')!r}")
        if e.get("type") not in EVIDENCE_TYPES:
            s4_failures.append(f"unknown evidence type {e.get('type')!r}")
    record("S4", "evidence integrity", not s4_failures,
           f"{len(entries)} entries checked; " + ("; ".join(s4_failures) if s4_failures else "all hashes match"))

    # S4b: index METADATA must match its committed digest (v1.1). Content
    # hashes alone cannot see an entry's type/note/action_digest being
    # rewritten; the index digest is carried in the sealed manifest.
    index_digest_field = manifest.get("evidence_index_digest")
    if index_digest_field:
        from .canonical import index_metadata_digest as _imd
        actual_index_digest = _imd(index)
        if actual_index_digest != index_digest_field:
            ok = False
            checks.append({"id": "S7", "name": "evidence index metadata",
                           "result": "FAIL",
                           "detail": "evidence/index.json metadata does not match "
                                     "the sealed evidence_index_digest "
                                     f"(expected {str(index_digest_field)[:20]}..., "
                                     f"actual {actual_index_digest[:20]}...)"})
        else:
            checks.append({"id": "S7", "name": "evidence index metadata",
                           "result": "PASS",
                           "detail": "index metadata matches evidence_index_digest"})

    # S8 / S9 checkpoint head over the WHOLE package state (v1.1).
    # S8: manifest checkpoint vs what is on disk - catches a log that was
    # shortened while the manifest still describes the longer state, which a
    # bare hash chain cannot see (the shorter chain is still internally valid).
    # S9: checkpoint pinned out-of-band - catches substitution with an older
    # but perfectly self-consistent package. NOTHING inside the package can
    # detect that; only an observation made elsewhere can.
    from .canonical import checkpoint_head as _ch
    from .canonical import index_metadata_digest as _imd2
    from .canonical import lifecycle_head as _lh
    actual_lc_head = _lh(events)
    try:
        actual_ckpt = _ch(actual_lc_head, evidence_root(recomputed_hashes),
                          _imd2(index), len(entries))
    except Exception as e:
        # a NaN / non-ECMAScript number anywhere in the state we commit to
        actual_ckpt = "sha256:uncomputable"
        ok = False
        checks.append({"id": "S8", "name": "package checkpoint head",
                       "result": "FAIL",
                       "detail": f"state is not canonicalizable ({type(e).__name__}: "
                                 f"{str(e)[:60]}) - a hostile number such as NaN in "
                                 "the manifest is itself a violation"})
    ckpt_field = manifest.get("checkpoint_head")
    if ckpt_field:
        if actual_ckpt != ckpt_field:
            ok = False
            checks.append({"id": "S8", "name": "package checkpoint head",
                           "result": "FAIL",
                           "detail": "state does not match the sealed checkpoint_head "
                                     f"(manifest {str(ckpt_field)[:20]}..., "
                                     f"disk {actual_ckpt[:20]}...) - state truncated, "
                                     "rolled back, or replaced after sealing"})
        else:
            checks.append({"id": "S8", "name": "package checkpoint head",
                           "result": "PASS",
                           "detail": f"checkpoint matches ({len(events)} event(s), "
                                     f"{len(entries)} evidence item(s))"})
    if expect_head:
        if str(actual_ckpt) != str(expect_head):
            ok = False
            checks.append({"id": "S9", "name": "head pinned out-of-band",
                           "result": "FAIL",
                           "detail": "package checkpoint does not match the pinned "
                                     f"--expect-head ({str(expect_head)[:20]}...) - "
                                     "rollback to an older self-consistent package, "
                                     "or a wrong pin"})
        else:
            checks.append({"id": "S9", "name": "head pinned out-of-band",
                           "result": "PASS",
                           "detail": "checkpoint matches the out-of-band pinned value"})

    # S5 evidence root
    if entries and not s4_failures:
        computed = evidence_root(recomputed_hashes)
        root_ok = computed == manifest.get("evidence_root")
        record("S5", "evidence root", root_ok,
               f"computed={computed}, manifest={manifest.get('evidence_root')}")
    else:
        ok = False
        checks.append({"id": "S5", "name": "evidence root", "result": "INCONCLUSIVE",
                       "detail": "skipped: evidence missing or S4 failed"})

    # S6 seal signature (v0.3: HMAC owner seals + Ed25519 public seals)
    # Hostile input must never crash the verifier: a manifest containing NaN or
    # an uncanonicalizable number raises inside JCS, and a crash is not a
    # verdict (red-team RT06). Convert it into a FAIL on the check that needs
    # canonical bytes.
    seal_path = os.path.join(package_dir, "signatures", "seal.json")
    has_seal = os.path.isfile(seal_path) and not missing
    assurance = "unattested"
    if has_seal:
        try:
            seal = _load_json(seal_path)
        except Exception as e:
            seal = None
            ok = False
            checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                           "detail": f"seal.json is not readable JSON: {type(e).__name__}"})
    if has_seal and seal is not None:
        algo = seal.get("algorithm")
        if algo == ALGORITHM_ED25519:
            pub = b64decode_strict(seal.get("public_key"))
            if pub is None or len(pub) != 32:
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "Ed25519 seal records no valid public_key"})
            elif seal.get("key_id") != ed_key_id(pub):
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "key_id does not match the recorded public key "
                                         "(seal metadata inconsistent)"})
            elif pubkey is not None and bytes(pubkey) != pub:
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "public key does not match the pinned --pubkey "
                                         "(possible key substitution or wrong pin)"})
            elif key is not None:
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "seal algorithm is Ed25519; the provided --key is an "
                                         "HMAC owner key and cannot check it - re-run without "
                                         "--key, or pin the signer with --pubkey"})
            elif ed_seal_verify_scoped(pub, identity, manifest, lifecycle,
                                        seal.get("signature", "")) is None:
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "Ed25519 signature invalid: identity/manifest"
                                         "/lifecycle do not match the seal"})
            else:
                coverage = ed_seal_verify_scoped(pub, identity, manifest, lifecycle,
                                                 seal.get("signature", ""))
                assurance = "public-key"
                note = ("" if coverage == "lifecycle-bound" else
                        " - LEGACY seal: covers identity+manifest only, "
                        "lifecycle tampering is not signed (S3 semantics are the only guard)")
                checks.append({"id": "S6", "name": "seal signature", "result": "PASS",
                               "detail": f"Ed25519 seal valid (key_id {ed_key_id(pub)[:16]}...) "
                                         f"coverage={coverage}, third-party verifiable, no secret "
                                         f"involved{note}"})
        elif algo == ALGORITHM:
            # Structural consistency before anything else: an HMAC seal has no
            # public key, so a seal that carries one is relabelled (algorithm
            # confusion, red-team RT04). Refuse it instead of reporting the softer
            # "cannot check without a key".
            if seal.get("public_key"):
                ok = False
                checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                               "detail": "seal declares HMAC-SHA256 but carries a "
                                         "public_key - algorithm confusion / relabelled seal"})
            elif key is not None:
                kid = key_id(key)
                if seal.get("key_id") != kid:
                    ok = False
                    checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                                   "detail": "key mismatch: seal was not created by this key "
                                             "(possible key substitution or wrong key)"})
                else:
                    sig = seal.get("signature", "")
                    coverage = None
                    if lifecycle and seal_verify(key, identity, manifest, sig, lifecycle):
                        coverage = "lifecycle-bound"
                    elif seal_verify(key, identity, manifest, sig):
                        coverage = "legacy"
                    if coverage is None:
                        ok = False
                        checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                                       "detail": "signature invalid: identity/manifest/lifecycle "
                                                 "do not match the seal"})
                    else:
                        assurance = "owner-key"
                        checks.append({"id": "S6", "name": "seal signature", "result": "PASS",
                                       "detail": f"HMAC-SHA256 seal valid (key_id {kid[:16]}..., "
                                                 f"coverage={coverage})"})
            else:
                checks.append({"id": "S6", "name": "seal signature", "result": "INCONCLUSIVE",
                               "detail": "HMAC seal present but no verification key provided "
                                         "(--key); symmetric seals cannot be checked publicly - "
                                         "an Ed25519 seal can"})
        else:
            ok = False
            checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                           "detail": f"unknown seal algorithm {algo!r}"})
    elif key is not None:
        ok = False
        checks.append({"id": "S6", "name": "seal signature", "result": "FAIL",
                       "detail": "strict mode (--key): package is unsigned - "
                                 "owner demands a sealed submission"})
    else:
        checks.append({"id": "S6", "name": "seal signature", "result": "INCONCLUSIVE",
                       "detail": "package unsigned: evidence chain is internally consistent "
                                 "but provenance is unattested"})

    # Three-valued top-level verdict (seal v0.3): a FAIL anywhere fails the
    # package; an unresolved INCONCLUSIVE anywhere caps the verdict at
    # INCONCLUSIVE - PASS is reserved for packages every check resolved.
    _results = [c["result"] for c in checks]
    if "FAIL" in _results:
        result = "FAIL"
    elif "INCONCLUSIVE" in _results:
        result = "INCONCLUSIVE"
    else:
        result = "PASS"

    if assurance == "public-key":
        # An Ed25519 seal carries its own public key, so a plain open-mode
        # verify uses a key the artifact itself supplies: internally
        # consistent, not anchored. Only --pubkey - a channel the artifact
        # does not control - earns "anchored".
        trust_level = "anchored" if pubkey is not None else "unanchored"
    elif assurance == "owner-key":
        trust_level = "anchored"
    else:
        trust_level = "unattested"

    return {
        "verifier_id": VERIFIER_ID,
        "verifier_version": __version__,
        "spec_version": SPEC_VERSION,
        "spec_id": _SPEC_ID,
        "result": result,
        # Anchor rule (draft-maintainer-1f916-agent-record-01 Section 3.6):
        # "A verification run is ANCHORED only when at least one key reached
        # the verifier through a channel the artifact does not control." A
        # key read out of the package proves internal consistency and nothing
        # more, so it must not be reported as if it were provenance.
        "trust_level": trust_level,
        "key_custody": identity.get("key_custody"),
        "subject": manifest.get("agent_id"),
        "checks": checks,
        "root_algorithm": "sha256(canonical-json(sorted(content_hashes))) v0.1-provisional",
        "assurance": assurance,
        # --- report discipline (archive SS16) ---
        "scope": "Structure, identity consistency, lifecycle state machine, evidence "
                 "content hashes, evidence root, and the seal signature of this "
                 "submission package only. Ed25519 seals are verified publicly in "
                 "every mode; HMAC seals only in strict --key mode.",
        "limitations": [
            "HMAC-SHA256 seals (v0.2) are symmetric: verification requires the owner "
            "key. Ed25519 seals (v0.3) are third-party verifiable with the public key "
            "recorded in the seal.",
            "Anchor rule: in open mode the seal's public key is read out of the "
            "package under test, so a passing signature proves internal consistency "
            "only ('unanchored'). 'anchored' requires an out-of-band key (--pubkey).",
            "There is no independent witness or transparency-log countersignature, so "
            "even an anchored run cannot reach the 'witnessed' strength. Truncation is "
            "caught by the S8 checkpoint, and rollback only by S9 with a head observed "
            "outside the package (--expect-head): nothing inside a package can detect "
            "being replaced by an older self-consistent one.",
            "Key substitution is detectable only when verifying with the owner key "
            "(--key), a pinned public key (--pubkey), or out-of-band key pinning.",
            "Evidence Root algorithm is provisional (pending canonical serialization ratification).",
            "Timestamps are not independently anchored.",
            "Lifecycle event signatures (event.signature) are not ratified and not verified.",
            "No behavioral evaluation is performed (Evaluation is out of verifier scope, archive SS15).",
        ],
        "checked": ["structure", "identity", "lifecycle", "evidence hashes", "evidence root"]
                   + (["seal signature"] if has_seal or key is not None else []),
        "not_checked": ["lifecycle event signatures",
                        "external timestamp anchoring",
                        "behavioral evaluation", "memory fidelity/continuity"],
        "statement": ("No violation was detected within the observed evidence boundary."
                      if result == "PASS" else
                      "Violations were detected within the observed evidence boundary."
                      if result == "FAIL" else
                      "No violation was detected, but verification is incomplete: at "
                      "least one check could not be resolved within the observed "
                      "evidence boundary."),
    }


def verify(package_dir: str, key: bytes = None, pubkey: bytes = None,
           expect_head: str = None) -> dict:
    """Fail-closed wrapper: a verifier must return a verdict, never crash.

    Red-team RT06 put a NaN into manifest.json. json accepts NaN, RFC 8785 does
    not, so the canonicalizer raised inside S6 and the caller got a traceback.
    A crash is not a verdict - and an attacker who can choose which inputs
    crash the verifier can also choose which inputs never get reported.
    """
    try:
        return _verify_impl(package_dir, key=key, pubkey=pubkey,
                            expect_head=expect_head)
    except Exception as e:  # noqa: BLE001 - hostile input of any shape
        return {
            "verifier_id": VERIFIER_ID,
            "verifier_version": __version__,
            "spec_version": SPEC_VERSION,
        "spec_id": _SPEC_ID,
            "result": "FAIL",
            "trust_level": "unattested",
            "key_custody": None,
            "subject": None,
            "checks": [{"id": "S0", "name": "verifier robustness",
                        "result": "FAIL",
                        "detail": f"{type(e).__name__}: {str(e)[:120]} - the package "
                                  "could not be processed; treated as a violation, "
                                  "never as a pass"}],
            "root_algorithm": "sha256(canonical-json(sorted(content_hashes))) v0.1-provisional",
            "assurance": "unattested",
            "scope": "Verifier robustness only: the package could not be processed.",
            "limitations": ["No check could be completed on this input."],
            "checked": [],
            "not_checked": ["everything"],
            "statement": "Input rejected before any check could complete.",
        }
