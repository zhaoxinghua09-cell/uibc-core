# UIBC conformance corpus

28 cases, each a complete submission package plus the verdict it must produce.
Written by `python tools/oracle_check.py --emit <dir>`; the answers were checked
against the bytes on disk after writing, so what you read here is what the files
do (mismatches at emit time: 0).

## Rebuilding these bytes

The corpus is reproducible, not merely consistent. Emit it with the same clock
and you get the same files:

    SOURCE_DATE_EPOCH=1794700800 python tools/oracle_check.py --emit <empty dir>

Every `created_at` comes from that epoch instead of the wall clock, and every
`event_id`, `evidence_id` and file name prefix is derived from a fixed seed
(`UIBC_REPRO_SEED`, set by `--emit`) instead of `uuid4`, so a second run asking
in the same order gets the same identifiers. `tests/test_oracle_reproducible.py`
rebuilds the corpus and compares bytes; it fails if that stops being true.
Without `SOURCE_DATE_EPOCH` the corpus still emits and still round-trips - it
just cannot be rebuilt, which is the thing worth not doing.

## How to use it with any verifier

1. Take `cases/<name>/` as the package.
2. Read `keys.json` for that case. If `mode` is `strict`, verify in strict
   (owner-key) mode exactly as `uibc verify <path> --key <hex> --json` does. If
   `mode` is `open`, verify with no key: those packages were built sealed and then
   mutated, so the seal is expected to fail and open mode is what lets the case
   reach the check it was written for.
3. Compare the overall verdict, and the first failing check id for reject cases,
   with `expected.json`.

`kind` is `accept` (must not be rejected) or `reject` (must be rejected at the
named check). A verifier that rejects everything passes every reject case and
fails every accept case, which is why both halves are here.

## What this corpus does not prove

These packages were produced by this project. They are anchored to
`docs/CHECK-MATRIX.md` and to the spec text, not to an outside authority, and
passing them shows conformance to this reading of the spec, not to any
regulator's requirement. Anything a verifier does that is not in here is
unmeasured, not impossible.
