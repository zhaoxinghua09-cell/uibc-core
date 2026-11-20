# Example: audit a *published* release you did not produce

`tools/conformance_harness.py` is the inbound direction: someone else's verifier
runs our corpus. This directory is the outbound direction: **our implementation
audits someone else's published artifact**, and the receipt says what we
recomputed and whether it matched what they published.

The artifact audited first was a live one — `dfr.derappar.at`, release
`Apparat-2026-09-27-5F33DA`, 56 rows — chosen by the register's author, not by
us. The tool was then generalised so the same receipt can be produced for any
register with the same shape (sealed entries, an RFC 6962 commitment, a signed
digest, a published file-hash list).

## Re-run it against the live release

```bash
python tools/audit_sealed_release.py \
  --root https://dfr.derappar.at \
  --release-id Apparat-2026-09-27-5F33DA \
  --out receipt.json
```

Five checks run:

| Step | What it recomputes | What it compares against |
|---|---|---|
| `1-entry-seals-and-merkle` | each entry seal over JCS of six fields, then an RFC 6962 root | `release_commitment`, and each row's published seal when present |
| `2-release-digest` | SHA-256 over JCS of seven digest fields | `release_digest` |
| `3-signature` | ECDSA P-256/SHA-256 over those canonical bytes | `anchor.signature_b64`, `anchor.key_id` |
| `5-chain-walk` | `previous_release_commitment` against the predecessor in the index | the register's own claim about its chain |
| `6-file-hashes` | SHA-256 of every file named in `file_hashes`, fetched as served | the published values |

Exit codes: `0` every check ran and agreed, `1` a check ran and disagreed, `2`
a check could not run. `1` and `2` are kept apart because "we disagree" and
"we could not look" are different claims, and printing the second as the first
is how audits become fiction.

## The result on the live release (2026-11-20)

| Step | Outcome |
|---|---|
| 1 | 56/56 seals; root `4b85a5b6…` = published |
| 2 | `e5dacf1a…` = published |
| 3 | verified; `key_id` matches only when read as SHA-256 over DER SubjectPublicKeyInfo |
| 5 | 10 releases, exactly 1 broken link (`…5885 → …A431`), agreeing with the author's own disclosure |
| 6 | **`index.html` and `latest.html` do not match their published hashes**; the other five files do |

The two HTML failures have a probable cause and it is *not* claimed as one:
both responses carry `static.cloudflareinsights.com/beacon.min.js`, so an edge
is injecting analytics into HTML. Two fetches minutes apart returned identical
bytes, so it is not per-request churn. The receipt states only what was
measured — the served bytes differ from the registered hash — and names the
likely cause as a hypothesis.

## Three defects this port produced, kept as notes

Every one of these made a *wrong answer that looked right*, which is why each
has a test in `tests/test_audit_sealed_release.py`:

1. **Per-release pages share a basename.** Every release page in this profile
   is `<release_id>/release.json`, so an offline cache keyed on the URL
   basename collapses all ten releases onto one file and reports a clean
   chain. The cache is now keyed on the release id, and a page answering with a
   different id is an error, not a hit.
2. **An unreadable file counted as a match.** `failed` only collected
   `ok is False`, so three missing files left the step green. Unreadable is now
   its own bucket and makes the step `not run`, never `passed`. This is the same
   failure the corpus harness's `CONTROL-VACUOUS` exists to catch.
3. **`row_count` is a number in the file and a string in the preimage.** The
   register publishes `56`; the digest is computed over `"56"`. Recomputing with
   the number produced a digest mismatch that looks exactly like a bad
   signature. This is the profile's stated reason for carrying it as a string,
   and it is the same class of divergence our own canonicaliser was fixed for
   on the same day.

## What this does not show

- It does not show the register is wrong. The cryptographic checks all pass;
  one check failed on served bytes, not on their construction.
- It does not verify the Rekor *inclusion proof* mathematics. The anchor fields
  (log index, integrated time, log id, logged hash, logged signature) are
  compared; the proof itself is not folded, and the receipt says so.
- It does not verify `build_provenance`, `anchor_status` or `signer.name`:
  none of these are covered by the signed preimage, so they are readable and
  unverifiable. The receipt lists them as such rather than silently ignoring
  them.
- It does not turn any of this into a claim of superiority. One audited
  artifact, audited once, by its own specification's rules.
