# Registries (skeleton, PROPOSAL v0.1)

Three append-only JSONL registries. One JSON object per line. Never
rewrite history — corrections are new entries referencing the old one
(Correction layer, see docs/governance.md).

## certificates.jsonl
Issued certificates (mirror of what `cert-issue` produces):
`{"type":"certificate","evidence_root":"...","key_id":"...","issued_at":"...","expires_at":"...","cert_ref":"path/to/cert.json"}`

## revocations.jsonl
Signed revocations. A gate MUST verify the signature before honoring:
`{"type":"revocation","target_key_id":"...","reason":"...","key_id":"...","signature":"...","created_at":"..."}`

## disputes.jsonl
Dispute flags. Disputes annotate, never silently block (Dispute≠Revocation):
`{"type":"dispute","package_ref":"...","claim":"...","raised_by":"...","status":"open|resolved|withdrawn","created_at":"..."}`

## Rules
1. Append-only; readers sort by `created_at`.
2. Every entry names its signer (`key_id`); trust = verify signature.
3. Registry files are evidence like any other: if mirrored into a `.uibc`
   package, S1–S6 apply.

Empty `.jsonl` files are committed so the paths are stable from day one.
