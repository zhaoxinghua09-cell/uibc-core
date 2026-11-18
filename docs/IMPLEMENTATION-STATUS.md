# Implementation status, in the format the peer uses

Modeled on [RFC 7942] "Implementation Status", the convention IETF readers
recognize, and on `agent-action-capsule`'s own `IMPLEMENTATIONS.md`. The rule
that makes such a page worth reading is theirs and it is right: **an entry owned
by an author of the specification is not independent, however it is worded.**

Date of this page: **2026-11-18**. Every bucket below was checked on that date.

[rfc7942]: https://www.rfc-editor.org/rfc/rfc7942

## 1. Merged upstream

**None.** No change from this project has been merged into any repository it does
not own. `docs/UPSTREAM-SUBMISSION-PLAN.md` lists the ones worth attempting and
what each would require.

## 2. Registry entries by other owners

**None.** No third party has registered an implementation of this format, because
the format has not been published anywhere a registry could point at.

## 3. Proposed / in review

**None.** Nothing is open, so nothing can be reported as open. A draft in a
repository is not a proposal; `drafts/draft-zhao-uibc-evidence-chain-00.md` has
never been submitted to any venue.

## 4. Independent implementations and reviews

**None independent of this project.** The JavaScript verifier in
`tools/verify-js/` shares no code with the Python one and was written from the
prose, which is the property that matters — but it was written here, by the same
author, so by the rule above it does not count as independent adoption. It
counts as a *second implementation*, and it is the strongest internal evidence
this project has; it is not external evidence at all.

The conformance suite (36 packages) and the hostile-input table (10 cases) are
likewise internal: they can be handed out, but as of this date they have not
been.

## What this page is not

It is not modesty. It is the honest answer to the question a reviewer asks
second, after "what does it do": *who else has used it?* For one project in this
space the answer is a merged WG contribution, a third-party product and a public
log; for this one it is four empty buckets and a draft nobody has read. See
`docs/COMPETITORS.md` for the two projects side by side on the same day.

The buckets fill in this order, and only in this order:

1. Publish a version someone can install (`0.4.0`, `pip install uibc-core`).
2. Put the 36-package suite somewhere a stranger can download it without an
   account.
3. Hand it to one outside person and record what they ran.
4. Then, and only then, the draft is worth submitting: a draft citing a
   verifier no one can install is a description of a private project.

Anything filed before step 1 is a claim; anything filed after step 3 is a
finding.
