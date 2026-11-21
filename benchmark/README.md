# uibc mutation benchmark · 21 类篡改基准（公开度量衡）

**Purpose.** Give anyone a set of mutations and an expectation matrix they can re-run
against this implementation — or against *theirs*. A benchmark that only the author
runs is marketing; a benchmark a stranger can run and disagree with is a measurement.

**One command.**

```bash
pip install -e .            # or: pip install pycose cbor2 cryptography
python benchmark/run.py     # add --rerun to rebuild the base package first
```

Output ends with two numbers per mode. They are deliberately different:

| mode | what the verifier is given | accepted | documented by design | **undocumented** |
|---|---|---|---|---|
| `open` | nothing out-of-band | 2 / 21 (9.5%) | M17, M20 | **0** |
| `pinned` | public key out-of-band (`--pubkey`) | 1 / 21 (4.8%) | M20 | **0** |
| `head-pinned` | public key **and** checkpoint head out-of-band (`--expect-head`) | 0 / 21 (0.0%) | — | **0** |

(21 mutated members plus 1 unmutated anchor = 22 scored members; the anchor must PASS.)

- **acceptance rate** = how many mutations passed, period.
- **undocumented acceptance** = those *not* explained by a channel the mode lacks.

Only the second is a defect. Quoting the first without the second invites a reader to
mistake a design boundary for a bug; quoting only the second invites the opposite
mistake — pretending nothing was accepted.

**The third number: the corpus anchor.**

The unmutated package is part of the corpus and **must PASS** (`base_open` / `base_pinned`,
carried into `results.json` as `corpus_anchor`). Without it a verifier that refuses every
input scores a perfect 0/21 acceptance rate and looks flawless while being useless; the
anchor makes that score 0/22 instead. `run.py` exits non-zero when the anchor is not PASS,
because once the base fails, every rate below it is a number about nothing.

This is the property a mutation suite has to state rather than imply: the corpus contains
a member that must be **accepted**, and each of the 21 is **one mutation from that member**.
`benchmark/corpus/manifest.json` records the base digest and, per case, exactly which field
was changed. So "refuse everything" and "accept everything" both score badly; only a
verifier that reads each field separately scores well.

**The two documented boundaries, stated plainly.**

1. `M17` key substitution, `open` only: the key is read out of the package under test,
   so a valid signature proves internal consistency and nothing about who signed it.
   This is why the report carries `trust_level=unanchored` and why the gate policy is
   `PASS + anchored` rather than `PASS`.
   **Why `pinned` rejects it:** `S6` compares the seal's recorded `public_key` against the
   key supplied out-of-band and fails on any difference (`uibc_core/verify.py`, the
   `pubkey is not None and bytes(pubkey) != pub` branch). With a key supplied, the substituted
   signer is caught; without one, there is nothing to compare against.
   A second implementation that verifies the seal but never compares it with a supplied key
   will therefore report `PASS` for `M17` in `pinned` mode while ours reports `FAIL`.
   That gap is a missing key-pinning check on the second side, not a defect here — and it is
   the one disagreement in the table below that a reader is most likely to hit first.
2. `M20` whole-package rollback, `open` and `pinned`: an older package is self-consistent
   and correctly signed. Nothing inside it can detect that it was installed over a newer
   one. Only a head observed outside the package (`--expect-head`) catches it — that is
   check `S9`. The same limit is stated independently in
   `draft-ruvalcaba-nhe-audit-00`: an unkeyed chain proves internal linkage, and a party
   able to rebuild the whole chain can produce a consistent alternative.
   **Where the responsibility sits:** freshness and version monotonicity are the *caller's*
   layer, not the package's. A package can only be judged against a head it did not author;
   deciding whether that head is current is the two-clock rule (`docs/` on the two clocks),
   i.e. the relying party's clock and the log's clock. Accepting `M20` in `open`/`pinned`
   is therefore a declared boundary of this layer, not an unfinished check.

**What each case attacks.**

| ids | target | idea |
|---|---|---|
| M01–M05 | `manifest.json` | identity fields, evidence root, version, self-declared status, injected approval field |
| M06–M07 | `identity.json` | owner, agent type |
| M08–M11 | `lifecycle.json` | timestamp far future, actor substitution, dropped first event, illegal second ACTIVATE |
| M12–M15 | evidence files + `index.json` | one-byte edit, self-consistent extension, dropped entry, deleted file |
| M16–M17 | `signatures/seal.json` | signature byte flip, attacker key swap with re-sign |
| M18 | package root | undeclared extra file |
| M19 | `index.json` metadata | change `type`/`note` without touching any file byte |
| M20 | whole package | install an older self-consistent package |
| M21 | unsigned package | truncate the log tail while the manifest still describes the longer log |

M20 and M21 exist because a hash chain alone cannot answer them: they need a head
commitment (`checkpoint_head` = lifecycle head + evidence root + index metadata digest +
entry count), checked by `S8` (self-consistency) and `S9` (out-of-band pin).

**What this benchmark does NOT prove.**

- It is **single-point mutation**, not an attack-surface enumeration. The failure that
  produced M19 is worth repeating: "we ran a mutation benchmark once" is not "we covered
  the attack surface". A field nobody thought to mutate is invisible here.
- No behavioral / semantic evaluation: a package can be perfectly intact and describe
  behaviour that should never have been allowed.
- No witness, no transparency log, no timestamp authority. `anchored` is the ceiling;
  `witnessed` is not reachable.
- No dependency-free verification: this path needs `pycose` / `cbor2` / `cryptography`.
  A reader who wants "clone and run with the standard library only" should look at the
  shape `draft-stone-aivs-01` specifies, not at ours.

**Using it on another implementation.** The mutations are defined in
`tools/mutation_benchmark.py` and operate on package directories, not on this verifier.
Point your own verifier at `tools/out/_mb/m_M*/` after a run and compare per-case
verdicts; `expected.json` is the shared matrix, `results.json` is ours. If your numbers
differ, that is the interesting result — please open an issue with the case id.

**Portable corpus + plug-in contract.**

```bash
python benchmark/corpus.py     # writes benchmark/corpus/{base,cases/M01..M21,manifest.json}
python benchmark/adapter.py    # runs a SECOND verifier over the same corpus
```

The contract is one function: `verify(package_dir, pubkey_b64, expect_head) ->
"PASS" | "FAIL" | "INCONCLUSIVE"`. Verdicts are per package; the three modes are
properties of the *call*, not of the bytes. `corpus/manifest.json` records, per case,
the authored expectation, the tree digest, and which checks our implementation fired —
so a disagreement can be located, not merely counted.

**First run against a second verifier: 18/21 agree.**

| case | ours | second impl. | why |
|---|---|---|---|
| M17 key substitution, `pinned` | FAIL | PASS | second impl. verifies the seal but does not compare it with the key supplied out-of-band (no S6/V6 pinning) |
| M18 root extra file | FAIL | PASS | no "undeclared file in package root" check (S1) |
| M19 index metadata edited | FAIL | PASS | no index-metadata digest check (S7) |
| M21 unsigned log truncated | FAIL | INCONCLUSIVE | no checkpoint head (S8) |

In `open` mode `M17` is **not** a disagreement: both implementations accept it, and both
should, because no key was supplied to either of them.

That is the corpus doing its job: it found that **our own second implementation lags
the first on three checks** — something "8/8 agreement on fixtures" could never have
revealed. Until it reaches parity, `independent_verifier/` must not be cited as
evidence that a package was checked for these three attacks.

Spec identity: `python -c "import uibc_core as u; print(u.spec_id())"`.
