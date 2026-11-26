# Reproduction record

Required by the gate the maintainers apply to their own material (S7-C5): interpreter,
commands, expected exit codes, observed output, cross-machine status, integrity check.

**As of 2026-11-26. Commit `a62f302` on `feat/standards-exceed-20261125` (an open branch,
not a release and not a standard).**

## Interpreter and platform

- Python **3.13.18**, Windows **AMD64**
- Reference verifier version reported by `python -m uibc_core.cli --version` → `0.5.5`
- No virtualenv, no extra packages beyond the repository's declared requirements

## Commands, expected and observed

| # | Command | Expected | Observed (2026-11-26) |
|---|---|---|---|
| 1 | `python tools/axis_report.py --out out/axis_report` | 32 cases compared, divergence list empty | `合计 32 例，一致 32，分歧 0。` exit 0 |
| 2 | `python tools/outsider_chain_audit.py` | chain sound, newest bundle anchored, superseded refused, withheld anchor stale | `VERDICT: OK` with `ok` on all four lines (python and node readers) |
| 3 | `python -m uibc_core.cli verify conformance/oracle/cases/oracle-clean --key <seed file> --bundle-out X.json --trustlist out/trustlist.json` | verdict PASS, bundle written | `"verdict": "PASS"`, `key_on_list: true`, exit 0 |
| 4 | same command with `--trustlist` pointing at a non-existent file | one sentence, exit 2, no traceback | `trustlist file not found: …`, exit 2 |
| 5 | `python -m pytest -q tests` | no failures | see the gate directory's `_data/full_pytest.txt`; network-dependent PyPI test can fail on a slow link and passes on re-run |

The seed for cases 3–4 comes from `conformance/oracle/keys.json` (`oracle-clean`). No key is
stored in this repository; the corpus keys are test keys and must not be used elsewhere.
The 7-case head-chain demo (`用例 7/7`) is shipped in the gate pack, not in this repository;
what is reproducible *from the repository alone* is `tools/outsider_chain_audit.py`.

## Getting the bytes: clone, not the tarball, on Windows

Use `git clone` (or the zip from GitHub's "Download ZIP" on non-Windows hosts). **Do not
extract `codeload.github.com/.../tar.gz` with Windows `bsdtar` and then judge the corpus:**
bsdtar mangles non-ASCII filenames on extraction. Observed on 2026-11-26:

```
repository : evidence/files/accept-unicode-names-运行日志.txt
              evidence/files/accept-unicode-names-résumé.md
torrent out: evidence/files/accept-unicode-names-杩愯鏃ュ織.txt      (mojibake)
              evidence/files/accept-unicode-names-r茅sum茅.md          (mojibake)
```

The corpus case `accept-unicode-names` then fails S4 and the run reports 31/32 instead of
32/32. That is the extraction path, not the verifier: the same commit cloned with `git`
reports 32/32 on the same machine. If you are on Windows and see exactly one divergence,
check the filenames before filing it as a verifier bug.

If a tarball is the only thing you have, extract it with the shipped reader rather than
with `bsdtar`. It refuses to write a member whose name would not survive as UTF-8, so the
mangling is caught at extraction time instead of surfacing as a hash mismatch:

```
python tools/extract_tar.py uibc-core-<ref>.tar.gz --dest out
```

## Cross-machine

**Partially verified (2026-11-26).** A public clone of this branch
(`https://github.com/zhaoxinghua09-cell/uibc-core.git`) was made on the same Windows
machine, from the network rather than a local directory, and reported 32/32 and
`outsider_chain_audit.py → VERDICT: OK`. A second operating system has still not run
these commands; do not read this as cross-OS evidence.

## Integrity

```
sha256(conformance/oracle/expected.json)[:16] = fe1d1764f6999b64
```

A mismatch means the corpus changed after this record was written; treat the numbers above
as superseded until re-run.

## What this record does not show

- It does not show that the verifier is correct; it shows what the verifier does.
- It does not show coverage: 32 cases are below the scale of the published corpora we cite
  (54 and 73).
- There is no second implementation behind these numbers. `independent_verifier/` covers
  10 of the 19 checks; 3 corpus cases are judged differently at the same check id. See
  `out/cross_impl.md`.
