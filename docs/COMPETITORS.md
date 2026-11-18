# Two projects in the same neighbourhood, measured on the same day

**Date of measurement: 2026-11-18.** Every number below can be re-run with the
command beside it. Nothing here is a claim about quality — the table lists what
each project ships, and the section after it says plainly where this project is
behind.

The other project is **`agent-action-capsule`** (AAC), the reference verifier for
`draft-mih-scitt-agent-action-capsule`, from Action State Group. It is the closest
thing to a peer this project has: same subject (a sealed record of what an agent
did, and a way for a third party to check it), same instinct (a format plus a
verifier that refuses malformed input).

## The two projects, side by side

| | `uibc-core` | `agent-action-capsule` |
|---|---|---|
| Version measured | 0.4.0-dev on `main` (`1f7c957`); 0.3.3 on PyPI | 0.17.0 on PyPI |
| First published | 4 releases, latest 2026-11-15 | 23 releases, latest 2026-11-18 |
| Specification | In this repo: `drafts/draft-zhao-uibc-evidence-chain-00.md`, **not submitted** | IETF Internet-Draft `draft-mih-scitt-agent-action-capsule`, referenced from the package itself |
| Licence | Apache-2.0 | BSD-3-Clause |
| Language of the verifier | Python (first) **and JavaScript (second, independent)** | Python only |
| Verifier modules | 25 | 40 |
| Test files / test functions | 30 / 524 | 95 / 1189 |
| Conformance material | 36 packages (6 positive, 30 mutations), shipped as its own zip | `vectors/` in the repo, referenced by tests, not in the sdist |
| Second implementation is a **CI gate** | Yes — `second-implementation` job, 18 of 19 checks, 36/36 identical FAIL sets | No second implementation to gate |
| Hostile-input suite | `tools/redteam_robustness.py`, 10 cases, table in `docs/ROBUSTNESS.md` | `tests/test_json_nesting_vectors.py`, `tests/test_verify_bounds.py`, `tests/test_parse.py` |
| Deep-nesting ceiling | **512 levels, both implementations, refuses with S11** | 128 levels, refuses at parse time |
| External time proof | RFC 3161 timestamp verified in both implementations (real FreeTSA token, 7/7 red-team on the token verifier) | SCITT transparency log via an anchor client and witness records |
| Stars / forks | 11 / 2 | 2 / 6 |
| Last push | 2026-11-18T15:11Z | 2026-11-18T14:57Z |

Re-run the machine-checkable half:

```
python3 tools/check_doc_facts.py            # ours: 524 tests, 19 checks, 36 cases
python3 tools/redteam_robustness.py         # ours: 10 of 10 refused
python3 tools/cross_impl_check.py --json    # ours: 36 of 36 identical
```

For AAC, install and run its CLI on the same hostile inputs:

```
pip install agent-action-capsule==0.17.0
agent-action-capsule verify notjson.json    # exit 2, "cannot read capsule"
agent-action-capsule verify nan.json        # exit 1, ok: False
agent-action-capsule verify deep.json       # exit 2, "nested more than 128 levels deep"
agent-action-capsule verify badutf.json     # exit 2, "utf-8 codec can't decode"
```

Measured 2026-11-18: all four refused, none crashed. Their depth ceiling is
explicit and their message names the limit — **that is better than what this
project did until today**, which recursed until the stack ended and reported S0
("the verifier broke") for an input the verifier had simply never been built to
survive. The lesson was taken: `MAX_NESTING = 512`, counted outside string
literals, refused as S11 on both sides, and the same treatment for a manifest
that parses as an array (it used to reach `.get()` and raise).

## Where this project is behind, stated plainly

1. **Specification standing.** AAC's format has an Internet-Draft. `uibc-core`'s
   has a draft in this repo and no submission. This is the single largest
   difference in external credibility, and no amount of local testing closes it.
2. **Release cadence.** 23 releases against 4. AAC ships weekly; this project
   tags when a chapter of work closes.
3. **Surface area.** 40 modules against 25. AAC covers COSE/CBOR carriers,
   bilateral flows, ERC-8183 and x402 adapters, an anchor client, witness
   records. This project covers one format and one verifier, and says so.
4. **Test count.** 1189 against 524.

## Where this project is ahead, also stated plainly

1. **A second implementation that shares no code.** AAC's 1189 tests are all in
   Python: they can find a bug in the code, never a misreading of the spec. The
   JavaScript verifier here was written from the prose, and its value is that it
   disagrees — it found four bugs in the Python side (S12's missing
   `evidence_count` comparison, S5 scoring a package twice, the NaN hole, the
   array-manifest crash). Agreement on 36 of 36 packages across two languages is
   the one claim here that cannot be made by a single-language project at any
   test count.
2. **Second implementation enforced by CI, not by intention.** The gate fails the
   build on any drift. A project that has no second implementation cannot have
   this gate.
3. **The conformance suite is a shippable artefact.** 36 packages in their own
   zip, runnable by anyone, positive and negative, with the mutation recorded in
   each case's name. It is the thing that can be handed to a third party who
   wants to check *us*.
4. **A hostile-input table where each row is a verdict.** Ten cases, both
   implementations, three properties (no crash, a verdict, a refusal), and the
   document explains why the two verdict lists may differ without being
   inconsistent.
5. **Anchoring checked in both languages, on a real token.** The RFC 3161
   verifier is written in Node with no dependencies, cross-checked against
   Python's `cryptography`, and red-teamed against seven token mutations.

## What "ahead" does not mean here

It does not mean "全面超越". On specification standing and release cadence this
project is clearly behind, and those two are the ones a reviewer will look at
first. What it means is narrower and checkable: **a claim that two independent
readers agree on the same packages cannot be produced by a one-language project,
and this project can produce it.**

The honest next step is not more local tests. It is:
- submit the draft, so the format has a standing that is not self-declared;
- publish 0.4.0, so the numbers above are reachable by a stranger;
- hand the 36-package suite to one outside person, so "two implementations
  agree" stops being a claim made only by the two implementations.
