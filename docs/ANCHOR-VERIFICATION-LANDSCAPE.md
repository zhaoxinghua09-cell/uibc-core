# Anchor verification: what the field does, and where this repository stands

Surveyed 2026-11-26. The question every entry below answers is narrow: **given
someone else's OpenTimestamps proof, who decides whether it is true, and with
what evidence?** Not "does the vendor say it is anchored".

## Practitioners and their evidence

| who | what they accept as verification | trust assumption | source |
|---|---|---|---|
| `ots` reference client | timestamp ops replayed, then checked against a **local Bitcoin Core node's** chain (pruned node enough); incomplete proofs get the block path from a calendar | the node, or the calendar that answered | client README: verification needs a node |
| `ots` project website | server-side check | the website | "you cannot verify independently, since the verification is made by a third party" |
| one real implementation in the wild (mirror-stack MCP) | block Merkle root matched against **one** explorer (blockstream.info); no node | that single explorer told the truth | its ANCHORING doc |
| Sigstore Rekor | inclusion proof at tree size N **plus** a signed checkpoint, and (per the 2025 witness push) a checkpoint co-signed by a witness quorum | log operator + witnesses; explicitly notes an inclusion proof at N alone does not prove the tree was not forked | Sigstore security model; Rekor deep dive |
| SCITT external-time-anchor draft | OTS proof + "sufficient confirmation depth", verifiable without contacting the anchor service | the Bitcoin chain | draft-fassbender-scitt-time-anchor |

The spread is instructive: the cheapest path trusts one server, the best path
trusts a node you run, and the transparency-log world solved the same "did it
fork?" question with witnesses + consistency proofs rather than more APIs.

## What this repository now does (as of 2026-11-26)

1. **Proof -> header**: the attestation's message must equal the Merkle root
   inside an 80-byte header, and `sha256d(header)` must equal the block hash -
   two independent operators have to agree on both. `docs/anchor-ots-block-977449.json`.
2. **Header -> tip**: 160 headers walked by prev-hash from the tip to the
   attested block; each hashes to its own id, links to the next, and meets the
   difficulty target its `bits` field demands; segment work recorded.
   `docs/anchor-ots-chain-977449.json`.
3. **Both receipts re-derive offline**: no network, no trust in us -
   `--check` / `--chain-check` recompute hash, root, linkage, targets, work.
   A flipped byte fails.

Where that leaves the trust question, honestly:

| question | who answers here | note |
|---|---|---|
| is the proof about this file? | arithmetic (digest binding) | no server needed |
| is the block real, with that root? | arithmetic over bytes two operators agree on | wrong bytes fail a hash |
| is this block on the chain we are shown? | arithmetic over 160 linked, PoW-valid headers | resists substitution, not reorgs |
| is this block on the chain **with the most work**? | **still unanswered** - needs a node that follows every branch | `--node http://user:pass@127.0.0.1:8332` is the hook, exercised against a stub (agree / disagree / unreachable), not against a live node; receipts record `node.checked=false` |

## What the field does better, and what is left

- **Better**: Sigstore's answer to equivocation is witnesses and consistency
  proofs. Bitcoin has no witness quorum, but a node is the equivalent: its active
  chain is the most-work chain it knows. We expose that hook and refuse to
  pretend it ran.
- **Joined now, and beyond**: three witnesses (RFC 3161, OpenTimestamps, Rekor)
  answer into one verdict, and the two things Rekor's entry does not prove are
  printed inside that verdict rather than left in a README. The reference client,
  by contrast, replays ops from the digest
  itself but stops at one anchor type. `tools/ots_full_verify.py` gives one
  verdict for **both** witnesses the ASQAV profile asks about - RFC 3161 and
  OpenTimestamps - over the same digest; the older note below is kept because
  it explains the seam that used to be open:
  our path used to start at the attestation's message in a second tool.
  `tools/ots_full_verify.py` closes that seam - file -> proof -> header ->
  segment, four byte comparisons, one verdict, and the unchecked list printed
  with it.
- **Left**: no competing-branch enumeration, no reorg risk model, no witness set.
  Each needs either a node or a social layer, and inventing a number for them
  would be exactly the dishonesty this whole anchor effort exists to avoid.
