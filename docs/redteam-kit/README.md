# UIBC red-team kit 0.1

Nine hostile packages, one runner, no dependency on the reference repository.
Bring your own verifier:

```
python run_matrix.py --label mine -- python -m uibc_core.cli verify
python run_matrix.py --label mine -- python ivcli.py
python run_matrix.py --json --label mine -- node verify.mjs
```

Two rules, both from the reference repository's own test docstring:

1. **must_answer** — a crash is not a verdict.
2. **must_refuse** — no case may come out PASS.
3. **must_structure** (advisory only) — a JSON verdict should carry at least 8
   check entries. Not a gate: the reference legitimately reports fewer when
   serialization fails early.
4. **must_accept** — *only when you pass `--pin keyfile`*: the one positive
   package in `positive/` must come out PASS. This is what catches a verifier
   that answers FAIL to everything.

The `controls/` folder holds deliberately bad verifiers. Run them and watch
the kit fail them; if it does not, the kit is the thing that is wrong.

Cases: bytes that are not JSON; wrong top-level type; duplicate member
(two readers, two answers); NaN literal; 4000-level nesting; invalid UTF-8;
path escaping the package; empty directory; 8 MB manifest.

Not claimed: this is a hostile-input smoke, not a conformance suite, and
passing it says nothing about whether a verifier's *positive* checks are
correct. It is deliberately tiny so anyone can read all nine cases.

## Positive case

`positive/clean` is the Ed25519 `clean` package from
`fixtures-v041` with its published public key. No secret is involved: the key
is a verification key, not an owner key. Measured 2026-11-24: the reference
verifier and an independently written verifier both return PASS on it.
