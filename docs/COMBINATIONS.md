# Two defects at once

Every check in this project is measured one mutation at a time - each of the nineteen checks has an artefact that makes it fail, and every field has been probed. Both of those ask about **one** change. A package that carries two is a different question, and the interesting failure is not *both are caught* but **the two explain each other away**: a second change that supplies exactly the consistency the first one broke.

## Method

Fourteen independent mutations of the clean fixture, each caught alone. Then every pair (91) and every triple (364) applied together.

```
$ python3 tools/check_combinations.py --triples
```

## Result

| set | combinations | caught somewhere | caught nowhere | cancelled |
|---|---|---|---|---|
| single | 14 | 14 | 0 | - |
| pair | 91 | 91 | 0 | 0 |
| triple | 364 | 364 | 0 | 0 |

Zero combinations are silent, and zero show the cancelled pattern - two halves caught alone, the combination caught nowhere. The whole run takes under a second, so it is a test rather than a ceremony: `tests/test_combinations.py`.

## The mutations

| mutation | what it does | caught by |
|---|---|---|
| `m-ev0-agent` | event 0 names another agent | S2 |
| `m-ev0-type` | event 0 is not a REGISTER | S3 |
| `m-ev2-prev` | the chain's tail cites nothing | S3 |
| `m-payload` | a hash-shaped claim that is not a hash | S12 |
| `m-root` | the evidence root is one byte off | S5 |
| `m-count` | the declared count is wrong | S12 |
| `m-agent` | the identity names another agent | S2 |
| `m-entry-hash` | one content hash is one byte off | S4 |
| `m-entry-path` | one entry points at a file that is not there | S4 |
| `m-entry-id` | two entries share one id | S4 |
| `m-bom` | the manifest starts with a byte-order mark | S11 |
| `m-no-identity` | identity.json is missing | S1, S2 |
| `m-bad-time` | an event time is not a time | S12, S3 |
| `m-undeclared` | a note nobody declared, at the package root | S1 |

## One thing this caught in the tool itself

The first version put the undeclared file at `evidence/files/extra.txt`, and no check moved. That is not a hole: the format deliberately places structural members under `evidence/` and resolves each by the check that owns it, so a file there is a note until strict mode. Moving the same mutation to the package root - where a `notes.md` that contradicts the evidence has no owner - made S1 fail immediately.

**The same defect, in two positions, has two different verdicts, and both are correct.** A probe that picks one position and reports 'unprotected' would have been wrong about the other.

## What is still untested

Three at a time is not 'any number': 14 mutations have 1,001 combinations of size four, and a careful attacker composes changes with intent rather than randomly. What this establishes is narrower and honest - **no pair or triple from this family cancels**, and the family is one of independent, single-field defects, not of a chained forgery.
