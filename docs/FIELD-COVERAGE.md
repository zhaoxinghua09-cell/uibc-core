# Every field, and who notices when you change it

F-007 and F-008 were the same shape of defect: a field the package writes, the schema declares, and no check reads. Both were found by asking the question by hand. This is that question asked by measurement, for every leaf field in a package.

Method: copy `fixtures/clean.uibc`, replace one leaf with a different value of the same shape (a 64-hex digest gets one character flipped, a UUID its first character, a string gets `-altered`, a boolean is negated), run `verify`, and record **every check whose result moved** - not only those that moved to FAIL. A field that turns a PASS into an INCONCLUSIVE was noticed too.

```
$ python3 tools/check_field_coverage.py
```

## What it reports

| the alteration | count |
|---|---|
| fields probed | 59 |
| alterations that moved at least one check | 36 |
| alterations that moved nothing | 23 |
| of the moved, percent that reached FAIL | 100% |

## The silent ones, with the reason

A silent field is not automatically a hole. What would be a hole is a silent field with no reason on record, so every one of them is listed and classified, and `tests/test_field_coverage.py` fails if the list grows.

**Descriptive.** Changes the text, changes no verdict, and should not: the schema tag, a version string, an agent type, a media type, a human note.

**Unreferenced.** A value nothing else points at: the chain's last event id (no successor cites it), the evidence ids (the index is read by position, and duplicates are not checked - stated here rather than implied).

**Undecidable without material the package does not carry.** Per-event signatures the format defines no payload for, and an HMAC seal whose secret the verifier does not hold: `S6` reports INCONCLUSIVE, which is the correct answer, not a miss.

**Known gaps.** `manifest.status` and `identity.status` are enums nothing validates. Listed so they are remembered, not excused.

## What this round fixed

`payload_hash` was in every lifecycle event, written by every package, and read by nothing: replace the `null` with any string and every check said what it said before (F-008). `S12` now requires a declared `payload_hash` to be 64 lowercase hex, in both implementations. That checks the shape of the claim, not that it matches a payload the package does not ship - weaker than verifying, stronger than silence.

## Full matrix

| field | changed to | checks that moved |
|---|---|---|
| `manifest.json/schema` | `uibc-core/0.2.2-proposal-altered` | **nothing** |
| `manifest.json/agent_id` | `fx-agent-001-altered` | S2 PASS->FAIL |
| `manifest.json/agent_version` | `0.1.0-altered` | **nothing** |
| `manifest.json/created_at` | `2026-11-06T06:20:54Z-altered` | S12 PASS->FAIL |
| `manifest.json/evidence_count` | `3` | S12 PASS->FAIL |
| `manifest.json/evidence_root` | `09348d857ee5efb322db8c4e611f59e0a727` | S5 PASS->FAIL |
| `manifest.json/status` | `SUBMITTED-altered` | **nothing** |
| `identity.json/schema` | `uibc-core/0.2.2-proposal-altered` | **nothing** |
| `identity.json/agent_id` | `fx-agent-001-altered` | S2 PASS->FAIL |
| `identity.json/agent_type` | `software-agent-altered` | **nothing** |
| `identity.json/owner` | `fixture-owner-altered` | S3 PASS->FAIL |
| `identity.json/created_at` | `2026-11-06T06:20:53Z-altered` | S12 PASS->FAIL |
| `identity.json/status` | `REGISTERED-altered` | **nothing** |
| `identity.json/version` | `0.1.0-altered` | **nothing** |
| `lifecycle.json/schema` | `uibc-core/0.2.2-proposal-altered` | **nothing** |
| `lifecycle.json/events[0]/event_id` | `0816d8ac-d4e6-49f0-bbeb-a6747dacf131` | S3 PASS->FAIL |
| `lifecycle.json/events[0]/event_type` | `REGISTER-altered` | S3 PASS->FAIL |
| `lifecycle.json/events[0]/agent_id` | `fx-agent-001-altered` | S2 PASS->FAIL |
| `lifecycle.json/events[0]/timestamp` | `2026-11-06T06:20:53Z-altered` | S12 PASS->FAIL, S3 PASS->FAIL |
| `lifecycle.json/events[0]/actor` | `fixture-owner-altered` | S3 PASS->FAIL |
| `lifecycle.json/events[0]/payload_hash` | `altered` | S12 PASS->FAIL |
| `lifecycle.json/events[0]/previous_event` | `altered` | S3 PASS->FAIL |
| `lifecycle.json/events[0]/signature` | `altered` | **nothing** |
| `lifecycle.json/events[1]/event_id` | `01ec47d4-fc86-42cd-9ffa-cbebdb393f95` | S3 PASS->FAIL |
| `lifecycle.json/events[1]/event_type` | `ACTIVATE-altered` | S3 PASS->FAIL |
| `lifecycle.json/events[1]/agent_id` | `fx-agent-001-altered` | S2 PASS->FAIL |
| `lifecycle.json/events[1]/timestamp` | `2026-11-06T06:20:53Z-altered` | S12 PASS->FAIL, S3 PASS->FAIL |
| `lifecycle.json/events[1]/actor` | `fixture-owner-altered` | S3 PASS->FAIL |
| `lifecycle.json/events[1]/payload_hash` | `altered` | S12 PASS->FAIL |
| `lifecycle.json/events[1]/previous_event` | `0816d8ac-d4e6-49f0-bbeb-a6747dacf131` | S3 PASS->FAIL |
| `lifecycle.json/events[1]/signature` | `altered` | **nothing** |
| `lifecycle.json/events[2]/event_id` | `0c76ada9-b5cd-40ca-b5cb-717046bc5874` | **nothing** |
| `lifecycle.json/events[2]/event_type` | `UPDATE-altered` | S3 PASS->FAIL |
| `lifecycle.json/events[2]/agent_id` | `fx-agent-001-altered` | S2 PASS->FAIL |
| `lifecycle.json/events[2]/timestamp` | `2026-11-06T06:20:53Z-altered` | S12 PASS->FAIL, S3 PASS->FAIL |
| `lifecycle.json/events[2]/actor` | `fixture-owner-altered` | S3 PASS->FAIL |
| `lifecycle.json/events[2]/payload_hash` | `altered` | S12 PASS->FAIL |
| `lifecycle.json/events[2]/previous_event` | `01ec47d4-fc86-42cd-9ffa-cbebdb393f95` | S3 PASS->FAIL |
| `lifecycle.json/events[2]/signature` | `altered` | **nothing** |
| `evidence/index.json/entries[0]/evidence_id` | `0e0b42ae-444d-4fde-b693-2ee8d7420b79` | **nothing** |
| `evidence/index.json/entries[0]/type` | `ACTION-altered` | S4 PASS->FAIL, S5 PASS->INCONCLUSIVE |
| `evidence/index.json/entries[0]/path` | `files/action-log.txt-altered` | S4 PASS->FAIL, S5 PASS->INCONCLUSIVE |
| `evidence/index.json/entries[0]/content_hash` | `023f8c9abbf6d7252f2731330155932d616a` | S4 PASS->FAIL, S5 PASS->INCONCLUSIVE |
| `evidence/index.json/entries[0]/created_at` | `2026-11-06T06:20:53Z-altered` | S12 PASS->FAIL |
| `evidence/index.json/entries[0]/media_type` | `text/plain-altered` | **nothing** |
| `evidence/index.json/entries[0]/note` | `action log-altered` | **nothing** |
| `evidence/index.json/entries[1]/evidence_id` | `0b638151-910d-46f9-a0a4-d2e34ebbd3fa` | **nothing** |
| `evidence/index.json/entries[1]/type` | `OUTPUT-altered` | S4 PASS->FAIL, S5 PASS->INCONCLUSIVE |
| `evidence/index.json/entries[1]/path` | `files/run-summary.txt-altered` | S4 PASS->FAIL, S5 PASS->INCONCLUSIVE |
| `evidence/index.json/entries[1]/content_hash` | `08e6a809464e4d985baf26520e87e4e7bc27` | S4 PASS->FAIL, S5 PASS->INCONCLUSIVE |
| `evidence/index.json/entries[1]/created_at` | `2026-11-06T06:20:53Z-altered` | S12 PASS->FAIL |
| `evidence/index.json/entries[1]/media_type` | `text/plain-altered` | **nothing** |
| `evidence/index.json/entries[1]/note` | `run summary-altered` | **nothing** |
| `signatures/seal.json/schema` | `uibc-core/0.2.0-proposal-altered` | **nothing** |
| `signatures/seal.json/algorithm` | `HMAC-SHA256-altered` | S6 INCONCLUSIVE->FAIL |
| `signatures/seal.json/key_id` | `12f279663342de18f24b4bb667e64aa2f2fe` | **nothing** |
| `signatures/seal.json/signed` | `identity+manifest-altered` | **nothing** |
| `signatures/seal.json/signature` | `0MPkQLtglIUxn4Iwp/mymsOVMwkrXk7jjk8J` | **nothing** |
| `signatures/seal.json/created_at` | `fixture-altered` | **nothing** |
