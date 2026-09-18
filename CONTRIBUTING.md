# Contributing to uibc-core

Thanks for looking. This project is a **proposal-stage specification plus its
reference implementation**, so contributing here is as much about the spec as
about the code.

## Ground rules

1. **Evidence over assertion.** A change that claims "this is safer / faster /
   more correct" should come with the fixture, test, or measurement that shows
   it. The repository's culture is: the claim is the thing under test.
2. **Honest boundaries.** Never widen a claim to sound better. If a check only
   covers part of a problem, the docs must say which part. Overclaiming is
   treated as a defect, not a marketing choice.
3. **No silent behaviour changes to verification.** The verifier's verdicts
   (PASS / FAIL / INCONCLUSIVE) are a contract. Any change in what produces
   which verdict must be called out explicitly in `CHANGELOG.md`, with the
   fixture that proves it.
4. **Append-only means append-only.** Registries and archive directories are
   never rewritten or pruned in place.

## Development setup

Python **3.9+**, standard library only. No runtime dependencies.

```bash
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
pip install -e .
python -m uibc_core.cli demo      # smoke: build -> seal -> verify PASS -> tamper -> FAIL
```

## Before you open a pull request

Run the full local gate — this is the same gate a pre-push hook runs:

```bash
python -m pytest tests/ -q                    # unit suite
python -m pytest tests/ -q -k stress          # stress scenarios
python independent_verifier/cross_check.py    # cross-implementation agreement
```

A pull request is expected to:

- Keep the unit and stress suites green.
- Keep `independent_verifier` agreeing with the main implementation. If they
  disagree, that is a **specification bug** — fix the spec, then both
  implementations.
- Add or update a fixture under `fixtures/` when behaviour changes.
- Record the change in `CHANGELOG.md` under `Unreleased`.

## What we especially want

- **Adversarial cases.** Packages that *should* be rejected and currently are
  not. Send those first; they are the most valuable contribution to a
  verification project.
- **Cross-implementation ports.** A verifier in another language is the
  strongest possible test of whether the specification is actually
  deterministic and implementable.
- **Regulatory mapping.** This work sits near EU AI Act logging/record-keeping,
  GMP/QMSR record control, and ISO/IEC 42001-style AI management systems. If you
  can point at a clause this does or does not satisfy, that is useful — say
  which, precisely, and cite it.

## What we will decline

- Features that make the verifier depend on a network service. Offline
  verification is a core requirement, not a preference.
- Changes that require trusting the producing system to validate the producing
  system.
- Wording that upgrades "PROPOSAL" to "standard", or a scoped proof to an
  absolute trust claim.

## Licence and contributions

By contributing you agree your contribution is licensed under
**Apache-2.0** (see `LICENSE`), including the patent grant in Section 3.

Note for standards-track work: if you are contributing on behalf of an
employer, make sure you are permitted to, and say so in the pull request.

## Conduct

See `CODE_OF_CONDUCT.md`. Short version: be precise, be kind, attack the
argument and not the person.
