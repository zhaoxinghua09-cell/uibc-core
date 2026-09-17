# experiments/ — append-only evaluation archive

One JSONL line per graded submission. Never rewrite; corrections are new
entries with a `supersedes` field.

Schema:
{"ts": "...", "submission_sha256": "...", "problem_id": "P-01",
 "agent_id": "...", "gate": "ALLOW|DENY|HOLD", "scores": {...},
 "grader_version": "...", "reverified": true|false|null}
