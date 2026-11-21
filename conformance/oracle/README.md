# UIBC conformance corpus

30 cases, each a complete submission package plus the verdict it must produce.
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

## The three checks a package cannot carry

Seventeen of the twenty checks are decided by the package alone. Three are not, and
two of those ship their outside input with the case rather than leaving the reader
to guess:

- **S9, `oracle-s09-rollback-pin`** — the package is a valid older one. S9 is the
  check that it is not a *rollback*, which only means something against a head
  observed somewhere else. `expected.json` carries that head in `expect_head`; verify
  the suite the way `uibc verify --expect-head <value>` does and it must FAIL at S9.
  Verified against its own head it is PASS, so the case is not simply broken.
- **S19, `oracle-s19-stale-state`** — the package is signed and self-consistent, and
  is older than what this verifier remembers. `expected.json` carries the memory in
  `state` (the same shape `uibc verify --state <file>` writes). Supply it as the
  state file and the verdict must be FAIL at S19.
- **S0 is not here at all.** S0 asks what the verifier does with input that is not a
  package: truncation, deep nesting, invalid UTF-8, a path climbing out. There is no
  package to put in a directory, so the ten hostile inputs live in
  `tools/redteam_robustness.py` and `docs/ROBUSTNESS.md` instead. This is a real
  limit of a package corpus and it is written down rather than papered over.

## What this corpus does not prove

These packages were produced by this project. They are anchored to
`docs/CHECK-MATRIX.md` and to the spec text, not to an outside authority, and
passing them shows conformance to this reading of the spec, not to any
regulator's requirement. Anything a verifier does that is not in here is
unmeasured, not impossible.
