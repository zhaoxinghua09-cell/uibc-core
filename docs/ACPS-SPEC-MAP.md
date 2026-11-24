# The ten ACPs documents, mapped (2026-11-24)

Who reads what, and where the documents contradict each other. Everything below is
measured against the files in `aip-pub/ACPs-community` as fetched on 2026-11-24 — not
against any crate's summary of them.

## Inventory

All ten documents caught up to **v02.02** at the same time. "AIC mentions" counts the
literal string `AIC` in the text, which is a crude but honest proxy for "this document
depends on the identity code".

| # | Document | 版本 | Size | AIC mentions | What it is |
|---|---|---|---|---|---|
| 01 | `ACPs-spec-overview` | v02.02 | 21 KB | 23 | The frame: 5.1 core concepts through 5.10, each section pointing at its own document |
| 02 | `ACPs-spec-AIC` | v02.02 | 8 KB | 10 | **Agent Identity Code** — ten arcs, checksum with per-ARSP salt |
| 03 | `ACPs-spec-ACS` | v02.02 | 39.5 KB | 6 | Agent Capability Specification: provider, capabilities, security scheme, endpoints, skills |
| 04 | `ACPs-spec-ATR` | v02.02 | 7.4 KB | 37 | Agent Trusted Registration: ARSP issues AIC, CASP issues CAI, EAB binds the ACME account |
| 05 | `ACPs-spec-AIA` | v02.02 | 6.7 KB | 6 | Agent Identity Authentication: mTLS 1.3, verify CAI, compare peer AIC against the certificate's AIC |
| 06 | `ACPs-spec-ADP` | v02.02 | 46.6 KB | 67 | Agent Discovery: search by capability, `forwardChain` of AICs with loop detection |
| 07 | `ACPs-spec-AIP` | v02.02 | 90.8 KB | 26 | Agent Interaction Protocol: roles, sessions, messages, RPC, tasks |
| 08 | `ACPs-spec-DSP` | v02.02 | 19.9 KB | **0** | Data synchronization between registries — the one document that never touches AIC |
| 09 | `ACPs-spec-AMP` | v02.02 | 130.2 KB | 13 | Agent Monitoring: logs, heartbeat, log format |
| 10 | `ACPs-spec-AAC` | v02.02 | 39.3 KB | 63 | Agent Access Control: subject IDs, actor chains, authorization events |

## Where the identity code is actually consumed

| Consumer | How AIC enters | Consequence for a reader |
|---|---|---|
| ATR | AIC is the registration output; CAI's `CN` **must** be the AIC; SAN carries `URI:acps://{AIC}`; both must match or the certificate is invalid | A code that cannot be read is a certificate that cannot be validated |
| AIA | mTLS peer AIC compared against the AIC inside its CAI | Same check, at handshake time |
| ADP | `forwardChain` entries are AICs; `40003 ForwardChainInvalid` and `50801 ForwardLoopDetected` are defined against them | A misparse becomes a false loop or a false accept |
| AAC | `agent:{aic}` is the recommended subject-ID form; `immediate_actor = agent:{mTLS peer AIC}` | Authorization decisions ride on the AIC string |
| AMP | Log records key off AIC, with `kid` needed as well because "AIC alone cannot determine the verification key" | Key rotation is explicitly out of the AIC's scope |
| AIP | Sessions and messages reference AIC | — |
| ACS | Examples carry AIC in provider blocks | — |

One line worth quoting from AMP, because it is the most honest statement in the set:
"AIC alone cannot uniquely determine the public key needed for signature verification",
hence `kid`. The identity code identifies; it does not authenticate.

## The contradiction worth reporting to the authors

Two documents in the same repository, both stamped v02.02, place the version arc in
different positions.

**`ACPs-spec-AIC` §3** (what our reader implements):

```
prefix(4) · version · ARSP · vendor · ontology · instance · checksum
example:  1.2.156.3088.1.1.34C2.478BDF.3GF546.0JU4
```

**`ACPs-spec-overview` §5.2**:

```
prefix(4) · ARSP · vendor · ontology · instance · version · checksum
example:  1.2.156.3088.1.34C2.478BDF.3GF546.1.0SEN
```

**`ACPs-spec-ATR` §3.1** follows the overview's numbering in words: the ontology AIC
carries `0` in "第8级智能体实体序列号", and the entity serial is described as occupying
nine digits at "oid 第8级" — i.e. version is not at position 5.

Measured, not argued (salt `0x1234`, the value the AIC document publishes):

| Sample | Source | Carried | Recomputed | Verdict |
|---|---|---|---|---|
| `…3088.1.1.34C2.478BDF.3GF546.0JU4` | AIC §3/§4 | `0JU4` | `0JU4` | matches |
| `…3088.1.34C2.478BDF.3GF546.1.0SEN` | overview §5.2 | `0SEN` | `0SEN` | matches |
| `…3088.1.1.34C2.478BDE.3GF546.1.0RBK` | ACS | `0RBK` | `0RBK` | matches |
| `…3088.1.1.34C2.478BDF.3GF546.0JU1` | AIP | `0JU1` | `0JU4` | **mismatch** |
| `…3088.1.1.34C2.478BDF.3GF546.0JU2` | AIP | `0JU2` | `0JU4` | **mismatch** |

Reading: **the checksum does not depend on the arc semantics.** It hashes arcs 1-9 as
text, so a string built under either ordering carries a valid checksum for itself. Seven
of the nine distinct ten-arc samples in the corpus verify; the two that do not are AIP's
`…0JU1` / `…0JU2`, which look like `0JU4` with the last character bumped to name two
agents — a placeholder, not a second algorithm.

So the defect is not the checksum. It is **field naming**: a reader that labels arcs per
AIC §3 will read the overview's example as `ARSP=1, vendor=34C2, ontology=478BDF,
instance=3GF546, version=1`, which passes every shape rule and is wrong about what each
arc means. Downstream (AAC subject IDs, ADP chains, ATR certificate matching) the labels
matter, not the CRC.

What this repository does about it: our reader follows AIC §3, `scope` says so, and
`docs/ACPS-SPEC-IN-HAND.md` records the overview's alternative ordering with its own
verifying example. We do **not** claim a crosswalk, and we do **not** silently re-label —
that would be inventing the answer the authors have not given.

## How the files were obtained (and what that taught us)

| Route | Result |
|---|---|
| `git clone --depth 1 https://atomgit.com/aip-pub/ACPs-community.git` | **works**, 1,937 files |
| `contents` API, per file | works, but rate-limits (HTTP 429) after a few dozen calls |
| `git/tree?recursive=1` API | returns **0 entries** for these repositories |

The CRLF wrinkle: a Windows checkout of `ACPs-spec-AIC.md` is 8,149 bytes; the API's copy
is 8,043. They are the same document — the hash matches after normalising line endings
(`sha256:38242a01…23ab`). Pinning a text by hash without saying which line-ending
convention applies is how a future reader concludes "the file changed".

## What is still open

1. **Ask the authors which ordering is normative.** A GitHub/AtomGit issue with the two
   examples and the two measurements is ready to send; it needs your approval to post.
2. `acps-docs/` currently holds only a README and `.gitignore` — the reference
   documentation advertised in the community README is not there yet. Not our gap.
3. `ACPs-spec-AMP` (130 KB) and `ACPs-spec-AIP` (90.8 KB) were read only around AIC
   usage. A full read is a separate job, and nothing in them changes the reader.
4. No ARSP-issued code and no ARSP salt, unchanged from `docs/ACPS-SPEC-IN-HAND.md`.
