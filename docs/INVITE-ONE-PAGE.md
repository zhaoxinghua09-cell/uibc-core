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

Then, instead of writing glue code, give us **one executable** and let the harness
drive it:

```bash
python tools/conformance_harness.py --adapter "node your-adapter.mjs"
```

Your adapter reads one JSON line and writes one back — five fields in, two out. The
protocol is in [`conformance/ADAPTER-PROTOCOL.md`](../conformance/ADAPTER-PROTOCOL.md)
and it is short enough to read in two minutes. The harness feeds every vector,
compares results, and writes a receipt naming your command, your OS, your runtime
and the UTC time.

The receipt splits two things on purpose: **root agreement** (language-neutral —
your fold either produces the same bytes or it does not) and **verdict agreement**
(your error vocabulary versus ours). A root-equal, verdict-different row is recorded
as *wording only* and is explicitly **not** counted as a conformance failure. You
are not being asked to adopt our names for things.

## What to send back

The receipt file the harness wrote, plus three lines we cannot derive from it:

1. Your implementation: language, repository URL, commit you ran.
2. Whether you had seen our expected results before running (**blind** or
   **directed**) — asked because directed runs prove reproducibility, not independent
   discovery, and the ledger records which it was.
3. Any vector where you believe **the RFC** (not our vector) is ambiguous — with the
   sentence of the RFC you are reading.

If a vector is wrong, say so and say which field is wrong. We will fix the package
and credit you by name in the changelog. If your verifier refuses an input we score,
that is the most interesting outcome on the table — with one condition: quote the
RFC sentence. A refusal is either a gap in our vector or a bug in your fold, and
`MTH({}) = SHA-256()` and the domain of `PATH` are both written down, so the text
decides it. If it really is a gap, it moves to `manifest.underspecified_inputs`
instead of being scored; if the text does decide it, the vector stays and the
disagreement is recorded against the sentence. We have already retracted one false
gap this way (`manifest.retired_underspecified_inputs`, retired 2026-11-21).

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

**What happens to your answer.** It is checked before anything else happens to it:
`tools/check_conformance_receipt.py` re-derives every number in your receipt from
its own rows and from the packaged vectors, and refuses a receipt that contradicts
itself. If yours fails that check you get the specific contradiction back —
"summary says 55/55, rows say 42/55" — rather than silence or a vague reply.

*Prepared 2026-11-20. Not yet sent to anyone at the time of writing; sending is a
separate, deliberate act.*
