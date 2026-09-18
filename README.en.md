# uibc-core (English)

[中文文档](README.md)

> **万物互联，数智共生** — Everything Connected, Digital-Intelligence Symbiosis.

UIBC Core reference implementation v0.2.1 **[PROPOSAL]** — agent lifecycle
evidence packages and a verifier.

Philosophy (LGD): **Registry · Evidence · Gates** → identity registration /
content-hashed evidence with a cryptographic seal / a lifecycle state machine
plus verification gates.

> ⚠️ Status: PROPOSAL, not a formal standard. Verification results are
> **scoped proofs**: PASS only means "no violation found within the observed
> evidence boundary" — it does not claim absolute trust.

## 5-minute quickstart

**30-second taste first (zero preparation):**

```bash
python -m uibc_core.cli demo   # one command: build → seal → verify PASS → tamper → FAIL caught
```

```bash
pip install -e .

# 0. generate a seal key (optional, recommended in v0.2)
uibc keygen --out owner.key    # keep it yourself; NEVER put it in the package

# 1. create a package
uibc init demo.uibc

# 2. register the agent (Registry)
uibc register demo.uibc --agent-id my-agent-001 --owner alice

# 3. lifecycle event (managed by the gate state machine)
uibc event demo.uibc --type ACTIVATE

# 4. attach evidence (SHA-256 recorded automatically)
uibc evidence demo.uibc --type ACTION --file report.txt --note "agent action log"

# 5. seal (computes the Evidence Root and writes an HMAC seal)
uibc submit demo.uibc --key owner.key

# 6. verify (gate): exit 0 = PASS
uibc verify demo.uibc --key owner.key   # strict mode: forged/key-swapped packages blocked at S6
uibc verify demo.uibc                   # open mode: integrity checks only
```

## Running the tests (the outsider reproduction kit)

```bash
python -m unittest discover tests           # full suite, 115 cases (incl. 11 MCP, 9 registry-server, 15 A2A, 9 runtime)
python -m unittest tests.stress_test        # stress suite, 7 scenarios
python independent_verifier/cross_check.py  # independent second implementation, 70 checks, 0 mismatches
```

Zero third-party dependencies. `pip install -e .` is optional (it only gives
you the short `uibc` command).

## What gets verified (v0.2 checks)

| Check | What it does |
|-------|--------------|
| S1 | package structure (manifest / identity / lifecycle / evidence index) |
| S2 | identity consistency between identity.json and manifest |
| S3 | lifecycle state machine (REGISTER first, previous_event chain, REVOKE/RETIRE terminal, illegal transitions rejected) |
| S4 | every evidence file's SHA-256 recomputed and compared (the anti-tamper core) |
| S5 | Evidence Root recomputed and compared against the manifest |
| S6 | **seal signature** (new in v0.2): in strict `--key` mode, unsigned/forged/key-swapped packages FAIL; in open mode a signed package is INCONCLUSIVE, an unsigned one SKIP |

## Two verification modes

| Mode | Command | Semantics |
|------|---------|-----------|
| Open | `uibc verify pkg` | v0.1-compatible: integrity only (S1-S5); a seal is present but cannot be checked → INCONCLUSIVE |
| Strict | `uibc verify pkg --key owner.key` | owner holds the key: the seal must exist and be valid; forgeries and key swaps are blocked at S6 |

## Reporting discipline (archive §16/§17)

Every verification report must state: `scope`, `limitations`, `checked`,
`not_checked`. v0.2 explicitly does NOT check: asymmetric/third-party
signatures (Ed25519, v0.3 target), lifecycle event signatures, external
timestamp anchoring, behavior evaluation, memory faithfulness/continuity.

## Known boundaries (the honest list)

- **The seal is symmetric HMAC-SHA256 (v0.2 stopgap, stdlib-only)**:
  verification requires the key; third-party verifiability needs Ed25519
  (v0.3 target, pending the `cryptography` dependency decision)
- **Key-swap detection requires out-of-band pinning**: an attacker can re-sign
  the whole package with their own key — verifying with the owner's `--key`
  FAILs (key mismatch), but without the owner's key the swap is invisible.
  This is the standing motivation case for v0.3 (Ed25519 + public-key
  registry; see fixtures/malicious-keyswap)
- The Evidence Root algorithm is temporary (SHA-256 over sorted hashes);
  upgrades to a Merkle tree once canonical serialization is finalized
- Timestamps are not externally anchored yet (OTS/Rekor in production)

## Golden Fixtures (archive SS30)

Benchmark as executable evidence — eight mutation categories, each a runnable,
owner-signed submission.uibc package:

```text
fixtures/              open mode        strict (--key) mode
├── clean.uibc         PASS (S6 INCONCLUSIVE)   PASS (S6 PASS)   baseline
├── tampered.uibc      FAIL (S4)        FAIL (S4+S6)     evidence content rewritten
├── deleted.uibc       FAIL (S4)        FAIL (S4+S6)     evidence file deleted
├── duplicated.uibc    FAIL (S5)        FAIL (S5+S6)     index entry duplicated
├── reordered.uibc     FAIL (S3)        FAIL (S3+S6)     lifecycle order shuffled
├── migrated.uibc      FAIL (S5)        FAIL (S5+S6)     partial migration, not resealed
├── malicious.uibc     PASS (S6 n/a)    FAIL (S6)        fully self-consistent forgery —
│                                                        v0.1 blind spot, blocked in v0.2 strict
└── malicious-keyswap  PASS (S6 n/a)    FAIL (S6)        re-signed with attacker key —
                                                         owner-key check is the only detector
```

Regenerate + re-verify: `python fixtures/generate_fixtures.py` (writes
`fixtures/EXPECTED.md` with expected-vs-observed per archive SS31 fields,
both modes + attacker-key column).

## Ecosystem pieces

| Piece | Where | What |
|-------|-------|------|
| MCP server (read-only) | `mcp_server/` | 7 tools over stdio JSON-RPC |
| Registry server (read-only) | `registry_server/` | HTTP access to certificates/revocations/disputes; static query page at `registry/index.html` |
| A2A adapter | `adapters/a2a/` | JSON-RPC 2.0 over HTTP: `card` / `uibc/verify` / `uibc/gate` / `uibc/inspect` |
| Showcase (full lifecycle) | `examples/showcase.py` | one agent, one verifiable lifecycle, real run transcript in `examples/SHOWCASE.md` |
| Failure corpus | `failure_corpus/` | real failures F-001..F-006 with root causes and lessons |
| Contest package | `contest/` | charter, problems, rubric, submission spec, pilot-run record |
| AI discovery | `llms.txt` + `ai/` | machine-friendly entry points |
