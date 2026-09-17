"""Golden Fixtures generator (archive SS30): benchmark as executable evidence.

Seven mutation categories (archive SS30):
  clean / tampered / deleted / duplicated / reordered / migrated / malicious

Each fixture is a submission.uibc package. The generator builds a clean base
package, then applies one mutation per category, runs the verifier on every
fixture, and records expected vs observed results in EXPECTED.md
(fields follow archive SS31: Threat Model / Target / Mutation / Expected /
Observed / Evidence / Verifier Version).

Honesty note (Break UIBC discipline, archive SS31): the 'malicious' fixture is
a FULLY self-consistent forgery (evidence + index hash + manifest root all
rewritten). The v0.1 verifier has no signatures yet, so this forgery is
expected to be UNDETECTED (PASS). That observed result is recorded as-is and
is the motivating case for ratifying signatures (v0.2, archive SS10 B5).

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
from uibc_core.verify import verify
from uibc_core import cli as ucli
from uibc_core import __version__

HERE = os.path.dirname(os.path.abspath(__file__))
FIXTURES = ["clean", "tampered", "deleted", "duplicated", "reordered", "migrated", "malicious"]

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
    ucli.cmd_submit(_ns(path=pkg))


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
    v0.1 verifier has no signatures => expected UNDETECTED (PASS)."""
    mut_migrated(pkg)
    mp = os.path.join(pkg, "manifest.json")
    m = _read(mp)
    idx = _read(os.path.join(pkg, "evidence", "index.json"))
    hashes = [e["content_hash"] for e in idx["entries"]]
    m["evidence_root"] = evidence_root(hashes)
    _write(mp, m)


MUTATIONS = {
    "tampered": mut_tampered,
    "deleted": mut_deleted,
    "duplicated": mut_duplicated,
    "reordered": mut_reordered,
    "migrated": mut_migrated,
    "malicious": mut_malicious,
}

EXPECTED = {
    "clean": "PASS",
    "tampered": "FAIL (S4 hash mismatch, S5 INCONCLUSIVE)",
    "deleted": "FAIL (S4 missing file, S5 INCONCLUSIVE)",
    "duplicated": "FAIL (S4 PASS, S5 root mismatch)",
    "reordered": "FAIL (S3 lifecycle L1/L4 violations)",
    "migrated": "FAIL (S4 PASS, S5 root mismatch)",
    "malicious": "PASS - UNDETECTED by v0.1 (no signatures yet; motivates v0.2 Ed25519, archive SS10)",
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
        report = verify(pkg)
        failed = [f"{c['id']}:{c['result']}" for c in report["checks"] if c["result"] != "PASS"]
        results.append({
            "fixture": f"{name}.uibc",
            "observed": report["result"],
            "non_pass_checks": ", ".join(failed) if failed else "-",
            "statement": report["statement"],
        })
        print(f"{name:12s} -> {report['result']:5s}  {', '.join(failed) if failed else 'all checks PASS'}")

    # write EXPECTED.md (archive SS31 fields)
    rows = []
    for r in results:
        name = r["fixture"].replace(".uibc", "")
        rows.append(
            f"| FIX-{name.upper():9s} | evidence boundary manipulation | "
            f"{name} | {EXPECTED[name]} | **{r['observed']}** | {r['non_pass_checks']} | "
            f"uibc-core verifier {__version__} |"
        )
    md = f"""# Golden Fixtures - Expected vs Observed (archive SS30/SS31)

> Benchmark as executable evidence. Generated by `generate_fixtures.py`
> (clean base built through the real CLI path, one mutation per category).
> Verifier: uibc-core v{__version__} [PROPOSAL] - root algorithm:
> sha256(canonical-json(sorted(content_hashes))) v0.1-provisional.

| Fixture | Threat Model | Target | Expected | Observed | Evidence (failed checks) | Verifier Version |
|---------|--------------|--------|----------|----------|--------------------------|------------------|
{chr(10).join(rows)}

## Findings

1. Six of seven mutations are detected and precisely localized by check id.
2. **The fully self-consistent forgery (`malicious.uibc`) is UNDETECTED by
   v0.1** - expected and recorded honestly per the Break UIBC discipline
   (archive SS31). Root cause: signatures are present as fields but not
   ratified/verified in v0.1. This fixture is the standing motivating case
   for the v0.2 signature decision (archive SS10/B5, Ed25519 PROPOSAL).

## Scope statement (archive SS17)

These fixtures demonstrate detection within the observed evidence boundary of
the v0.1 verifier. They do not prove the absence of undetected attacks.
"""
    with open(os.path.join(HERE, "EXPECTED.md"), "w", encoding="utf-8") as f:
        f.write(md)
    print("\nEXPECTED.md written")


if __name__ == "__main__":
    main()
