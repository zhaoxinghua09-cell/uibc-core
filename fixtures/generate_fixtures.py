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

EXPECTED_OPEN = {
    "clean": "PASS (S6 INCONCLUSIVE: seal present, no key)",
    "tampered": "FAIL (S4 hash mismatch, S5 INCONCLUSIVE)",
    "deleted": "FAIL (S4 missing file, S5 INCONCLUSIVE)",
    "duplicated": "FAIL (S4 PASS, S5 root mismatch)",
    "reordered": "FAIL (S3 lifecycle L1/L4 violations)",
    "migrated": "FAIL (S4 PASS, S5 root mismatch)",
    "malicious": "open mode: S6 INCONCLUSIVE -> overall PASS (integrity unchecked "
                 "cryptographically; use --key for strict)",
    "malicious-keyswap": "open mode: S6 INCONCLUSIVE -> overall PASS "
                         "(key substitution UNDETECTABLE without the owner key)",
}

EXPECTED_STRICT = {
    "clean": "PASS (S6 PASS: owner seal valid)",
    "tampered": "FAIL (S4 + S6 signature invalid)",
    "deleted": "FAIL (S4 + S6 signature invalid)",
    "duplicated": "FAIL (S5 root mismatch + S6 signature invalid)",
    "reordered": "FAIL (S3 + S6 signature invalid)",
    "migrated": "FAIL (S5 root mismatch + S6 signature invalid)",
    "malicious": "FAIL (S6 signature invalid - forgery without the owner key is impossible)",
    "malicious-keyswap": "FAIL (S6 key mismatch: attacker key != owner key)",
}


def main():
    results = []
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
        failed_open = [f"{c['id']}:{c['result']}" for c in r_open["checks"] if c["result"] not in ("PASS", "SKIP")]
        failed_strict = [f"{c['id']}:{c['result']}" for c in r_strict["checks"] if c["result"] != "PASS"]
        results.append({
            "fixture": f"{name}.uibc",
            "open": r_open["result"],
            "strict": r_strict["result"],
            "attacker_key": r_attack["result"],
            "non_pass_open": ", ".join(failed_open) if failed_open else "-",
            "non_pass_strict": ", ".join(failed_strict) if failed_strict else "-",
        })
        print(f"{name:18s} open={r_open['result']:5s} strict={r_strict['result']:5s} "
              f"{', '.join(failed_strict) if failed_strict else 'all PASS'}")

    # write EXPECTED.md (archive SS31 fields)
    rows = []
    for r in results:
        name = r["fixture"].replace(".uibc", "")
        rows.append(
            f"| FIX-{name.upper():17s} | evidence boundary manipulation | "
            f"{name} | open: {EXPECTED_OPEN[name]}<br>strict: {EXPECTED_STRICT[name]} | "
            f"open: **{r['open']}** ({r['non_pass_open']})<br>strict: **{r['strict']}** ({r['non_pass_strict']}) | "
            f"attacker-key verify: **{r['attacker_key']}** | "
            f"uibc-core verifier {__version__} |"
        )
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

| Fixture | Threat Model | Target | Expected | Observed | Evidence | Verifier Version |
|---------|--------------|--------|----------|----------|----------|------------------|
{chr(10).join(rows)}

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

## Scope statement (archive SS17)

These fixtures demonstrate detection within the observed evidence boundary of
the v0.2 verifier. They do not prove the absence of undetected attacks.
"""
    with open(os.path.join(HERE, "EXPECTED.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("\nEXPECTED.md written")


if __name__ == "__main__":
    main()
