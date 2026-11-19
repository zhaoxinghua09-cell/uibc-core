# UIBC conformance corpus

28 cases, each a complete submission package plus the verdict it must produce.
Written by `python tools/oracle_check.py --emit <dir>`; the answers were checked
against the bytes on disk after writing, so what you read here is what the files
do (mismatches at emit time: 0).

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
