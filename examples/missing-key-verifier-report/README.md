# The missing-key case: a worked verifier-report example

Built with the released **uibc-core 0.3.3** (PyPI) on 2026-11-18, for the
SCITT-thread question: *what should a verifier report when it does not
have the signer's key?*

The short answer this example demonstrates: **INCONCLUSIVE, with the
reason stated in the report** — not PASS (the seal was never checked)
and not FAIL (nothing was shown to be wrong). The three-valued outcome
lives in the report's `result` field; the CLI exit code is 0 only for
PASS and 1 for both other values, so a consumer must read the report,
not the exit code.

## The package

`package/` is a small evidence package (fictional agent
`demo-agent-joe-001`, two evidence files: an INPUT and an EVALUATION),
sealed with an **HMAC-SHA256 owner key** (`uibc submit --key`).
A symmetric seal is the honest setting for the missing-key case: the
key cannot travel with the package, so a verifier who does not hold it
genuinely *cannot perform* the seal check at all.

## The runs (verbatim outputs in `report-*.json`, full record in
`RUN-TRANSCRIPT.txt`)

| Run | Command | `result` | What decides it |
|---|---|---|---|
| A — **missing key** | `uibc verify package` | **INCONCLUSIVE** | S1–S5 all PASS; S6 cannot be performed: *"HMAC seal present but no verification key provided (--key); symmetric seals cannot be checked publicly"* — `assurance: "unattested"`, statement: *"No violation was detected, but verification is incomplete…"* |
| B — control | `uibc verify package --key keys/demo-owner.key` | **PASS** | S6 PASS, `assurance: "owner-key"` |
| C — control | evidence file altered after sealing, correct key | **FAIL** | S4 FAIL names the file: *hash mismatch on 'files/evaluation.txt'*; S5 INCONCLUSIVE (skipped); S6 still PASS — the report shows exactly which check caught it |
| D — bonus contrast | `uibc verify package --key keys/wrong.key` | **FAIL** | S6 FAIL: *"key mismatch: seal was not created by this key (possible key substitution or wrong key)"* |

The distinction between A and D is the point of the example:

- **No key at all → INCONCLUSIVE.** Absence of the means to check is
  not evidence about the package. Every check that *could* be
  performed passed; one check could not be performed, and the report
  says which and why.
- **A wrong key → FAIL.** A definite contradiction was observed: the
  seal was not created by this key. That is a positive finding, and
  the report states it as one.

## Reproduce it (under five minutes)

```sh
python3 -m venv venv && venv/bin/pip install uibc-core==0.3.3
cd <this folder>
venv/bin/uibc verify package                              # INCONCLUSIVE (Run A)
venv/bin/uibc verify package --key keys/demo-owner.key    # PASS (Run B)
venv/bin/uibc verify package-tampered --key keys/demo-owner.key  # FAIL (Run C)
venv/bin/uibc verify package --key keys/wrong.key        # FAIL (Run D)
```

The report JSON carries no timestamp, so your outputs should match
the shipped `report-*.json` files byte for byte. To rebuild the
package from nothing instead, follow Part 1 of `RUN-TRANSCRIPT.txt` —
a rebuild also produces byte-identical reports. Both demo keys are
fixed, published strings (SHA-256 of stated phrases, see the
transcript) precisely so the example is reproducible; they protect
nothing and must never be used for anything real.

## Two honest boundaries

- **The report is not signed.** The seal signs the *package*
  (identity + manifest, which fixes the evidence root). The report is
  the verifier's own output about the package; whoever relies on a
  report still needs a reason to trust the verifier that emitted it.
- **Ed25519 seals behave differently, by design.** With an Ed25519
  seal the public key is recorded inside `signatures/seal.json`, so an
  unpinned verify can check the signature and PASS (with
  `assurance: "public-key"`); pinning to a *different* public key
  (`--pubkey`) FAILs S6, because a definite mismatch was observed.
  There is no missing-key INCONCLUSIVE for Ed25519 in open mode,
  because the key is never missing — which is also why a pin is only
  as good as the channel that delivered it. The missing-key case in
  this folder is the symmetric-seal case, where the key truly cannot
  be obtained from the package.
