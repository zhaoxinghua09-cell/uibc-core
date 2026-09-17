# A2A <-> UIBC Mapping (normative for the future adapter)

| A2A concept | UIBC counterpart | Rule |
|---|---|---|
| Agent Card | ai/manifest.json + adapters/a2a/agent-card.json | card advertises skills; UIBC manifest advertises specs |
| Message (task) | one gate/verify invocation | request carries package path/bytes; response carries the full verification report |
| Artifact | verification report JSON | reports are evidence: hash them if archived |
| Skill | verify_package / gate_check / cert_verify | 1:1 with MCP tools (mcp_server/) - same functions, different transport |
| Push notification | not supported | verification is synchronous; long jobs are out of scope |

Transport mapping:
- A2A `message/send` with skill `verify_package` ->
  `uibc_core.verify.verify(path, key)` -> report JSON as artifact.
- Errors: verifier exceptions map to A2A task-failed; verifier FAIL is a
  *successful* task whose artifact says FAIL (a detected forgery is a
  result, not an error).

Trust boundary (unchanged): the adapter trusts the local filesystem it
reads. Remote package submission (upload-and-verify) is deliberately out
of scope until v0.3 (Ed25519) - under HMAC there is no safe way to hold
strangers' keys.
