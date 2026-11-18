# Hostile input: ten cases, two implementations, zero crashes

A conformance suite measures the attacks someone thought of. It says nothing
about the bytes nobody thought of. This page is the other half: inputs that are
not packages at all, or that are packages built to break a reader.

Run it yourself:

```
python3 tools/redteam_robustness.py
```

Each case starts from `fixtures/clean.uibc`, applies one mutation, and runs both
implementations. `--json` gives the table below as machine-readable output.

## The rule

Two properties, neither negotiable:

1. **Both answer.** A crash is not a verdict. A verifier that dies tells the
   caller nothing about the file it was handed, and a process that exits
   non-zero with no report is indistinguishable from a process that was
   interrupted.
2. **Both refuse.** "Could not tell" about bytes that were never judged is the
   one wrong answer that looks honest. INCONCLUSIVE means "nothing found wrong",
   and nothing can be found in bytes that were never read as JSON.

## Results, as measured

| input | JavaScript | Python |
|---|---|---|
| `{oops` | FAIL S11 | FAIL S11 |
| `manifest.json` is an array | FAIL S1, S2, S5, S12 | FAIL S1 |
| duplicate member name | FAIL S11 | FAIL S11 |
| a bare `NaN` literal | FAIL S11 | FAIL S11 |
| 4000 levels of nesting | FAIL S11 | FAIL S11 |
| invalid UTF-8 in identity | FAIL S11, S2, S3 | FAIL S11 |
| evidence path `../../etc/passwd` | FAIL S4 | FAIL S4 |
| symlink to `/etc/hostname` in evidence | FAIL S4, S12 | FAIL S4, S12 |
| an empty directory | FAIL S1, S2, S3, S4 | FAIL S1, S2 |
| an 8 MB manifest | FAIL S1, S2, S5, S12 | FAIL S2, S5 |

10 of 10 answered by both, 10 of 10 refused by both, 0 crashes.

## Why the verdicts are not identical

Four of the ten are byte-level failures that stop both readers at the same
place. The other six fail later and cascade differently:

- **Both implementations now stop when the bytes never became JSON.** S11 runs
  first and returns early on invalid UTF-8, a repeated member name, a document
  past the nesting ceiling, or bytes that do not parse. Nothing downstream can
  be judged from bytes nobody read, so nothing downstream is claimed.
- **JavaScript keeps going on two cases** (an array manifest, an 8 MB manifest)
  and reports the later checks that also lost their input, because in JavaScript
  those checks degrade to a report rather than an exception. Every extra line is
  true; a cascade is noisy, not wrong.
- **Deep nesting is now S11 on both sides.** Until 2026-11-18 it was S0 on both:
  the reader recursed 4000 levels and the stack ended. That was reported as "the
  verifier broke", which is a statement about us, not about the input. A
  ceiling of 512 levels, counted outside string literals, makes it a verdict.
  The idea came from `agent-action-capsule`, which refuses at 128 levels with a
  message that names the limit; see [COMPETITORS.md](COMPETITORS.md).
- **A manifest that parses as an array used to reach `.get()` on Python** and
  raise `AttributeError`, again landing on S0. S1 owns "the structure is not the
  structure", so S1 is what reports it now.

The rule for the future is not "make the two lists identical" - it is "never
call bytes unjudged and then report INCONCLUSIVE", and "never report a
predictable input shape as a broken verifier".

## The hole this found

Python's `json` module accepts `NaN`, `Infinity` and `-Infinity` by default,
although RFC 8259 defines none of them. Before this check, a manifest carrying
`"remark":NaN` parsed, every later check found nothing wrong with the fields it
looked at, and the package came out **INCONCLUSIVE** - an honest-looking answer
about a file that is not JSON. The S11 byte scan never asked whether the bytes
parse; it asked whether they are UTF-8, carry duplicate names and contain control
characters.

The fix is one line on each side, in the same check:

- Python: `json.loads(text, object_pairs_hook=hook, parse_constant=reject)`.
- JavaScript: `JSON.parse(text)` inside S11's try, which refuses `NaN` for free.

A parser that is more permissive than the format is a parser that cannot refuse
the format's violations. This is the sort of defect a second language catches
and a second test file keeps caught.
