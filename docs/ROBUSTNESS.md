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
| `{oops` | FAIL S11 | FAIL S11, S2, S5 |
| `manifest.json` is an array | FAIL S1, S2, S5, S12 | FAIL S0 |
| duplicate member name | FAIL S11 | FAIL S11 |
| a bare `NaN` literal | FAIL S11 | FAIL S11 |
| 4000 levels of nesting | FAIL S0 | FAIL S0 |
| invalid UTF-8 in identity | FAIL S11, S2, S3 | FAIL S11, S2 |
| evidence path `../../etc/passwd` | FAIL S4 | FAIL S4 |
| symlink to `/etc/hostname` in evidence | FAIL S4, S12 | FAIL S4, S12 |
| an empty directory | FAIL S1, S2, S3, S4 | FAIL S1, S2 |
| an 8 MB manifest | FAIL S1, S2, S5, S12 | FAIL S2, S5 |

10 of 10 answered by both, 10 of 10 refused by both, 0 crashes.

## Why the verdicts are not identical

The two implementations put different names on different layers, and this is
visible only when a package fails early:

- **JavaScript stops at S11 when the bytes are not JSON.** Nothing below can be
  judged, so it returns immediately with the one check that can say what
  happened. Before this was fixed it fell through to S0, which means "the
  verifier broke" - the wrong statement about who is at fault, and it hid the
  check that had the answer.
- **Python continues**, so a later check also reports its own missing input
  (S2 for an unreadable manifest, S5 for a root it cannot compute). A cascade is
  noisy but not wrong; each line is true.
- **Deep nesting lands on S0 on both sides.** Neither reader is built to
  recurse 4000 levels, so both fail closed and say so. S0 is precisely the
  check for "the verifier could not finish", and it is the honest answer here.

The rule for the future is not "make the two lists identical" - it is "never
call bytes unjudged and then report INCONCLUSIVE".

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
