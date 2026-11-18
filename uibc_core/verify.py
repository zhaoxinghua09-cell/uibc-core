"""Verifier (archive SS16): PASS / FAIL / INCONCLUSIVE, scoped report.

Report discipline (archive SS16/SS17):
  - report MUST state scope, limitations, checked, not_checked
  - result is a scoped proof: "No unauthorized action was detected within the
    observed evidence boundary" - never a claim of absolute trustworthiness.
"""

import json
import os
import re
from datetime import datetime, timedelta, timezone

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
_SHA256_ONLY = re.compile(r"^(sha256:)?[0-9a-f]{64}$")

# draft-sharif-agent-audit-trail-03 Section 13.6: any component left outside the
# attested set is a forgery channel. Declared, not verified - see S10.
CLOSURE_FIELDS = ("model_weights", "tokenizer", "chat_template", "engine_build",
                  "decoding", "numeric_env")

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


# S11 strict serialization (v1.1). Motivated by vectors the AER-1 conformance
# corpus treats as must-fail and a plain json.load() silently accepts:
#   * duplicate member names - RFC 8259 leaves it undefined, Python keeps the
#     LAST one, so "{\"a\":1,\"a\":0}" verifies as if it said 0 while a reader
#     sees 1 - a two-reader split, which is worse than either value;
#   * raw control characters - invisible in an editor, meaningful to a parser;
#   * bytes that are not valid UTF-8 - the spec is UTF-8 or it is nothing.
# These are encoding-level, so they are checked on the bytes before any digest
# comparison: a package that fails here must not reach the hash checks at all.
_S11_FILES = ("manifest.json", "identity.json", "lifecycle.json",
              "evidence/index.json")


def _strict_scan(path):
    """Return a list of problems found by re-reading the file as bytes."""
    problems = []
    dups = []

    def hook(pairs):
        seen = set()
        for k, _ in pairs:
            if k in seen:
                dups.append(k)
            seen.add(k)
        return dict(pairs)

    try:
        with open(path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return problems
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return ["not valid UTF-8"]
    try:
        json.loads(text, object_pairs_hook=hook)
    except ValueError as e:
        problems.append("not parseable JSON (%s)" % e)
    for name in dups:
        problems.append("duplicate member name %r" % name)
    for ch in text:
        if ord(ch) < 0x20 and ch not in "\t\n\r":
            problems.append("raw control character U+%04X" % ord(ch))
            break
    return problems


RFC3339 = re.compile(
    r"^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(\.\d+)?(Z|[+-]\d{2}:\d{2})$")
UUID_FORM = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                       r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")
TIME_KEYS = {"timestamp", "created_at", "updated_at", "at", "issued_at",
             "effective_at", "observed_at"}
ID_KEYS = {"agent_id", "event_id", "id", "owner", "logical_agent_id"}


def _calendar_ok(y, m, d):
    """True iff the date exists. 1900 is deliberately NOT a leap year."""
    if not (1 <= m <= 12 and 1 <= d <= 31):
        return False
    days = [31, 29 if (y % 4 == 0 and (y % 100 != 0 or y % 400 == 0)) else 28,
            31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
    return d <= days[m - 1]


def _offset_ok(off):
    if off == "Z":
        return True
    hh, mm = int(off[1:3]), int(off[4:6])
    return hh <= 14 and mm < 60 and not (hh == 14 and mm)


def _now_utc():
    """Verifier clock, isolated so tests and callers can reason about it."""
    return datetime.now(timezone.utc)


def _semantic_problems(obj, path="", now=None, future_skew_s=300):
    """S12: timestamps and identifiers, judged on values rather than on hashes.

    Why a separate check: S4/S5/S7 all answer "was this byte changed?" - none of
    them answers "is this value a legal time?". A log whose timestamps are
    '2026-11-17T05:59:59' (no zone), 'feb29 1900', or a lowercase 't' hashes
    perfectly and orders nothing. AER-1's corpus treats those as must-fail; we
    had no counterpart before this check.

    Policy choices, stated so they can be argued with:
      * leap second (":60") is REJECTED - evidence timestamps are machine
        generated, and a leap second in an evidence log has no defensible
        ordering meaning;
      * UUID-shaped identifiers must be lowercase and non-nil - two readers must
        not disagree about whether 'ABC...' and 'abc...' are the same device;
      * non-UUID identifiers (e.g. 'mb-agent-001') are left alone: our schema
        allows them, so rejecting them would be a false positive.
      * a timestamp more than 300 s ahead of the verifier's own clock is
        REJECTED (draft-marques-asqav-compliance-receipts-01 4.1.2), while
        a past timestamp is never rejected on age alone: an evidence log
        that stops verifying once it is old is not an evidence log.
        The bound is a parameter so a test can move the clock instead of
        sleeping.
    """
    problems = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            child = path + "/" + str(k) if path else str(k)
            if k in TIME_KEYS and isinstance(v, str):
                m = RFC3339.match(v)
                if not m:
                    problems.append("%s: %r is not RFC 3339 (needs uppercase T, "
                                    "a timezone, full seconds)" % (child, v[:40]))
                else:
                    y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
                    if not _calendar_ok(y, mo, d):
                        problems.append("%s: %r is not a real calendar date"
                                        % (child, v[:40]))
                    if int(m.group(6)) > 59:
                        problems.append("%s: %r has a leap second; not accepted "
                                        "in evidence timestamps" % (child, v[:40]))
                    if not _offset_ok(m.group(8)):
                        problems.append("%s: %r has an out-of-range UTC offset"
                                        % (child, v[:40]))
                    if now is not None:
                        # A record dated in the future is not "fresh": it is a
                        # claim about a clock the producer does not control. The
                        # bound is one-sided on purpose - see the policy note
                        # above about past timestamps.
                        try:
                            ts = datetime.fromisoformat(v.replace("Z", "+00:00"))
                        except ValueError:
                            ts = None
                        if ts is not None:
                            if ts.tzinfo is None:
                                ts = ts.replace(tzinfo=timezone.utc)
                            ahead = (ts - now).total_seconds()
                            if ahead > future_skew_s:
                                problems.append(
                                    "%s: %r is %.0f s in the future; the accepted "
                                    "lead of the verifier's clock is %d s"
                                    % (child, v[:40], ahead, future_skew_s))
            if k in ID_KEYS and isinstance(v, str) and UUID_FORM.match(v):
                if v != v.lower():
                    problems.append("%s: %r is an uppercase UUID" % (child, v))
                if v.replace("-", "").strip("0") == "":
                    problems.append("%s: %r is the nil UUID" % (child, v))
            if k in ID_KEYS and isinstance(v, str) and not UUID_FORM.match(v):
                # v1.1: an identifier is bytes, not text. A trailing newline or
                # padding space makes two identifiers that print identically
                # compare differently - the exact cause of the AER-1 corpus
                # classes the corpus calls id-trailing-newline / provenance-trailing-newline.
                if v != v.strip() or any(ord(c) < 0x21 for c in v):
                    problems.append("%s: identifier %r has surrounding whitespace "
                                    "or a control character" % (child, v[:40]))
            problems.extend(_semantic_problems(v, child, now=now,
                                            future_skew_s=future_skew_s))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            problems.extend(_semantic_problems(
                v, "%s[%d]" % (path, i), now=now,
                future_skew_s=future_skew_s))
    return problems


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

    # S11 strict serialization runs FIRST, before any parse: if the bytes are not
    # UTF-8, or carry a duplicate member name, the later checks must not be the
    # ones that notice. Recorded here so the report still names the encoding
    # problem even when json.load would have raised and the fail-closed wrapper
    # would have collapsed everything into S0.
    s11_problems = []
    for rel in _S11_FILES:
        for problem in _strict_scan(os.path.join(package_dir, rel)):
            s11_problems.append("%s: %s" % (rel, problem))
    record("S11", "strict serialization", not s11_problems,
           "; ".join(s11_problems[:4]) if s11_problems else
           "UTF-8, no duplicate member names, no raw control characters")

    def _safe_load(rel):
        try:
            return _load_json(os.path.join(package_dir, rel))
        except Exception:
            return {}

    # S1 structure: required files present AND nothing undeclared inside the
    # package directory (v1.1 fix F4). Before this, a notes.md / README that
    # contradicted the evidence could sit in the package root and no check
    # noticed - one of the 18 mutations was accepted that way.
    missing = [f for f in REQUIRED_FILES if not os.path.isfile(os.path.join(package_dir, f))]

    manifest = _safe_load("manifest.json") if not missing else {}
    identity = _safe_load("identity.json") if not missing else {}
    lifecycle = _safe_load("lifecycle.json") if not missing else {}
    index = (_safe_load("evidence/index.json") if not missing else {"entries": []}) or {"entries": []}

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
    # Containment: an evidence entry must resolve to a real file inside evidence/.
    # Without this a package can put a symlink at evidence/files/x and have us hash
    # something that lives outside the package (RT03 in tools/redteam_suite.py hit
    # exactly that on 2026-11-17: the verifier returned PASS).
    evidence_dir_real = os.path.realpath(os.path.join(package_dir, "evidence"))
    for e in entries:
        p = os.path.join(package_dir, "evidence", e.get("path", ""))
        if not os.path.isfile(p):
            s4_failures.append(f"missing file {e.get('path')!r}")
            continue
        real = os.path.realpath(p)
        if os.path.islink(p) or not (real == evidence_dir_real or
                                     real.startswith(evidence_dir_real + os.sep)):
            s4_failures.append(
                f"evidence file {e.get('path')!r} resolves outside the evidence root")
            continue
        actual = hash_file(p)
        recomputed_hashes.append(actual)
        if actual != e.get("content_hash"):
            s4_failures.append(f"hash mismatch on {e.get('path')!r}")
        if e.get("type") not in EVIDENCE_TYPES:
            s4_failures.append(f"unknown evidence type {e.get('type')!r}")
    record("S4", "evidence integrity", not s4_failures,
           f"{len(entries)} entries checked; " + ("; ".join(s4_failures) if s4_failures else "all hashes match"))

    # S12 semantic strictness: timestamps must be real, ordered things and
    # identifiers must be canonical. Runs on the parsed values, so it is
    # deliberately separate from S11 (which runs on the bytes).
    s12_problems = []
    for doc_name, doc in (("manifest.json", manifest), ("identity.json", identity),
                          ("lifecycle.json", lifecycle),
                          ("evidence/index.json", index)):
        for problem in _semantic_problems(doc, now=_now_utc()):
            s12_problems.append("%s: %s" % (doc_name, problem))
    record("S12", "timestamp and identifier strictness", not s12_problems,
           "; ".join(s12_problems[:4]) if s12_problems else
           "timestamps are RFC 3339 with a zone; UUIDs are lowercase and non-nil")

    # S13 Merkle inclusion (v1.1). A hash chain answers "was file N changed?";
    # a Merkle tree answers "is this one file inside a set of size N that the
    # manifest committed to, without handing over all N files?". The class had
    # no counterpart in our code at all. Runs only when the package carries
    # evidence/merkle.json - a package with no tree is not penalised for it.
    merkle_file = os.path.join(package_dir, "evidence", "merkle.json")
    if os.path.isfile(merkle_file):
        from . import merkle as _mk
        mdoc = _load_json(merkle_file)
        s13_problems = []
        order = sorted(entries, key=lambda e: e.get("path", ""))
        leaves = []
        for e in order:
            p = os.path.join(package_dir, "evidence", e.get("path", ""))
            try:
                with open(p, "rb") as fh:
                    leaves.append(_mk.leaf_hash(fh.read()))
            except OSError:
                s13_problems.append("cannot read evidence file %r" % e.get("path"))
        root = _mk.root_hash(leaves)
        if mdoc.get("algorithm") != "rfc6962-sha256":
            s13_problems.append("algorithm %r is not rfc6962-sha256"
                                % mdoc.get("algorithm"))
        if mdoc.get("size") != len(leaves):
            s13_problems.append("declared size %r != %d evidence leaves"
                                % (mdoc.get("size"), len(leaves)))
        if str(mdoc.get("root", "")).lower() != root.hex():
            s13_problems.append("declared root does not match recomputed root")
        proofs = mdoc.get("proofs") or []
        for pr in proofs:
            idx = pr.get("index")
            path = pr.get("path")
            want = [e for e in order if e.get("path") == path]
            if not want:
                s13_problems.append("proof names unknown evidence %r" % path)
                continue
            i = order.index(want[0])
            if idx is not None and idx != i:
                s13_problems.append("proof index for %r is %r, recomputed %d"
                                    % (path, idx, i))
            try:
                pf = [bytes.fromhex(h) for h in (pr.get("proof") or [])]
            except ValueError:
                s13_problems.append("proof for %r has a non-hex sibling" % path)
                continue
            if not _mk.verify_inclusion(leaves[i], i, len(leaves), pf, root):
                s13_problems.append("inclusion proof for %r does not verify" % path)
        record("S13", "merkle inclusion proofs", not s13_problems,
               "; ".join(s13_problems[:4]) if s13_problems else
               "root %s... over %d leaves; %d inclusion proofs verified"
               % (root.hex()[:16], len(leaves), len(proofs)))

    # S14 strict base64 (v1.1). "Signature verifies" and "two decoders disagree
    # about the bytes" are not exclusive: pad bits, missing padding and stray
    # characters all decode permissively. Runs only on fields the package
    # itself marks as base64 (keys ending _b64 / _base64 or named 'base64'),
    # so a schema that does not use base64 cannot be false-flagged.
    def _b64_fields(obj, path=""):
        found = []
        if isinstance(obj, dict):
            for k, v in obj.items():
                child = "%s/%s" % (path, k) if path else str(k)
                if isinstance(v, str) and (str(k).endswith("_b64")
                                           or str(k).endswith("_base64")
                                           or str(k) == "base64"):
                    found.append((child, v, str(k) == "base64_url"))
                else:
                    found.extend(_b64_fields(v, child))
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                found.extend(_b64_fields(v, "%s[%d]" % (path, i)))
        return found

    from . import encoding as _enc
    b64_problems = []
    b64_count = 0
    for doc_name, doc in (("manifest.json", manifest), ("identity.json", identity),
                          ("lifecycle.json", lifecycle),
                          ("evidence/index.json", index)):
        for field, value, urlsafe in _b64_fields(doc):
            b64_count += 1
            for problem in _enc.problems(value, urlsafe=urlsafe):
                b64_problems.append("%s:%s %s" % (doc_name, field, problem))
    if b64_count:
        record("S14", "strict base64", not b64_problems,
               "; ".join(b64_problems[:4]) if b64_problems else
               "%d declared base64 field(s) are canonical" % b64_count)

    # S15 anchor event resolution (v1.1). S9 answers "is the head pinned
    # out-of-band?"; it cannot answer "can I resolve this anchor to a leaf in a
    # set I can recompute myself?". Runs only when the package carries
    # evidence/anchors.json. An anchor naming an external log stays unresolved
    # rather than being counted as checked: "I could not verify" is not "OK".
    anchors_file = os.path.join(package_dir, "evidence", "anchors.json")
    if os.path.isfile(anchors_file):
        from . import anchor as _anchor
        from . import merkle as _mk2
        adoc = _load_json(anchors_file)
        leaves = []
        for e in sorted(entries, key=lambda x: x.get("path", "")):
            p = os.path.join(package_dir, "evidence", e.get("path", ""))
            try:
                with open(p, "rb") as fh:
                    leaves.append(_mk2.leaf_hash(fh.read()))
            except OSError:
                leaves = None
                break
        aroot = _mk2.root_hash(leaves) if leaves else None
        a_problems, a_resolved, a_external = _anchor.check_document(
            adoc, root=aroot, leaves=leaves)
        record("S15", "anchor event resolution", not a_problems,
               "; ".join(a_problems[:3]) if a_problems else
               "%d anchor(s) resolved against the evidence Merkle root; "
               "%d external anchor(s) unresolved by design" % (a_resolved, a_external))

    # S16 external timestamp (v1.1). Everything above is witnessed by parties we
    # choose: our tree, our head file, our pin. An RFC 3161 token is the one
    # witness we cannot mint ourselves - it dates a digest with a key held by a
    # third party. Runs only when the package carries evidence/external_anchor.json,
    # and an unjudgeable token is INCONCLUSIVE, never PASS.
    ext_file = os.path.join(package_dir, "evidence", "external_anchor.json")
    if os.path.isfile(ext_file):
        from . import tsa as _tsa
        ext = _load_json(ext_file)
        ext_problems = []
        if not _tsa.HAVE_ASN1:
            checks.append({"id": "S16", "name": "external timestamp (RFC 3161)",
                           "result": "INCONCLUSIVE",
                           "detail": "verifier lacks asn1crypto; a token in the package "
                                     "cannot be judged, so it is not counted as checked"})
            ok = False
        else:
            rel_data = ext.get("digest_of") or "manifest.json"
            data_path = os.path.join(package_dir, rel_data)
            tsr_path = ext.get("tsr") or ""
            ca_path = ext.get("cabundle") or ""
            body = b""
            cabundle = b""
            try:
                with open(data_path, "rb") as fh:
                    data_bytes = fh.read()
            except OSError:
                data_bytes = None
                ext_problems.append("cannot read anchored file %r" % rel_data)
            try:
                with open(os.path.join(package_dir, tsr_path), "rb") as fh:
                    body = fh.read()
            except OSError:
                ext_problems.append("cannot read token %r" % tsr_path)
            try:
                with open(os.path.join(package_dir, ca_path), "rb") as fh:
                    cabundle = fh.read()
            except OSError:
                ext_problems.append("cannot read CA bundle %r" % ca_path)

            declared_tsr_sha = ext.get("tsr_sha256")
            if body and declared_tsr_sha:
                import hashlib as _hl
                if _hl.sha256(body).hexdigest() != declared_tsr_sha:
                    ext_problems.append("token digest is not the declared tsr_sha256")

            ext_info = {}
            if not ext_problems and data_bytes is not None:
                import hashlib as _hl
                v_ok, ext_info, v_problems = _tsa.verify_token(
                    body, _hl.sha256(data_bytes).digest(), cabundle)
                if not v_ok:
                    ext_problems.extend(v_problems)

            if ext_problems:
                record("S16", "external timestamp (RFC 3161)", False,
                       "; ".join(ext_problems[:3]))
            else:
                record("S16", "external timestamp (RFC 3161)", True,
                       "token dates %r at %s (%s, serial %s); signature verified offline"
                       % (rel_data, ext_info.get("gen_time"),
                          (ext_info.get("tsa") or {}).get("organization_name")
                          if isinstance(ext_info.get("tsa"), dict) else "TSA",
                          ext_info.get("serial")))

    # S17 linear receipt chain (v1.1). S8/S9/S13 all commit a TREE: they answer
    # "was this byte changed" and "is this leaf inside the set". None of them
    # answers "is this record the successor of that record", which is what a
    # regulator asks when one receipt is pulled out of the middle of a stream.
    # draft-marques-asqav-compliance-receipts-01 section 4.3 makes the linear
    # link mandatory (previousReceiptHash over the JCS of the predecessor) and
    # section 8 requires the verifier to recompute it. Runs only when the
    # package carries evidence/chain.json.
    chain_file = os.path.join(package_dir, "evidence", "chain.json")
    if os.path.isfile(chain_file):
        from . import chain as _chain
        cdoc = _load_json(chain_file)
        c_problems, c_checked = _chain.check_chain(cdoc)
        record("S17", "linear receipt chain", not c_problems,
               "; ".join(c_problems[:3]) if c_problems else
               "%d receipt(s) linked by previousReceiptHash over JCS; "
               "genesis is 64 zeros" % c_checked)

    # S18 policy artefact resolution (v1.1). A `policy_digest` nobody can
    # resolve is a number, not evidence. draft-marques-asqav-compliance-receipts-01
    # section 8 makes the verifier reject a receipt whose digest does not
    # resolve, and section 4.2.4 defines the value as SHA-256 over the JCS of a
    # retained artefact. Runs only when the package carries
    # evidence/policies.json; any policy_digest declared in evidence/chain.json
    # must resolve there.
    policies_file = os.path.join(package_dir, "evidence", "policies.json")
    if os.path.isfile(policies_file):
        from . import policy as _policy
        pdoc = _load_json(policies_file)
        required = []
        if os.path.isfile(chain_file):
            required = _policy.declared_digests(_load_json(chain_file))
        p_problems, p_resolved = _policy.check_policies(
            package_dir, pdoc, required_digests=required)
        record("S18", "policy artefact resolution", not p_problems,
               "; ".join(p_problems[:3]) if p_problems else
               "%d policy artefact(s) resolve to their declared SHA-256 over "
               "JCS; %d digest(s) referenced by receipts resolved"
               % (p_resolved, len(required)))

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

    # S10 attestation closure (draft-sharif-agent-audit-trail-03 Section 13.6).    # AAT's point is that any component left outside the attested set is a
    # forgery channel: weights, tokenizer, chat template, engine build, decoding
    # configuration, numeric environment. We can only check that a submitter
    # DECLARED all six and gave each a digest; whether those digests correspond
    # to what actually ran is not decidable from a package, and saying otherwise
    # would be the exact overclaim this project refuses elsewhere.
    closure = manifest.get("closure")
    if closure is not None:
        missing = []
        if not isinstance(closure, dict):
            missing = ["closure is not an object"]
        else:
            for k in CLOSURE_FIELDS:
                v = closure.get(k)
                if not isinstance(v, str) or not _SHA256_ONLY.match(v):
                    missing.append(k)
        if missing:
            ok = False
            checks.append({"id": "S10", "name": "attestation closure declared",
                           "result": "FAIL",
                           "detail": "closure is incomplete or malformed: "
                                     + ", ".join(missing)})
        else:
            checks.append({"id": "S10", "name": "attestation closure declared",
                           "result": "PASS",
                           "detail": "all 6 closure components declared with digests "
                                     "(declaration only, contents are not verified)"})

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
