# A2A Adapter (skeleton, PROPOSAL v0.1)

Goal: let agents speaking Google's A2A (Agent2Agent) protocol discover and
invoke UIBC verification as an agent skill - "verify this package" becomes
an A2A message exchange instead of a CLI call.

## Status: honest skeleton

This directory is a **format definition + mapping table**, not a running
A2A server. Nothing here speaks HTTP yet. See `agent-card.json` for the
declared skill surface and `MAPPING.md` for the A2A <-> UIBC translation.
Implementation order (after v0.3 Ed25519 decision): A2A HTTP server ->
agent-card hosting -> interoperability test against an A2A reference
client.

## Why an adapter and not a fork

A2A and UIBC solve different layers: A2A is transport/discovery between
agents; UIBC is evidence/verification about what agents did. The adapter
keeps both clean (Storage ≠ Protocol, the same discipline as
docs/api-scope.md): A2A carries the request, UIBC does the judging.
