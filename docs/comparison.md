# Positioning vs adjacent projects (honest comparison, v0.1)

> Method note: compiled from a competitor research pass on 2026-09-18.
> Star counts / activity figures below are order-of-magnitude estimates
> from that pass and marked where unverified — do not cite them without
> re-checking. This page names real projects and describes them fairly;
> the goal is honest positioning, not competition-bashing.

## The map

| Layer | Established players | Notes |
|---|---|---|
| Software supply chain provenance | in-toto, SLSA, Sigstore, TUF, SPIFFE/SPIRE | mature, standards-grade, huge ecosystems; target *software artifacts*, not *agent behavior* |
| Agent governance / policy | Microsoft agent-governance-toolkit (stars unverified) | policy enforcement + audit chain; big-vendor backing, multi-language SDKs |
| Agent action receipts / notarization | AgentNotary, agent-receipts / Obsigna (both small, stars unverified) | seal/attest/receipt CLI tools; closest in spirit to uibc-core |
| Agent memory (product layer) | Mem0, Zep, Letta/MemGPT | memory stores; memory *verifiability* is not their feature |

## Where uibc-core genuinely differs

1. **Verifiable memory migration (UIBC-MEM)** — none of the above makes
   memory transfer a checkable protocol (four Preservations: Fact /
   Attribution / Citation / Version). This is the least contested ground.
2. **Dual independent implementations** — a second, from-spec verifier
   with a 70/70 cross-check harness is, to our knowledge, unique at this
   scale; it converts "the spec is clear" from a claim into a measurement.
3. **Attack fixtures as executable evidence** — 8 engineered mutation
   classes incl. a preserved historical blind spot (malicious forgery),
   with machine-generated expected-vs-observed records.
4. **Honest-boundary discipline** — scoped proofs, explicit
   checked/not_checked in every report; rare in this space.

## Where uibc-core is honestly behind

- **Maturity & trust**: PROPOSAL, single maintainer, zero third-party
  users; in-toto/Sigstore are years ahead in review depth and tooling.
- **Crypto**: HMAC (symmetric) only until v0.3 Ed25519; no external
  timestamp anchoring (OTS/Rekor); key-substitution detection requires
  out-of-band key pinning.
- **Distribution**: no PyPI package yet; documentation is primarily
  Chinese; no hosted demo; no runtime hooks (auto-capture from agent
  frameworks) — adoption currently requires manual CLI usage.
- **Breadth**: governance layers (dispute/revocation registries) are
  skeletons; certificates are not third-party verifiable yet.

## Adopted from the comparison (already shipped or queued)

| Improvement | Status |
|---|---|
| One-command demo (`uibc demo`) | shipped this release |
| Test commands in README first screen | shipped this release |
| MCP read-only server | shipped (mcp_server/) |
| PyPI publication + English README | queued (needs owner decision on package name/account) |
| Runtime hook (auto-evidence capture) | queued, design wanted |
| Transparency log for keys (Rekor-style) | v0.3+ with Ed25519 |

## Bottom line

uibc-core occupies a real niche — *agent behavior & memory verifiability*
— that supply-chain tools and memory products both leave open. It is not
the most complete or the most polished tool in the wider space, and at
current maturity its strategy should be depth-on-differentiators
(UIBC-MEM, dual-implementation assurance, failure corpus) rather than
feature racing with VC/megacorp-backed projects.
