"""Golden Fixtures generator (archive SS30): benchmark as executable evidence.

Eight mutation categories (archive SS30 + v0.2 addition):
  clean / tampered / deleted / duplicated / reordered / migrated / malicious
  / malicious-keyswap

Each fixture is a submission.uibc package. The generator builds a clean SIGNED
base package (seal = HMAC-SHA256 over identity+manifest, v0.2), then applies
one mutation per category, runs the verifier on every fixture in BOTH modes
(open, and strict with the owner key), and records expected vs observed
results in EXPECTED.md (fields follow archive SS31: Threat Model / Target /
Mutation / Expected / Observed / Evidence / Verifier Version).

Honesty notes (Break UIBC discipline, archive SS31):
- v0.1 finding (kept for history): the 'malicious' forgery passed the v0.1
  verifier (no signatures). v0.2 strict mode (--key) now FAILS it at S6.
- 'malicious-keyswap' is the remaining known boundary: an attacker with their
  own key can re-sign a stolen package. Open mode: INCONCLUSIVE/PASS. Strict
  mode with the OWNER key: FAIL (key mismatch). Strict mode with the
  ATTACKER key: PASS - which is exactly why out-of-band key pinning matters,
  and why Ed25519 + a registry is the v0.3 target.

Usage:
    python fixtures/generate_fixtures.py
"""

import json
import os
import shutil
import sys
import uuid
from argparse import Namespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core.canonical import evidence_root, hash_file
from uibc_core.signing import key_id, seal_sign
from uibc_core.verify import verify
from uibc_core import cli as ucli
from uibc_core import __version__

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import _matrix_gate as _mg  # noqa: E402  (needs HERE on sys.path first)

FIXTURES = ["clean", "tampered", "deleted", "duplicated", "reordered",
            "migrated", "malicious", "malicious-keyswap"]

# Owner key: generated once per generator run. The forged fixtures do NOT
# have it - that is the whole point.
OWNER_KEY = os.urandom(32)
ATTACKER_KEY = os.urandom(32)

ACTION_V1 = "agent fx-agent executed db:read; result: 42 rows; reviewed by owner\n"
ACTION_V2 = "agent fx-agent executed db:read; result: 77 rows (post-migration); reviewed by owner\n"
SUMMARY = "run summary: 2 evidence items, lifecycle REGISTER->ACTIVATE->UPDATE\n"


def _ns(**kw):
    return Namespace(**kw)


def build_base(pkg: str):
    """Build a clean sealed package via the real CLI functions (no shortcuts)."""
    ucli.cmd_init(_ns(path=pkg))
    ucli.cmd_register(_ns(path=pkg, agent_id="fx-agent-001", owner="fixture-owner",
                          agent_type="software-agent", version="0.1.0"))
    ucli.cmd_event(_ns(path=pkg, type="ACTIVATE", actor="fixture-owner"))
    ucli.cmd_event(_ns(path=pkg, type="UPDATE", actor="fixture-owner"))
    src1 = os.path.join(HERE, "action-log.txt")
    src2 = os.path.join(HERE, "run-summary.txt")
    with open(src1, "w", encoding="utf-8") as f:
        f.write(ACTION_V1)
    with open(src2, "w", encoding="utf-8") as f:
        f.write(SUMMARY)
    ucli.cmd_evidence(_ns(path=pkg, type="ACTION", file=src1,
                          media_type="text/plain", note="action log"))
    ucli.cmd_evidence(_ns(path=pkg, type="OUTPUT", file=src2,
                          media_type="text/plain", note="run summary"))
    os.remove(src1)
    os.remove(src2)
    ucli.cmd_submit(_ns(path=pkg, key=None))  # unsigned intermediate
    # sign the seal with the owner key (v0.2): identity+manifest are already
    # written by cmd_submit, so sign what is on disk (single source of truth)
    identity = _read(os.path.join(pkg, "identity.json"))
    manifest = _read(os.path.join(pkg, "manifest.json"))
    sig_dir = os.path.join(pkg, "signatures")
    os.makedirs(sig_dir, exist_ok=True)
    _write(os.path.join(sig_dir, "seal.json"), {
        "schema": "uibc-core/0.2.0-proposal",
        "algorithm": "HMAC-SHA256",
        "key_id": key_id(OWNER_KEY),
        "signed": "identity+manifest",
        "signature": seal_sign(OWNER_KEY, identity, manifest),
        "created_at": "fixture",
    })


def _read(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# --- mutations: each takes the package dir of a COPY of the clean base -------

def mut_tampered(pkg):
    """ATTACK-002 Evidence Tampering (archive SS31): rewrite evidence content,
    leave recorded hash stale."""
    p = os.path.join(pkg, "evidence", "files", "action-log.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write("agent fx-agent executed db:read; result: 999999 rows; reviewed by NOBODY\n")


def mut_deleted(pkg):
    """Evidence deletion (archive SS12/SS31): remove an evidence file named in
    the index."""
    os.remove(os.path.join(pkg, "evidence", "files", "run-summary.txt"))


def mut_duplicated(pkg):
    """MEM-004 Entry Duplication (archive SS29): duplicate an index entry; the
    sealed manifest root no longer matches the recomputed root."""
    idxp = os.path.join(pkg, "evidence", "index.json")
    idx = _read(idxp)
    idx["entries"].append(dict(idx["entries"][0]))  # duplicate entry
    _write(idxp, idx)


def mut_reordered(pkg):
    """MEM-005 Ordering Change (archive SS29): swap REGISTER and the event
    after it; breaks L1/L4 chain (archive SS11)."""
    lcp = os.path.join(pkg, "lifecycle.json")
    lc = _read(lcp)
    lc["events"][0], lc["events"][1] = lc["events"][1], lc["events"][0]
    _write(lcp, lc)


def mut_migrated(pkg):
    """MEM-008 Cross-Version Migration, partial (archive SS29): migrate the
    evidence content and update the index hash, but do NOT re-seal the
    manifest - the evidence root no longer matches."""
    p = os.path.join(pkg, "evidence", "files", "action-log.txt")
    with open(p, "w", encoding="utf-8") as f:
        f.write(ACTION_V2)
    idxp = os.path.join(pkg, "evidence", "index.json")
    idx = _read(idxp)
    for e in idx["entries"]:
        if e["path"].endswith("action-log.txt"):
            e["content_hash"] = hash_file(p)
    _write(idxp, idx)


def mut_malicious(pkg):
    """ATTACK-001+002+007 combined: FULL self-consistent forgery - evidence
    rewritten, index hash updated, manifest evidence_root recomputed.
    v0.1: UNDETECTED (no signatures). v0.2 strict (--key): FAIL at S6 -
    the attacker cannot recompute the owner's seal."""
    mut_migrated(pkg)
    mp = os.path.join(pkg, "manifest.json")
    m = _read(mp)
    idx = _read(os.path.join(pkg, "evidence", "index.json"))
    hashes = [e["content_hash"] for e in idx["entries"]]
    m["evidence_root"] = evidence_root(hashes)
    _write(mp, m)


def mut_malicious_keyswap(pkg):
    """ATTACK-005+007 (v0.2 addition): the attacker rewrites the package,
    re-seals the manifest, and re-signs EVERYTHING with their OWN key,
    replacing signatures/seal.json wholesale. There is no cryptography in
    the package that can distinguish them - only out-of-band knowledge of
    the OWNER key does (verify --key owner.key => S6 key mismatch)."""
    mut_malicious(pkg)
    identity = _read(os.path.join(pkg, "identity.json"))
    manifest = _read(os.path.join(pkg, "manifest.json"))
    _write(os.path.join(pkg, "signatures", "seal.json"), {
        "schema": "uibc-core/0.2.0-proposal",
        "algorithm": "HMAC-SHA256",
        "key_id": key_id(ATTACKER_KEY),
        "signed": "identity+manifest",
        "signature": seal_sign(ATTACKER_KEY, identity, manifest),
        "created_at": "fixture",
    })


MUTATIONS = {
    "tampered": mut_tampered,
    "deleted": mut_deleted,
    "duplicated": mut_duplicated,
    "reordered": mut_reordered,
    "migrated": mut_migrated,
    "malicious": mut_malicious,
    "malicious-keyswap": mut_malicious_keyswap,
}

# ---------------------------------------------------------------------------
# Prose rationale (human-readable "why"), one line per fixture per mode.
#
# v0.2.1 CORRECTION: the previous wording claimed "S4 + S6 signature invalid"
# for the evidence-content mutations. That was FALSE. A seal computed over
# identity+manifest cannot be invalidated by rewriting an evidence file, so S6
# is PASS in those cases - the detection comes from S4/S5/S3, not from the
# signature. Documenting a defence that never fired is worse than documenting
# none: it inflates apparent coverage. Corrected below and enforced by
# EXPECTED_MATRIX.
# ---------------------------------------------------------------------------
EXPECTED_OPEN = {
    "clean": "PASS (S6 INCONCLUSIVE: seal present, no key to check it with)",
    "tampered": "FAIL (S4 hash mismatch; S5 INCONCLUSIVE - root not recomputable; "
                "S6 PASS - the seal never covered evidence content)",
    "deleted": "FAIL (S4 missing evidence file; S5 INCONCLUSIVE; S6 PASS - seal untouched)",
    "duplicated": "FAIL (S4 PASS - the duplicated entry still matches its file; "
                  "S5 root mismatch; S6 PASS)",
    "reordered": "FAIL (S3 lifecycle L1/L4 violations; S6 PASS - lifecycle is outside the seal)",
    "migrated": "FAIL (S4 PASS - index hash was updated; S5 root mismatch vs the "
                "unchanged manifest; S6 PASS)",
    "malicious": "PASS in open mode (S6 INCONCLUSIVE -> integrity is unchecked "
                 "cryptographically; use --key for strict)",
    "malicious-keyswap": "PASS in open mode (S6 INCONCLUSIVE -> key substitution is "
                         "UNDETECTABLE without the owner key)",
}

EXPECTED_STRICT = {
    "clean": "PASS (S6 PASS: owner seal valid)",
    "tampered": "FAIL (S4 hash mismatch; S6 PASS - evidence content is outside seal scope)",
    "deleted": "FAIL (S4 missing file; S6 PASS - seal untouched)",
    "duplicated": "FAIL (S5 root mismatch; S6 PASS - manifest untouched)",
    "reordered": "FAIL (S3 lifecycle violation; S6 PASS - lifecycle is outside the seal)",
    "migrated": "FAIL (S5 root mismatch; S6 PASS - manifest untouched)",
    "malicious": "FAIL (S6 signature invalid - the forged manifest no longer matches the owner seal)",
    "malicious-keyswap": "FAIL (S6 key mismatch: attacker key != owner key)",
}

# ---------------------------------------------------------------------------
# Structured expectation matrix (v0.2.1): the machine-checkable prior.
#
# WHY THIS EXISTS: until v0.2.1 the Expected column above was prose and NOTHING
# compared it to Observed. A wrong sentence could sit next to a contradictory
# observation forever while the generator exited 0 (exactly what the "S4 + S6"
# wording did). Prose cannot fail; a matrix can.
#
# DISCIPLINE: every cell below was derived BY HAND from verify.py's control flow
# before being compared with observed output. It is a prior, not a recording of
# a run. A mismatch therefore means one of two real things - the verifier drifted
# or the prior was wrong - and both stop the build instead of printing quietly.
#
# Note the deliberately non-obvious cells: `clean[open]` is result=PASS while
# S6=INCONCLUSIVE (an unanswerable check must not be laundered into a pass), and
# `malicious[open]` is PASS while `malicious[strict]` is FAIL on the SAME package
# - mode, not content, decides the verdict there.
# ---------------------------------------------------------------------------
P, F, I, S = "PASS", "FAIL", "INCONCLUSIVE", "SKIP"

EXPECTED_MATRIX = {
    "clean": {
        "open":     {"result": P, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": I}},
        "strict":   {"result": P, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": P}},
        "attacker": {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": F}},
    },
    "tampered": {
        "open":     {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": F, "S5": I, "S6": I}},
        "strict":   {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": F, "S5": I, "S6": P}},
        "attacker": {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": F, "S5": I, "S6": F}},
    },
    "deleted": {
        "open":     {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": F, "S5": I, "S6": I}},
        "strict":   {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": F, "S5": I, "S6": P}},
        "attacker": {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": F, "S5": I, "S6": F}},
    },
    "duplicated": {
        "open":     {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": F, "S6": I}},
        "strict":   {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": F, "S6": P}},
        "attacker": {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": F, "S6": F}},
    },
    "reordered": {
        "open":     {"result": F, "checks": {"S1": P, "S2": P, "S3": F, "S4": P, "S5": P, "S6": I}},
        "strict":   {"result": F, "checks": {"S1": P, "S2": P, "S3": F, "S4": P, "S5": P, "S6": P}},
        "attacker": {"result": F, "checks": {"S1": P, "S2": P, "S3": F, "S4": P, "S5": P, "S6": F}},
    },
    "migrated": {
        "open":     {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": F, "S6": I}},
        "strict":   {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": F, "S6": P}},
        "attacker": {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": F, "S6": F}},
    },
    "malicious": {
        "open":     {"result": P, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": I}},
        "strict":   {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": F}},
        "attacker": {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": F}},
    },
    "malicious-keyswap": {
        "open":     {"result": P, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": I}},
        "strict":   {"result": F, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": F}},
        "attacker": {"result": P, "checks": {"S1": P, "S2": P, "S3": P, "S4": P, "S5": P, "S6": P}},
    },
}

MODES = ("open", "strict", "attacker")
CHECK_ORDER = ("S1", "S2", "S3", "S4", "S5", "S6")

# The comparison/rendering/gate logic is shared with the memory-fixtures
# generator (fixtures/_matrix_gate.py) so the two cannot drift apart. These thin
# wrappers keep this module's call sites - and its tests - unchanged.
observed_cell = _mg.observed_cell


def compare_matrix(observed: dict) -> list:
    return _mg.compare(EXPECTED_MATRIX, observed, FIXTURES, MODES)


def render_check_cell(cell: dict) -> str:
    return _mg.render_cell(cell, CHECK_ORDER)


def main():
    results = []
    observed = {}
    for name in FIXTURES:
        pkg = os.path.join(HERE, f"{name}.uibc")
        if os.path.exists(pkg):
            shutil.rmtree(pkg)
        build_base(pkg)
        if name in MUTATIONS:
            MUTATIONS[name](pkg)
        r_open = verify(pkg, key=None)
        r_strict = verify(pkg, key=OWNER_KEY)
        r_attack = verify(pkg, key=ATTACKER_KEY)  # only meaningful for keyswap
        cells = {"open": observed_cell(r_open), "strict": observed_cell(r_strict),
                 "attacker": observed_cell(r_attack)}
        for mode, cell in cells.items():
            observed[(name, mode)] = cell
        results.append({"fixture": f"{name}.uibc", "cells": cells})
        print(f"{name:18s} open={r_open['result']:5s} strict={r_strict['result']:5s} "
              f"atk={r_attack['result']:5s} | open[{render_check_cell(cells['open'])}] "
              f"strict[{render_check_cell(cells['strict'])}]")

    deviations = compare_matrix(observed)

    # write EXPECTED.md (archive SS31 fields)
    rows = []
    for r in results:
        name = r["fixture"].replace(".uibc", "")
        c = r["cells"]
        rows.append(
            f"| FIX-{name.upper():17s} | evidence boundary manipulation | "
            f"{name} | open: {EXPECTED_OPEN[name]}<br>strict: {EXPECTED_STRICT[name]} | "
            f"open: **{c['open']['result']}** `{render_check_cell(c['open'])}`<br>"
            f"strict: **{c['strict']['result']}** `{render_check_cell(c['strict'])}` | "
            f"attacker-key verify: **{c['attacker']['result']}** | "
            f"uibc-core verifier {__version__} |"
        )

    # Matrix appendix: printed straight from the prior so the document and the
    # gate cannot disagree - if this section looks wrong, the build already failed.
    mrows = []
    for name in FIXTURES:
        for mode in MODES:
            exp = EXPECTED_MATRIX[name][mode]
            mrows.append(f"| {name} | {mode} | {exp['result']} | "
                         + " ".join(f"{cid}={exp['checks'][cid]}" for cid in CHECK_ORDER) + " |")
    md = f"""# Golden Fixtures - Expected vs Observed (archive SS30/SS31)

> Benchmark as executable evidence. Generated by `generate_fixtures.py`
> (clean base built through the real CLI path, SIGNED with an HMAC-SHA256
> owner seal, one mutation per category). Verifier: uibc-core v{__version__}
> [PROPOSAL] - root algorithm: sha256(canonical-json(sorted(content_hashes)))
> v0.1-provisional.
>
> Two verification modes per fixture:
> - **open** (no key): v0.1-compatible integrity checks; a present seal is
>   reported INCONCLUSIVE (nothing to check it with).
> - **strict** (`verify --key owner.key`): owner demands a valid seal -
>   unsigned/forged/substituted packages FAIL at S6.
>
> The Observed column is machine-compared against a hand-derived expectation
> matrix (`EXPECTED_MATRIX` in the generator). Any cell mismatch aborts the
> run with a non-zero exit code: this table cannot drift silently.

| Fixture | Threat Model | Target | Expected | Observed | Evidence | Verifier Version |
|---------|--------------|--------|----------|----------|----------|------------------|
{chr(10).join(rows)}

## Expectation matrix (the gate)

Cells below are the prior the generator enforces. `result` is the overall
verdict; the rest are per-check results (S1 structure / S2 identity / S3
lifecycle / S4 evidence hashes / S5 evidence root / S6 seal signature).

| Fixture | Mode | Result | Checks |
|---------|------|--------|--------|
{chr(10).join(mrows)}

## Findings

1. v0.1 history: the fully self-consistent forgery (`malicious.uibc`) passed
   the v0.1 verifier - recorded honestly then, and it motivated v0.2.
2. **v0.2 closes that blind spot in strict mode**: without the owner key the
   forger cannot recompute the seal; `malicious` now FAILs at S6.
3. **Remaining known boundary (recorded, not hidden)**: `malicious-keyswap`
   re-signs the whole package with the ATTACKER key. It passes strict
   verification *with the attacker's key* and passes open mode - only
   verifying with the OWNER key (out-of-band pinning) detects it. This is
   the standing motivating case for Ed25519 + a public key registry (v0.3).
4. Detection is precise: each failure localizes to its check id (S3/S4/S5/S6).
5. **Seal scope is `identity+manifest` - evidence content is OUTSIDE it**
   (v0.2.1 correction): rewriting/deleting/reordering evidence never
   invalidates the seal, so S6 stays PASS for `tampered`, `deleted`,
   `duplicated`, `reordered` and `migrated`. Those are caught by S4/S5/S3
   instead. Only a mutation that rewrites the manifest itself (`malicious`)
   breaks the seal. An earlier revision of this table claimed "S4 + S6
   signature invalid" - that described a defence which never fired, and it
   has been removed. Read `S6=PASS` as "the seal was not disturbed", never as
   "the content is authentic".
6. Every cell above is enforced: the generator compares observed vs expected
   and exits non-zero on any deviation.

## Scope statement (archive SS17)

These fixtures demonstrate detection within the observed evidence boundary of
the v{__version__} verifier. They do not prove the absence of undetected attacks.
"""
    with open(os.path.join(HERE, "EXPECTED.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("\nEXPECTED.md written")

    # --- MATRIX GATE: prose cannot fail; a matrix can ------------------------
    return _mg.gate(deviations, len(FIXTURES) * len(MODES))


if __name__ == "__main__":
    sys.exit(main())
