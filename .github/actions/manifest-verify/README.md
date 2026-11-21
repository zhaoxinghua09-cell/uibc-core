# Verify manifest bundle

A single-step composite Action that recomputes a SHA-256 manifest over a directory and fails on any
mismatch, missing file, or unexpected extra file. It carries its own negative control.

## What PASS means

Within the observed evidence boundary, no violation was detected:

- every listed file exists,
- its recomputed SHA-256 equals the listed digest,
- and no unlisted file is present when `allow_extra` is false.

PASS does **not** claim that the files are correct, complete, or produced by any particular party. It
means the current bytes on disk match the digests in the manifest, regardless of origin. A manifest
that lists the wrong digest fails here exactly the way a tampered file does — the tool cannot tell
those apart, and does not pretend to.

## Usage

```yaml
- uses: zhaoxinghua09-cell/uibc-core/.github/actions/manifest-verify@main
  with:
    manifest: VERIFICATION/manifest.sha256   # JSON {"files":[{path,sha256}]} or GNU sha256sum text
    root: .
    allow_extra: false                       # true tolerates files absent from the manifest
    negative_control: true                   # self-test: mutate one byte, the check must fail
```

Outputs: `verdict` (`PASS` / `MISMATCH` / `MISSING` / `EXTRA` / `ERROR`) and `checked` (number of files
whose digest was recomputed).

Exit codes: `0` PASS, `1` MISMATCH, `2` MISSING, `3` EXTRA, `4` ERROR (manifest unreadable or empty),
`5` the negative control did not fail.

## Why the negative control is on by default

A verifier that cannot fail is the failure mode this Action exists to catch. On every run it copies
the listed files to a temporary directory, flips one byte of one file, and requires the check to report
`MISMATCH`. If the flipped byte passes, the run fails with exit code `5` and says so in the log. Set
`negative_control: false` only when you are deliberately checking a manifest whose files cannot be
copied.

## Limits, stated rather than hidden

- Digests are recomputed over the working tree, not over the git object store; a file that is
  gitignored and present on disk is still visible to `allow_extra: false`.
- Only SHA-256 is accepted. Manifests listing MD5 or SHA-1 entries are rejected as unreadable rather
  than silently downgraded.
- The negative control covers one listed file, not all of them.
- There is no signature verification here: this Action checks bytes against digests, and says nothing
  about who wrote the manifest. Pair it with a signed manifest if that is the claim you need.

`entry.py` is the whole implementation; it depends only on the Python standard library.
