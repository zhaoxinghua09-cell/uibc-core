# UIBC Failure Corpus v0.1

Failures are first-class evidence. This corpus records every failure the
project has hit - in code, in tests, in process - with root cause and
fix status. Golden Fixtures (`fixtures/`) are *engineered attacks*; this
corpus is *failures that actually happened*. Both feed the same goal:
anyone implementing the spec can learn from our mistakes instead of
repeating them.

Format: one JSON object per file, schema below.

```json
{
  "id": "F-001",
  "date": "2026-09-17",
  "category": "code|test|process|docs",
  "summary": "one line",
  "root_cause": "what actually went wrong",
  "detection": "how it was caught (hook / test / external audit / human)",
  "fix": "what changed, or OPEN",
  "lesson": "the transferable rule",
  "fixture_ref": "related fixture or test, if any"
}
```

## Entries

- [F-001](F-001.json) - code: v0.1 verifier accepted a fully self-consistent
  forgery (the founding blind spot; closed by v0.2 strict S6)
- [F-002](F-002.json) - test: suite passed while a second-evidence flow was
  broken (test sealed stale package; fixture regenerated honestly)
- [F-003](F-003.json) - process: stress suite lacked v0.2 signing-path
  coverage (found by live re-run, not by the suite itself)
- [F-004](F-004.json) - test: certificate binding test used two
  content-identical packages - same evidence_root, binding check "passed
  for the wrong package" (same-content => same root is design, not bug)
- [F-005](F-005.json) - docs: external audit found quickstart commands did
  not match the CLI (5 commands, 2 broken verbatim) - docs are code
- [F-006](F-006.json) - docs: ai/benchmarks.md expectations diverged from
  EXPECTED.md on 3 of 8 fixtures - machine-generated truth beats prose

## Rules

1. A failure without a corpus entry is a repeat-offense risk; the ledger
   owner appends within the same session as the fix.
2. Entries are never rewritten - corrections are new entries referencing
   the old id (Correction layer, docs/governance.md).
3. Contest rule: submissions that document a *new* way to break UIBC may
   cite/extend this corpus (see contest/TRACKS.md).
