# The sixteen tests that were skipping, and what they were hiding

**2026-11-19.** Every green run this repository has published until today ended
with `527 tests ... OK (skipped=16)`. Sixteen is 3% of the suite, small enough
to read past. This page reads it.

## The list

| # | where | why it skipped | category |
|---|---|---|---|
| 5 | `test_v14_ots_anchor.py` | `opentimestamps not installed` | missing package |
| 6 | `test_langchain_live.py` | `langchain-core not installed` | missing package |
| 2 | `test_nostr_anchor.py` | `coincurve` / `pynostr not installed` | missing package |
| 2 | `test_aac_emit.py` | `pip install agent-action-capsule` | missing package |
| 1 | `test_quickstart.py` | `corpus already present; self-seeding path not exercised` | deliberate |

Fifteen of sixteen were one thing: **a package that `.[verify]` does not carry**
(`opentimestamps-client`, `langchain-core`, `coincurve`, `pynostr`,
`agent-action-capsule`). Which means these were not merely skipped locally —
CI installs `.[verify]` too, so the interop check against the peer,
the live-LangChain measurement, the OTS proof check and both Nostr anchors
**had never run in CI at all**. They were in the repository, counted in the
527, and never executed anywhere.

## What happens when they are given what they ask for

Measured on the machine that publishes this repository, Python 3.12:

```
$ pip install ".[verify,interop]"
$ python -m unittest discover -s tests -p "test_*.py"
Ran 527 tests in 42.4s
OK (skipped=2)
```

All fifteen pass. Not "pass with a relaxation" — the same assertions, now
running: `10 passed` for the interop and live-agent files, `15 passed, 19
subtests passed` for the two anchor modules. Nothing had to be fixed in them,
which is itself the useful finding: the code was right and the gate was
hollow.

The two that still skip are deliberate, and the reasons now say so:

- `test_quickstart.py` — the self-seeding path is not taken when the corpus
  already exists.
- `test_langchain_live.py::…:151` — "langchain-core is present; covered in a
  bare env". This one is new: it skipped *because* the package arrived. It is
  the control for the no-LangChain case, and the file now covers both sides
  depending on which environment you are in.

## What the gate caught on its first run

The `test-with-extras` job ran once with `.[verify,interop]` and failed — on a
category the audit above had not yet named:

```
SKIPPED [5] tests/test_aee_rail.py: agent_evidence_vectors corpus not installed
```

Five more tests that had never executed anywhere, on the rail that consumes
Sankalp Gilda's external conformance corpus — the one piece of this project
that reads a corpus written by somebody else. `conformance` exists as an extra
(`agent-evidence-vectors==0.36.3`) but no CI job installed it. With it:
`7 passed, 13 subtests passed` in 0.42 s.

So the job now installs `.[verify,interop,conformance]`. This is the useful
shape of the finding: the assertion did not just describe the problem, it
found the next instance of it, in the first minute.

## The gate that stops this recurring

`.github/workflows/ci.yml` gains `test-with-extras`: Python 3.13,
`pip install ".[verify,interop]"`, the whole suite, and then

```
! grep -E "not installed|pip install agent-action-capsule" /tmp/pytest.txt
```

A skip that still smells like an absent package fails the job. Green can no longer
mean "the difficult half was skipped" without someone deleting that line on
purpose.

## Reproduce

```
$ pip install ".[verify,interop,conformance]"
$ python -m pytest tests -q -rs     # 532 passed, 2 skipped, 62 subtests
$ python -m unittest discover -s tests -p "test_*.py"   # 527, skipped=2
```

The number in `README.md` now reads `2 skipped`, and `docs/RELEASE-DRY-RUN.md`
keeps its historical `16 skipped`, because that is what was measured on
2026-11-19 before this extra existed.

## A skip that was lying: the symlink case (`2026-11-19`, Windows)

A second class of skip exists and is not about packages at all: **the host may
be unable to construct the hostile condition**. On a default Windows account
`os.symlink` raises `WinError 1314` (no `SeCreateSymbolicLinkPrivilege`), so
`tools/redteam_robustness.py` could not build its `symlink-out` package.

Until 2026-11-19 the tool swallowed that in `except OSError: return` and went on
to verify a *clean* package - the two implementations dutifully answered
`INCONCLUSIVE`, and the sandbox recorded that as **"the implementations failed
to refuse"**. The same file argues, eight lines from the top, that `INCONCLUSIVE`
must never be the answer to bytes that were never judged. It was doing exactly
that, to itself.

```
before:   symlink-out   JS=INCONCLUSIVE   PY=INCONCLUSIVE   PROBLEM   (problems: 1)
after:    symlink-out   SKIPPED (symlink could not be created on this host (1314))
          9 of 9 hostile inputs answered and refused
          1 case(s) skipped on this platform - not counted as a pass   (problems: 0)
```

The rule now: a case the host cannot build raises `CaseSkipped`, is reported as
`SKIPPED` with its reason, is **never** counted as a pass, and appears in the JSON
as `"skipped": N`. On Windows a clean run therefore reads `skipped=24` where
Linux reads `2` - the difference is the host, not the software, and both numbers
are stated rather than averaged into one.

**Reproduce (Windows, no admin):**

```
$ python tools/redteam_robustness.py     # 9 of 9 ... 1 case skipped, problems: 0
$ python -m unittest discover tests      # Ran 561 tests, OK (skipped=24)
```

## 2026-11-22 · outside re-run on HEAD `7ee526d2` (shallow clone, Linux / Python 3.12)

The "2 skipped" line above was measured before the `conformance` extra existed and
before several tests were added. Re-measured on a clean anonymous clone:

| # | where | why it skipped | category |
|---|---|---|---|
| 1 | `tests/test_lab_bundle.py:147` | needs `UIBC_SLOW=1` for the full release script | manual opt-in |
| 2 | `tests/test_langchain_live.py:151` | `langchain-core` is present, so the bare-env control is not taken | deliberate |
| 3 | `tests/test_quickstart.py:22` | corpus already present, self-seeding path not exercised | deliberate |
| 4 | `tests/test_verify_external_node_report.py:53` | shallow clone does not contain commit `8a95747`; `ci.yml` uses `fetch-depth: 0` | clone-depth artifact |

A full clone gives 3 skips. With all extras:
`python -m pytest tests -q -rs` → `1323 passed, 4 skipped, 100 subtests in 115.9s`;
`python -m unittest discover -s tests -p "test_*.py"` → `Ran 1065 tests ... OK (skipped=4)`.
1065 matches the count pinned in `docs/EVIDENCE-INDEX.md`.