<!-- SPDX-License-Identifier: Apache-2.0 -->
# One page: run our RFC 9162 vector set and tell us what breaks

**Who this is for.** Anyone who has written an RFC 9162 / SCITT inclusion-proof
verifier in a language other than Python, and is willing to spend twenty minutes
running a corpus they did not write against code they did not write for us.

**What we are asking.** Run the vectors. Report what your verifier says. If your
verifier disagrees with a vector, we want that mismatch **more** than we want
agreement — a mismatch is the report that improves both sides. If your verifier
agrees with everything, we want the receipt so the agreement is a matter of record
rather than a claim we make about ourselves.

**What we are not asking.** Do not adopt our protocol, do not endorse anything, do
not sign a statement about our compliance. We are asking for one command's output
and how you ran it.

---

## What you get

A package that requires no code from us:

```
scitt-rfc9162/
  manifest.json          index, each expected block inlined, class counts included
  SHA256SUMS             every file, byte-for-byte
  v1/<vector-id>/expected.json
```

Each `expected.json` carries the leaf input bytes, the leaf digest, the declared
`leaf_index` and `tree_size`, the inclusion path in RFC 9162 order, the honest
root, the root obtained by folding, and the expected `result` — everything needed
to reproduce a verdict without our implementation.

The set covers the hash-tree and inclusion-path layer only. It carries **no**
COSE_Sign1 statement or receipt bytes, and says so in the package README rather
than filling the gap with unverifiable material.

## What it takes

```bash
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
sha256sum -c docs/upstream-package/scitt-rfc9162/SHA256SUMS   # integrity first
python tools/check_scitt_vectors_standalone.py                # reference run, ours
```

Then run **your** verifier over `docs/upstream-package/scitt-rfc9162/v1/*/expected.json`.

## What to send back

Five lines, no form, no template:

1. Your implementation: language, repository URL, commit you ran.
2. Environment: OS, runtime version.
3. The exact command you ran.
4. Per vector: `VALID` / the failure name you produce / `INCONCLUSIVE`.
5. Any vector where you believe **the RFC** (not our vector) is ambiguous — with the
   sentence of the RFC you are reading.

If a vector is wrong, say so and say which field is wrong. We will fix the package
and credit you by name in the changelog. If your verifier refuses an input we score,
that is the most interesting outcome on the table: it may mean the input belongs in
`manifest.underspecified_inputs` instead of being scored, and we will move it there.

## How the result will be recorded

Every receipt goes into `external-runs.json` in the portal repository, one row per
run, with `run_label` (`independent` only when you wrote the implementation) and
`evidence` (`blind` when you had not seen our expected results beforehand). The
number of external receipts published anywhere is **derived from that ledger** by
`tools/external_runs_gate.py`, not typed into prose — if the prose and the ledger
disagree, the gate fails the build.

So: whatever you send back becomes a row that cannot be quietly inflated later. That
is the point of asking.

## One honest caveat about our own second implementation

We also run a second implementation in JavaScript. It is written by the same author,
so it demonstrates determinism of the specification, **not** independence of the
implementation. It is recorded as `second-party-same-code`, never as an external
node. The axis we cannot close from the inside is exactly the one this page is
asking you to close.

---

*Prepared 2026-11-20. Not yet sent to anyone at the time of writing; sending is a
separate, deliberate act.*
