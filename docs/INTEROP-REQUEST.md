# Interoperability request (standing, low-friction)

This is not a partnership pitch. It is one concrete question addressed to any project
that publishes an agent-evidence format, and a command that answers it in ten minutes.

## The question

> Given the same fifteen inputs, does your canonicalization and your Ed25519 verification
> produce the same bytes and the same verdicts as ours?

The inputs and expected values are in [`docs/conformance/vectors.json`](conformance/vectors.json).
Nothing needs to be installed from us, and no account is needed:

```bash
python tools/conformance_check.py     # our checker: imports nothing from this repo, uses `cryptography`
```

An implementation that disagrees on any vector is not "wrong" — it is **different**, and
that difference is exactly what an interoperability matrix should record. We would rather
publish "they canonicalize `1.0` as `1` and we do not" than publish a green cell nobody
tested.

## What we are not asking for

* not an endorsement, a review, or a quote we can put on a page;
* not a change to your format;
* not a favour that only flows one way — the same file is the answer to the same question
  asked of us, and we publish our failures in `docs/REVIEW-LOG.md`.

## What we will publish, whatever the answer

The result goes in `docs/INTEROP-MATRIX.md`, with the responder's own words and the exact
command they ran. If a project declines, the matrix says "asked, declined" — which is a
fact about the field, not a verdict about them.

## Channels, as measured on 2026-11-17

| project | channel | state |
|---|---|---|
| NovaFabric | GitHub issues on `novafabric/novafabric` | tracker is open (13 open issues), but **posting failed: 401** — the fine-grained token on this machine is scoped to its own repositories and cannot write to a third-party repository. The text is prepared and must be posted by the account holder, or with a token whose scope allows it |
| agent-receipts | GitHub `agent-viscro/agent-receipts` | repository not reachable through the API on this date (404), so no issue could be filed |
| Vaara | no public issue tracker found | not contacted |
| Tracekit | arXiv preprint only, no repository found | not contacted |

No email addresses were guessed. A message to an address we invented is worse than no
message. Nothing in this file should be read as "we asked and they answered" — as of this
date, nothing has been sent.
