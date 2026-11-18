# Making "the publisher" a checkable thing

The forgery experiment ended on a sentence that is unpleasant and true: in open
mode a package re-signed by a stranger verifies as **PASS**, because the only key
the verifier ever sees came out of the package it is judging. A signature proves
*that key signed these bytes*. It proves nothing about who owns the key.

That sentence cannot be fixed inside the package. Any key shipped with the artifact
is a key the forger can also ship. What can be fixed is the **procedure**: make the
publisher produce two things that travel by different routes, and make the check
between them one command.

## The two things

| piece | what it is | where it must travel |
|---|---|---|
| `package/` | the sealed submission: evidence, lifecycle, manifest, `signatures/seal.json` | anywhere - a release asset, an email, a USB stick |
| `anchor.json` | `pubkey_b64`, `key_id`, `checkpoint_head` | a channel the package cannot reach: release notes, DNS TXT, a transparency log, a signed message to a mailing list |

```json
{
  "schema": "uibc-anchor/0.1",
  "agent_id": "fx-agent-001",
  "key_id": "8b81c862681b712b3541770fcae748a931d6ef3c3b817fe6f71b8dad20e96d07",
  "pubkey_b64": "…",
  "checkpoint_head": "sha256:2935c3f4…",
  "evidence_count": 2
}
```

Two values do the work. The public key answers *who signed this*; the head answers
*in what state*. A forger can produce neither for a package they did not write,
because the head is a digest of state they would have to have written before
publishing, and the key would have to be one the publisher's audience already
knows.

## Why it holds

- **The key is pinned from outside.** Row D of `docs/FORGERY-ENVELOPE.md`: a
  repaired, re-signed forgery fails S6 the moment the verifier holds the
  publisher's key rather than the package's own.
- **The head is pinned from outside.** Row E: a forgery cannot reproduce a head
  it never wrote, so the state must match what was published.
- **Neither is inside the package.** `anchor_check.py` refuses to run without an
  anchor file and says why: an anchor read out of the bundle is the bundle
  vouching for itself.

Both checks run in one command:

```
$ python3 tools/anchor_check.py bundle/
VERDICT: ANCHORED
trust_level: anchored   result: PASS
```

And when they do not hold:

```
$ python3 tools/anchor_check.py forged-bundle/
VERDICT: FAILED
trust_level: unanchored   result: PASS
  - S6 seal signature: Ed25519 signature invalid: … do not match the seal
```

Note the middle line: the package *itself* still says PASS. The anchor is the only
thing that changes the answer. That is the point of separating them.

## The five steps a release actually needs

1. Generate the signing seed somewhere it never touches the repository, and keep
   it (`uibc_core.signing.ed_generate_seed()`).
2. `python3 tools/make_release_bundle.py --out dist/<release> --seed-hex <hex>`
   - `--seed-hex` is required for anything real; the built-in demo seed exists only
     so this page is reproducible.
3. Publish `dist/<release>/anchor.json` **first**, on a channel the package cannot
   reach. The value must be checkable by a stranger who does not trust this
   repository: release notes with the key fingerprint, a DNS TXT record, an
   OpenTimestamps receipt over the head.
4. Publish `dist/<release>/package` (or its tarball) wherever is convenient. Its
   provenance now depends on step 3, not on where it was downloaded from.
5. Anyone can now run the one command. A failure is a failure of the anchor, not
   of a hash the publisher controls.

## What this does not do

- It does not make a package trustworthy to someone who never obtains the anchor.
  Without step 3 the verdict stays `PASS, unanchored` - by design.
- It does not protect against a **wrong** published anchor. A pinned head from
  the wrong release fails loudly (S9), which is the safe direction, but
  publication itself remains a human act with a human trust model.
- It does not yet include the timestamp or receipt in the anchor. `anchor.json`
  has room for them; `docs/IMPLEMENTATION-STATUS.md` tracks that as an open
  step, and `S16` / `S17` already know how to read them when present.

## Current status, stated plainly

`fixtures/clean.uibc` and every package in this repository are sealed with a
fixture key or an unsealed HMAC. **No release has published an anchor.** So
every verdict in this repository today is, at best, `PASS, unanchored`.

That is not a gap in the verifier - it is a gap in the publishing procedure, and
this document is the procedure. Closing it needs one deliberate decision by the
holder of the account: publish an anchor. Until then the honest status stays
zero, and `docs/IMPLEMENTATION-STATUS.md` will keep saying so.
