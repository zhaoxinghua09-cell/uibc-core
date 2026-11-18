# Link 3 — Handover evidence pack (checked at receiving)

A worked example from the medical-device lifecycle handbook: a
manufacturer hands a device evidence set downstream, and the receiving
side — a distributor, an importer, a hospital — checks it **before
filing it, before relying on it**. Four files (design verification
report, risk analysis summary, software test summary, electrical
safety summary), one seal, and the one habit that makes the seal mean
something: pinning the sender's public key.

Fictional throughout: Meridian Medical and the CardioPatch CP-2 do not
exist. The cryptography is real.

## The five runs

| Run | What happened | Verdict |
|---|---|---|
| `uibc verify packages/approved` | The set as sealed by the manufacturer | **PASS** |
| `uibc verify packages/approved --pubkey meridian-owner.pub` | Same, checked against the manufacturer's known public key | **PASS** |
| `uibc verify packages/received-swapped` | On arrival, one report (design verification) has been silently replaced by a Rev B | **FAIL** — the check names the file |
| `uibc verify packages/received-resealed` | The Rev B set, rebuilt and re-sealed under a substitute key, verified without pinning | **PASS** — an unpinned check cannot tell |
| `uibc verify packages/received-resealed --pubkey meridian-owner.pub` | The same rebuilt set, pinned to the manufacturer's key | **FAIL** — wrong signer |

The fourth run is the lesson of this pack. A seal proves a set was not
changed **after sealing**; it does not prove **who sealed it**. The
receiver who pins the sender's public key — obtained once, out of
band — catches the re-sealed set. The receiver who does not pin,
cannot. Both commands are one line; the difference is the habit.

## Verify it as a stranger

```
pip install uibc-core
cd examples/link3-handover-evidence
uibc verify packages/approved
uibc verify packages/received-resealed --pubkey meridian-owner.pub   # FAIL, as it should
```

A plain-language, five-step version (EN + 中文） is in
[README-VERIFY.md](README-VERIFY.md); the full recorded run is in
[RUN-TRANSCRIPT.txt](RUN-TRANSCRIPT.txt).

## Stated plainly: what these seals cover

These packs are sealed in the released 0.3.3 format. The seal covers
the identity and the manifest; the lifecycle event chain is guarded
by the verifier's chain check (S3), **not** by the seal. Newer
verifiers say so on the S6 line itself — `coverage=legacy` — and this
pack repeats the label rather than hiding it: for a handover, the
evidence files and their hashes are what the seal binds, and that is
the property the five runs exercise. Packs sealed by current code
additionally bind the lifecycle into the seal.

## Build note

`build_demo.py` rebuilds all three packs from `_src/` with published
demo seeds (owner `bytes([7]*32)`, substitute signer `bytes([9]*32)` —
demo only; never use a published seed for anything real). The
committed packs were rebuilt with the **released uibc-core 0.3.3**,
so the stranger path above reproduces every verdict; the transcript
records the re-verification, including the coverage note above.

## Doors

- Previous act in the chain — the change-evidence pack (Link 1):
  `examples/link1-change-evidence/` in this repository
- The check set and verdict semantics: `docs/verdict-and-seal-semantics.md` (repo root → docs/)
- Browser verifier (same checks, built-in example + tamper button): https://zhaoxinghua09-cell.github.io/uibc-core/verify.html
- On PyPI: https://pypi.org/project/uibc-core/
- The theory this instantiates (Lifecycle Governance Doctrine — evidenced, gated): https://github.com/zhaoxinghua09-cell/lgd-theory — concept DOI 10.5281/zenodo.22456647
- Ecosystem portal: https://zhaoxinghua09-cell.github.io/lgd-hub/
- Companion failure-mode catalogue: https://github.com/zhaoxinghua09-cell/silent-failure-catalog
