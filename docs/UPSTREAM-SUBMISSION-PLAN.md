# Where this could be sent, and what each route costs

**Nothing here has been sent. Every route below needs the account holder's
explicit go-ahead**, because each one is an external act that cannot be taken
back. This is the plan, not the act.

The order matters: a submission that cites a verifier nobody can install is a
description of a private project. Steps 1 and 2 come first for that reason, not
for tidiness.

## 1. Publish `0.4.0` — the precondition for everything else

| | |
|---|---|
| What | `python -m build`, `twine upload`, plus a signed tag `v0.4.0` on `main` |
| Needs | PyPI credentials for `uibc-core`; the tag is a force-free push |
| Precedent | the peer is at 0.17.0; we are at 0.3.3, published 2026-11-15 |
| What it unlocks | every number in `README.md` becomes reachable by a stranger |

Before uploading, `tools/check_release_parity.py` and
`tools/version_gate.py` are the gates; `docs/RELEASE-0.4.0.md` describes the five
steps and marks 3–5 as "account holder required".

## 2. Put the 36 packages where a stranger can get them without an account

| | |
|---|---|
| What | attach `conformance/uibc-conformance-0.4.0.zip` to the `v0.4.0` GitHub Release |
| Why a release asset and not a branch | a branch moves; an asset does not, and a stranger can point at a URL and a date |
| Cost | none beyond the release itself |
| Risk | the archive is already public inside the repo, so this changes nothing about exposure |

## 3. Hand it to one outside person

The candidate list is short because the requirement is narrow: someone who will
run a command and report what happened, and who is not the author.

| Candidate | Why | Why not |
|---|---|---|
| a classmate at 湖北师范大学 working in 信息计算与智能系统 | an academic reader, which is the audience the thesis needs | may not have a Linux host; the Windows path is tested but only by us |
| the maintainer of any project that cites a per-action record format | the strongest possible row in bucket 2 | none yet known; `INTEROP-REGISTRY.md` records the search |
| an LLM other than the one that wrote the code | cheap, and it does catch misreadings | an LLM report is not a person; it can support a claim, never replace one |

What they get: a five-line command, a zip, and `docs/OUTSIDER-RUN.md` telling them
what a good result looks like and how to report a bad one. What we get: a
sentence we are allowed to put in a thesis, and a bucket-4 row.

## 4. Submit the draft

| | |
|---|---|
| Venue | IETF SCITT WG (`scitt@ietf.org`) is the natural one for a transparency-record format; a Datatracker submission needs an author account and a naming decision |
| Blocker | our draft describes a verifier and a package format, not a SCITT profile; it would have to be re-cut as a profile or submitted as an independent submission |
| Precondition | steps 1–3 done. Submitted before that, a reviewer's first question ("where do I install it?") has no answer |

The peer's path is instructive and not copyable: their format is a SCITT profile,
so their vectors could go into the SCITT working group's `examples` repository
([PR #3](https://github.com/ietf-wg-scitt/examples/pull/3), merged 2026-06-26). Ours
is not a SCITT profile, so that door is closed until the draft is re-cut or a
different venue is chosen.

## 5. What not to do

- Do not file the draft to create the appearance of standing. A draft with no
  installable implementation behind it is weaker evidence than no draft.
- Do not ask a friendly party for a "registry entry" they do not actually use.
  The peer's own rule — an author's registration is not independent — is the
  reason their page is credible, and it applies to us first.
- Do not claim the JavaScript verifier as external review. It was written here.
