# AUDIT-KIT.md — three questions an outsider can ask, and the command that answers each

This document exists because "trust us" is not evidence. Everything below runs offline, needs no account, and produces numbers you can compare against ours. If your numbers differ from ours, that is the most useful thing you can send us.

## Zero: the archive that needs no repository

`conformance/uibc-conformance-0.4.1.zip` — sha256 `711fa82c9f183066cfae6441a4fe3fc27fcc516b25f2a976cad5e0dd61b5135f`, 228,000 bytes. Pin: `anchors/pins/uibc-conformance-0.4.1.sha256`. The build is deterministic for a given tree, and this hash is reproducible only from the tree that produced it: `0.4.1` was built at commit `d72c4f9`, and rebuilding from today's tree gives `083c0dbc…` because the runner template was fixed afterwards. `tools/build_conformance_bundle.py` therefore refuses to overwrite a pinned archive whose bytes would change, and prints both hashes (measured 2026-11-20, exit 3). A version number names one set of bytes; "latest" does not.

```
python run.py
```

**One command, no install.** The archive carries `uibc_core.pyz` (the reference verifier as a single file) and `run.py` uses it by default, so this works offline, on a machine that has never seen this project, in about six seconds.

`strict 36/36` on the reference verifier, and a `receipt.json` you can publish. A verifier that answers `PASS` to everything scores **6/36**, so the corpus cannot be passed by refusing nothing. Point it at another implementation with `--verify "cmd {pkg}"`.

If the verifier is not installed for the Python you are using, `run.py` **exits 3 and writes no receipt** — 36 rows of `FAIL` with no parseable output look exactly like a corpus that fails everything, and that is not a result. Found by walking this page as a stranger on 2026-11-20.

One case that promised the same thing and did not deliver it: if the command you hand to `--verify`
**cannot be started at all** (`--verify "uibc verify {pkg}"` on a machine where `uibc` is not on
`PATH`), the **shipped 0.4.1 archive exits 1 with a traceback and writes no receipt** — measured
2026-11-20. The build template now catches that and exits 3 with the reason on stderr, so any archive
built after that change behaves as promised; the shipped 0.4.1 predates it. Both facts are written
here rather than fixed silently in the prose, because changing the bytes of a pinned archive would
make every pin and every receipt cite a hash that no longer exists.

What that is not: a self-run. 36/36 here was produced by the maintainer on one machine. It becomes a third-party reproduction only when someone else runs this same hash elsewhere and publishes the receipt.

**Sunset clause (self-binding).** If no unrelated party has run this archive hash and published a receipt by **2027-05-19**, the public catalogue line "re-runnable by an outsider" is downgraded to "self-run only", and this section is edited to say so rather than left standing. The clause is written before the outcome is known, which is the only thing that makes it a commitment instead of a footnote. Same form as `draft-templeman-scitt-measurement-capsule-00` §The Experiment, which puts external recomputation into its acceptance criteria and states the draft is withdrawn if none occurs.

## Question 1: can every check be made to fail?

A check nobody can make fail is decoration.

If you have not cloned anything, the corpus is one anonymous download away — no login, no token, no
`pip install`:

```bash
curl -fL -o corpus.zip \
  https://github.com/zhaoxinghua09-cell/uibc-core/raw/main/conformance/uibc-conformance-0.4.1.zip
sha256sum corpus.zip   # 711fa82c9f183066cfae6441a4fe3fc27fcc516b25f2a976cad5e0dd61b5135f
unzip -q corpus.zip -d corpus && cd corpus && python run.py
```

Expected: `strict 36/36`, a `receipt.json`, exit 0. Measured this way on 2026-11-20 (download →
unzip → run, `PYTHONPATH` empty, nothing installed): the archive came down as 228,000 bytes with
that hash, and the run printed `strict 36/36` with `verifier_version 0.4.1 / cases 36 / passed 36`.

Note what changed on 2026-11-20: the release page used to carry no archive for this corpus at all —
the only release asset anywhere was `uibc-conformance-0.4.0.zip`, a 30-case archive under a different
version. Running the release workflow for the existing `v0.4.1` tag attached
`uibc-conformance-0.4.1.zip` (228,000 bytes, the pin's hash) to
`https://github.com/zhaoxinghua09-cell/uibc-core/releases/download/v0.4.1/uibc-conformance-0.4.1.zip`.
Both that and the raw URL above serve the same bytes; `tools/check_outsider_entry.py` fails if either
disappears from the documents, or if a document points at an asset for a different version. The commands below need the
repository, because they rebuild the suite rather than run it.

```
python3 tools/export_conformance.py
python3 tools/check_falsifiability.py
```

It asks, for each of the **nineteen** checks, whether a package we publish can drive that check to `FAIL`. Two checks cannot be reached from inside a package, so they are covered separately by the outsider audit (a real RFC 3161 token and four mutations of it for S16; a head observed outside the package, then a rollback only that observation can see, for S9).

**What to compare:** the count of checks with a published artefact, and the identity of any check without one.

## Question 2: is every field judged by somebody?

```
python3 tools/check_field_coverage.py --json
```

It copies the clean fixture, replaces **one leaf field** with a different value of the same shape — a 64-hex digest gets one character flipped, a UUID its first character, a string gets `-altered`, a boolean is negated — runs `verify`, and records **every check whose result moved**, in either direction.

An empty set is not automatically a defect: a note field or a media type legitimately changes nothing. The point is that every field now has a recorded answer, and a reviewer can disagree with the answer instead of guessing it.

**What to compare:** the list of fields that move nothing, and whether each of them is argued for in `docs/FIELD-COVERAGE.md`.

## Question 3: does a verifier we did not write agree?

```
python3 tools/run_conformance.py --verify "<your verifier command>"
```

The suite is 36 packages derived from one correct package, each broken in exactly one declared way. A case passes only if the verifier reports `FAIL` and names at least one of the expected checks; cases that must be accepted must not be refused.

If you write your own verifier, point this at it. That is the single most useful contribution anyone can make to this project, and it is the one thing we cannot do for ourselves.

## What this kit does not establish

| Not established | Why it matters |
|---|---|
| Independent human reproduction | The receipts in `docs/external-review/` are from external models, not people. Machine review does not carry a person's accountability. |
| Scientific validity of any score | No criterion correlation, no inter-rater study, no calibration against labelled risk. See `LIMITATIONS` in this directory. |
| Production use | Every artefact here is from an experimental environment. No customer authorisation exists, so `deployed` would be false. |
| Correctness against the real world | Passing 36 packages means the verifier refuses the 30 declared mutations and accepts the 6 correct ones. It does not mean the model of evidence is right. |

## Reporting a result

Send the command, the version you ran (`git rev-parse HEAD` or the installed version), the date, and the raw output. We publish disagreements, including the ones where we turn out to be wrong — see `failure_corpus/` for how that is recorded.
