# Link 1 — Change-evidence pack (the PCCP side)

A worked example from the medical-device lifecycle handbook: an AI model
in a (fictional) device is updated from v1.1 to v1.2, and the change is
handed downstream as a **sealed evidence set** — change description,
locked-set evaluation report, approval record, previous-version
manifest. Anyone can verify the set with one command; nobody has to take
the sender's word for what was approved.

Fictional throughout: Meridian Medical and the CardioPatch CP-2 do not
exist. The cryptography is real.

## The three acts

| Package | What happened | Verdict |
|---|---|---|
| `packages/change-approved` | The four files, sealed with Ed25519 | **PASS** (also PASS pinned to the R&D public key) |
| `packages/change-swapped` | After sealing, the evaluation report was replaced by an interim tuning-set report with better-looking numbers (sensitivity 0.968) | **FAIL** — check S4 names the file: `files/evaluation-report.md` |
| `packages/change-unsigned` | The same four files, submitted but never sealed | **INCONCLUSIVE** — internally consistent, provenance unattested; the gate answers **HOLD** |

The gate's three answers all appear: ALLOW (approved), DENY (swapped),
HOLD (unsigned). HOLD is not a refusal — it means the release decision
waits until the evidence is sealed. "Ship now, tidy the evidence later"
is exactly the change-control failure this pack exists to catch.

## Verify it as a stranger

```
pip install uibc-core
uibc verify packages/change-approved     # PASS
uibc verify packages/change-swapped      # FAIL, S4 names the swapped file
uibc verify packages/change-unsigned     # INCONCLUSIVE
uibc gate   packages/change-unsigned     # HOLD
```

No key, no permission, no cooperation from us. A plain-language,
five-step version (EN + 中文） is in [README-VERIFY.md](README-VERIFY.md);
the full recorded run is in [RUN-TRANSCRIPT.txt](RUN-TRANSCRIPT.txt).

## What this does not do

It seals and verifies the change **evidence set**. It does not write a
PCCP, does not judge whether the change should have been approved, and
does not assess whether the evaluation was done well. Those remain
human quality judgements. The claim is only: the evidence folder is
sealed, re-verifiable by anyone, and a missing seal reads as
INCONCLUSIVE — never as a quiet pass.

## Build note (why these packs were sealed with the released code)

The committed packages were built with the **released uibc-core 0.3.3**
(the version `pip install` gives you), so the stranger path above
reproduces every verdict. `build_demo.py` rebuilds them from `_src/`
with a published demo seed (`bytes([3]*32)` — demo only, never use a
published seed for anything real). RUN-TRANSCRIPT.txt records a
compatibility note found by cold-testing: seals made by later repo code
are read by this release's verifier as invalid, while newer verifiers
read these 0.3.3 seals as PASS with `coverage=legacy`. Until a release
restores a single numbering, handbook packs are built with the released
code.

## Doors

- The check set and verdict semantics: `docs/verdict-and-seal-semantics.md` (repo root → docs/)
- Browser verifier (same checks, built-in example + tamper button): https://zhaoxinghua09-cell.github.io/uibc-core/verify.html
- On PyPI: https://pypi.org/project/uibc-core/
- The theory this instantiates (Lifecycle Governance Doctrine, third law — gated): https://github.com/zhaoxinghua09-cell/lgd-theory — concept DOI 10.5281/zenodo.22456647
- Ecosystem portal: https://zhaoxinghua09-cell.github.io/lgd-hub/
- Companion failure-mode catalogue: https://github.com/zhaoxinghua09-cell/silent-failure-catalog

Companion handbook packs are being published link by link. The next
act in the chain — the evidence set leaving the manufacturer and being
checked at the receiving side — is the Link-3 handover pack:
`examples/link3-handover-evidence/` in this repository.
