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

- **acceptance rate** = how many mutations passed, period.
- **undocumented acceptance** = those *not* explained by a channel the mode lacks.

Only the second is a defect. Quoting the first without the second invites a reader to
mistake a design boundary for a bug; quoting only the second invites the opposite
mistake — pretending nothing was accepted.

**The two documented boundaries, stated plainly.**

1. `M17` key substitution, `open` only: the key is read out of the package under test,
   so a valid signature proves internal consistency and nothing about who signed it.
   This is why the report carries `trust_level=unanchored` and why the gate policy is
   `PASS + anchored` rather than `PASS`.
2. `M20` whole-package rollback, `open` and `pinned`: an older package is self-consistent
   and correctly signed. Nothing inside it can detect that it was installed over a newer
   one. Only a head observed outside the package (`--expect-head`) catches it — that is
   check `S9`. The same limit is stated independently in
   `draft-ruvalcaba-nhe-audit-00`: an unkeyed chain proves internal linkage, and a party
   able to rebuild the whole chain can produce a consistent alternative.

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

Spec identity: `python -c "import uibc_core as u; print(u.spec_id())"`.
