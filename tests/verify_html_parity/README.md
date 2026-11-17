# verify.html parity corpus

The browser verifier in `verify.html` (repository root, published via GitHub
Pages) is a JavaScript port of `uibc_core/verify.py`. This directory holds
the corpus that keeps the two from drifting apart:

- `gen_battery.py` — builds 21 package variants (27 verifier runs) with the
  Python library — pristine, forged-and-resealed, lifecycle truncated,
  actor rewritten, index metadata tampered, evidence byte flipped,
  duplicate JSON keys, malformed JSON, unsigned, stray files, HMAC seals
  (current and legacy coverage, with / without / wrong key), pinned
  checkpoint heads, a NaN-bearing manifest, a future timestamp, Merkle
  (S13), receipt chain (S17), policy artefacts (S18) and anchors (S15) —
  and records the reference verifier's verdict for each run in
  `truth.json`.
- `legacy_sample/` — the pre-v1.1 page sample (a v0.3.0-proposal package
  whose seal covers identity+manifest only), frozen as the
  legacy-coverage case.
- `run_parity.mjs` — extracts the verifier library from `verify.html`,
  runs it over the corpus, and diffs every check result against
  `truth.json`.

Run:

```
python3 gen_battery.py
node run_parity.mjs
```

Expected: `ALL PARITY OK`. Any change to `verify.py` semantics or to the
page's verifier should keep this green; a red run names the exact check
that diverged. Declared port limit: S16 (RFC 3161 tokens) is INCONCLUSIVE
on the page by design, so no corpus case carries a timestamp token.
