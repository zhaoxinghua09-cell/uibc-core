# Anchor closing report — 2026-11-26

Scope: the external-anchor layer of `uibc-core` — one head file, three independent
witnesses (RFC 3161 TSA, OpenTimestamps/Bitcoin, Sigstore Rekor), and what a
stranger can check without us. This is the closing snapshot, not a marketing page:
every number below points at a file in this repository.

## One command, and the verdict it printed today

```
python tools/ots_full_verify.py \
  --file tests/fixtures/anchor/anchored_head.json \
  --proof tests/fixtures/anchor/ots_head.ots \
  --tsa-token tests/fixtures/anchor/freetsa.tsr \
  --rekor-entry tests/fixtures/anchor/rekor_entry.json
```

```
verdict=FULL_CHAIN_OF_EVIDENCE_VERIFIED
  anchors: {open_timestamps: true, rfc3161: true, transparency_log: true,
            both_anchors_verified: true}
  most_work_established: false
```

`most_work_established: false` is the honest part, not a defect: no Bitcoin Core
node was available to this run, so the global "most work chain" question stays
open and is printed in `unchecked` on every verdict.

## The evidence chain, step by step

| step | what proves it | where the bytes are |
|---|---|---|
| file → proof | proof commits a digest byte-equal to the file's sha256 (`bound`) | `tests/fixtures/anchor/ots_head.ots` (3 536 B) |
| proof → block | attestation message equals the Merkle root inside an 80-byte header; `sha256d(header)` equals the block hash two operators agree on | `docs/anchor-ots-block-977449.json` |
| block → tip | 160 headers (977450..977609) linked by prev-hash, each hashing to its own id and meeting its own difficulty target | `docs/anchor-ots-chain-977449.json` |
| RFC 3161 | Free TSA token over the same digest, signature verified offline against the shipped CA bundle | `tests/fixtures/anchor/freetsa.tsr` + `freetsa_ca.pem` |
| Rekor | entry body hashes the file, embedded signature verifies, log's `signedEntryTimestamp` verifies against the published key | `tests/fixtures/anchor/rekor_entry.json` |

Numbers as recorded in the receipts (dated, they only grow):

- block **977449**, hash `00000000000000000001b9b568f25bb0dbb631c3084632a22135c3bfcb0f11a7`
- Merkle root `4729e14a…1bde`, byte-equal to the digest the OTS attestation commits
- tip 977609 from both operators; **160 confirmations** measured, far above the 6 the CTS draft calls a floor
- segment work `0x4ca3bff8b1fe1a4bd5c780` — the floor any displacing chain must redo
- TSA genTime `2026-11-17T08:11:35+00:00`; Rekor log index `3944456508`

## What a stranger can re-derive without us and without network

```
python tools/ots_block_crosscheck.py --check  docs/anchor-ots-block-977449.json
python tools/ots_block_crosscheck.py --chain-check docs/anchor-ots-chain-977449.json
python tools/ots_full_verify.py --file ... --proof ... --tsa-token ... --rekor-entry ...
```

All three run offline against the committed receipts; each re-derives hashes,
roots, linkage, difficulty and work from raw bytes. A flipped byte fails. The
test suite (348 cases, 7 skipped for optional deps) exercises each seam and
each failure path.

## What each witness does not prove (carried in the verdict, not a README)

- **OTS**: the header is checked against two explorers and 160 headers above it;
  no competing branch is enumerated, no reorg risk modelled.
- **RFC 3161**: a TSA signs *time*; a compromised TSA could backdate within its
  policy. Depth-free by nature.
- **Rekor**: checkpoint signature and inclusion proof are **not verified** - the
  checkpoint key does not match the published one and the 20-sibling proof is not
  a full RFC 6962 path. Entry-level evidence only.
- **All**: the digest proves existence, never truth of content.

## What remains, and what it costs

| gap | needs | status of the hook |
|---|---|---|
| global most-work chain | a Bitcoin Core node (`--node http://user:pass@127.0.0.1:8332`, repeatable for two) | wired, exercised against JSON-RPC stubs (agreement, disagreement, shortfall, unreachable), never against a live node |
| competing-branch enumeration | a node that follows every branch; no explorer API does | not started - and not fakeable |
| reorg risk model | node data + a stated attacker model | not started |

All three machines we control were probed on 2026-11-26 (no `bitcoind`, no 8332
listener, the cloud VM has 9.7 GB free and nothing installed), so the first row
is blocked by the fleet, not by the code. `docs/ANCHOR-NODE-RUNBOOK.md` records
the probe, what a node would add, what it costs, and the exact commands to run
when one exists.

## Defects this layer found in itself (kept, because they were real)

1. A "proof" that was a bare timestamp tree - unreadable by the official client, its digest invented by our own reader. Fixed by rebuilding on standard containers and keeping the defect bytes as a fixture.
2. The report tool printed blank block heights. Fixed.
3. Header PoW compared big-endian: 22 real blocks looked invalid. Fixed; bits at offset 72, little-endian.
4. `verify_entry` handed PEM bytes instead of a loaded key: every log entry looked forged. Fixed.
5. The node branch used `re` without importing it - found only because the stub ran it. Fixed.
6. `ots_full_verify.py` accepted `--node` and then ignored it: the verdict only read the chain receipt's stale node section, so a live answer could not outrank a receipt saying "no node". Fixed the same day a second node was wired in; `test_a_live_node_answer_overrides_a_stale_receipt` pins it.

Each of the six now has a test that fails if it comes back.
