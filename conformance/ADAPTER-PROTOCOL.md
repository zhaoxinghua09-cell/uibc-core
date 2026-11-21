<!-- SPDX-License-Identifier: Apache-2.0 -->
# Adapter protocol: one executable, one JSON line in, one JSON line out

You do not need to read our code, install our package, or agree with our verdict
names to run this corpus. You need an executable that does this:

```
# inclusion (no `kind` field, or kind = "inclusion")
stdin  : {"leaf_input_hex": "...", "leaf_index": 3, "tree_size": 8,
          "inclusion_path": ["...", "...", "..."], "root_true": "..."}
stdout : {"reconstructed_root": "...", "result": "YOUR OWN VERDICT WORD"}

# consistency (kind = "consistency")
stdin  : {"kind": "consistency", "old_size": 3, "new_size": 7,
          "old_root": "...", "new_root": "...",
          "consistency_path": ["...", "...", "..."]}
stdout : {"reconstructed_old_root": "...", "reconstructed_new_root": "...",
          "result": "YOUR OWN VERDICT WORD"}
```

One process per vector, one line each way, exit code 0. The harness
(`tools/conformance_harness.py`) starts your executable once per vector.

## Fields, exactly

**What you receive**

| Field | Type | Meaning |
|---|---|---|
| `leaf_input_hex` | hex string | the leaf input bytes. Compute `SHA-256(0x00 ‖ bytes)` yourself |
| `leaf_index` | int | the index the prover claims |
| `tree_size` | int | the tree size the prover claims |
| `inclusion_path` | array of hex strings | sibling digests in RFC 9162 order |
| `root_true` | hex string | the root the log signed. Also handed to you so a verifier can compare, but **compute your own fold before reading it** |

**What you return**

| Field | Required | Meaning |
|---|---|---|
| `reconstructed_root` | yes | the root *you computed* by folding. Hex. Empty string if your verifier refuses to fold at all |
| `result` | yes | your own verdict word. Any string. You are not being graded on our vocabulary |

**Consistency requests** carry `kind: "consistency"` and the two sizes, the two
roots and the proof; return the two roots your verifier rebuilt from `old_root`
and the path, plus your verdict word. Empty strings when your verifier refuses to
rebuild at all. If you only implement inclusion, answer those rows with
`{"reconstructed_old_root": "", "reconstructed_new_root": "",
"result": "UNSUPPORTED"}` — the receipt will record them as root disagreements,
which is honest and costs you nothing on the inclusion half. The 44 inclusion
vectors and the 13 consistency vectors are counted separately in the receipt
(`kinds`), so a reader can see which half you support.

Anything else you return is kept verbatim in the receipt under `their_extra`, so if
your verifier produces a structured reason code, return it and it will be preserved.

## What the harness does with it

It compares two things **separately**:

1. **`root_agreement`** — your root versus the vector's recorded root. Language-neutral:
   a root is a byte string and either it matches or it does not. A mismatch here is
   an algorithmic difference and is worth a report to us.
2. **`verdict_agreement`** — your verdict word versus ours. Implementation-specific.
   If your root matches and your word differs, the receipt records it as
   *wording only* and does **not** count it as a conformance failure.

That split is the point: a report that says "6 of 57 failed" because you call it
`E_PROOF_MISMATCH` and we call it `INVALID_INCLUSION_PATH` teaches nobody anything.

## Two examples in this repository

| Adapter | Purpose |
|---|---|
| `conformance/adapters/reference_python.py` | minimum viable adapter. Folds per RFC 9162 written from the text; will agree on roots |
| `conformance/adapters/accept_all.py` | negative control. Refuses nothing, so it *must* disagree on the fail vectors. If this one agrees with everything, the harness is broken |

Run both, from the repository root:

```bash
python tools/conformance_harness.py --adapter "python3 conformance/adapters/reference_python.py"
python tools/conformance_harness.py --adapter "python3 conformance/adapters/accept_all.py" --expect-disagreement
```

The first must end `ROOTS-AGREE`; the second must end `CONTROL-OK`. If the second
ends `CONTROL-FAILED`, the harness is a rubber stamp and should be fixed before
anyone trusts a receipt from it.

## Adapters in other languages

```bash
# Node
python tools/conformance_harness.py --adapter "node conformance/adapters/your.mjs"
# Rust: build your binary first, then point at it
python tools/conformance_harness.py --adapter "./target/release/your-adapter"
```

Your adapter does not have to link our code, parse our manifest, or handle
`SHA256SUMS`. The harness has already done all of that before your process starts.

## Filing the receipt

The receipt names your command, your OS, your runtime, the UTC time, and every
vector's two comparisons. Send it as-is; we file it into `external-runs.json` in
the portal repository with `run_label` = `independent` **only if you wrote the
implementation**, and `evidence` = `blind` **only if you had not seen our expected
results beforehand**. Both are recorded as you state them, and the published count
is derived from the ledger, not typed into prose.

## What happens to the receipt here

A receipt is checked before it is filed, by `tools/check_conformance_receipt.py`:

```bash
python tools/check_conformance_receipt.py receipt.json
```

It re-derives every number in the receipt from its own rows and from the packaged
vectors, and refuses a receipt that contradicts itself: a summary count that disagrees
with the rows, a row naming a vector that does not exist here, a row whose
`root_agreement` flag disagrees with the answer it records, or a partial run that does
not say which vectors it skipped. Its own `--self-test` mutates a good receipt four
ways and requires each to be caught.

**What this can and cannot do.** It cannot verify what your program computed — that
happened on your machine. It verifies that what you sent is internally consistent and
that it describes this package's vectors rather than a stale copy. That is the
difference between a receipt and a claim: a filer who is careless (or worse) now
produces something that fails to check, instead of something that reads well.

If you would rather not have your name filed, say so and the row will carry
`who: "independent implementer (anonymous, at their request)"` with your receipt
attached. The count still goes up; only the attribution is withheld.
