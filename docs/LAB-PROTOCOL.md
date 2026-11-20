# Lab protocol — the four things a run has to carry

A run is a number. Evidence is a number plus the bytes it decided, a control that
proved the suite discriminates, an outcome that separates "the verifier did not
run" from "the corpus failed", and a declaration of what the runner already knew.
This repository's receipts carry the first; `docs/RECEIPT-FORMAT.md` says what
makes them quotable. This page is the layer above: a run as a **bundle**.

Build one:

```bash
python tools/lab_manifest.py --dir run/ --archive uibc-conformance-0.4.1.zip \
    --question "Does 0.4.1 reject a flipped evidence byte?" \
    --claim "the corpus decides this, and a naive checker does not" \
    --runner "Your Name <you@example.org>" \
    --blind "directed — I read the checks before running" \
    --command "python run.py" --exit-code 0 \
    --hostile-what "a verifier that answers PASS to everything" --hostile-result 6/36 --cases-total 36 \
    --positive-what "the shipped clean package" --positive-result "PASS" \
    --negative-what "no verifier installed for this interpreter" --negative-result "exit 3, no receipt written" \
    --limits "single corpus; AEE predicate only; no anchor" \
    --out lab_bundle.json
```

Check one:

```bash
python tools/check_lab_bundle.py lab_bundle.json --dir run/ --archive uibc-conformance-0.4.1.zip
```

## The four carried facts

| fact | field | what a checker refuses |
|---|---|---|
| the bytes | `bytes[]` — path, size, sha256, media type per file | a digest that does not recompute, a file missing from disk, an empty list |
| the discriminator | `controls.hostile.result` + `cases_total` | a hostile control that scored full marks — that means the corpus lets an accept-everything verifier through |
| the environment | `run.exit_code`, `run.stdout_tail` | a bundle with no exit code, or a table replaced by a sentence |
| the runner's prior knowledge | `exposure.blind`, `declared_by`, `declared_utc` | a blank exposure, an unattested declaration |

Two more are required but not checkable by machine, which is why they are
*declared* rather than verified: `roles.runner` (who ran it) and `limits` (what
this run does not cover — an empty list reads as claiming everything).

## Blind and directed are different evidence

*Directed* means the runner read this repository's checks, its expected reasons,
or its vectors before or during the run. That is not disqualifying and is not
hidden: it changes what the number supports. The two are never added together and
never averaged in `docs/RUNS.md`.

## The release bundle, measured by the release script

`tools/release_lab_bundle.py --version <v>` runs three scenarios in throwaway
directories and refuses to write anything if a control misbehaves:

| scenario | what runs | what it must show |
|---|---|---|
| A | the archive as shipped, `python run.py`, no install | full pass, and a receipt with `passed == cases` |
| B | the same archive with `--verify` pointed at a verifier that answers PASS to everything | **far below full** — 6/36 on 0.4.1; full marks would mean the corpus does not discriminate |
| C | the bundled verifier removed and none installed | **exit 3, no receipt** — an environment failure must not be publishable as a corpus result |

Outputs: `uibc-lab-bundle-<v>.json`, `receipt.json` from scenario A, the archive copy,
and `CORPUS-DIGESTS.txt` (sha256 + size for each). `.github/workflows/release-lab-bundle.yml`
runs it on a version tag, re-checks the bundle with `tools/check_lab_bundle.py`, and
attaches the four files to the release. It fires only when a maintainer pushes a tag;
it publishes nothing on its own.

Measured on 0.4.1, 2026-11-20: `36/36` positive, `6/36` hostile, `exit 3` negative, 15 s.

## The digest list is signed, and the external anchors are recorded

`tools/anchor_release_digests.py` adds three things to `CORPUS-DIGESTS.txt` and states which
of them happened:

| output | what it is | failure looks like |
|---|---|---|
| `.sig` | Ed25519 over the exact bytes, public key in the sidecar | no key → `UNSIGNED.txt`, and the demo seed is refused rather than warned about |
| `.tsr` + `_ca.pem` | RFC 3161 token from an independent TSA, verifiable offline | `unanchored` |
| `.ots` | OpenTimestamps proof | `pending_calendar` when it is a calendar attestation; the word Bitcoin is not printed for it |
| `ANCHORS.json` | one state per item: `anchored` / `pending_calendar` / `unanchored` / `unavailable` / `not attempted` | the state is the output; no summary sentence can turn a failure into success |

Offline verification:

```bash
python tools/anchor_release_digests.py verify --sig release/CORPUS-DIGESTS.txt.sig
python tools/anchor_tsa.py --verify release/anchor_freetsa.tsr \
    --data release/CORPUS-DIGESTS.txt --cabundle release/anchor_freetsa_ca.pem
```

Measured 2026-11-20 on a throwaway digest file: signature verified; one flipped byte produced two
reasons (hash and signature); FreeTSA answered and its token verified offline (`signature_verified:
true`, `problems: []`); OpenTimestamps reported `unavailable` because the client is absent here,
and the report says exactly that.

The workflow signs only when `UIBC_RELEASE_SEED_HEX` exists and ships `UNSIGNED.txt` when it does
not. It also **opens the release if the tag has none**, because `gh release upload` has nowhere to
put a file otherwise: measured 2026-11-20, the repository carried a `v0.4.1` tag and no `v0.4.1`
release, which is why the newest asset for this corpus was still `0.4.0`. Before that step existed,
"push a tag" and "a release exists" were two different acts and only the first was automated.
**It has now run on a published release, once.** Workflow run `44671945364` (2026-11-20,
`gh workflow run release-lab-bundle.yml -f tag=v0.4.1 --ref main`) attached
`anchor_freetsa.tsr` (4,643 B) and `anchor_freetsa_ca.pem` (5,107 B) to `v0.4.1`, and its
`ANCHORS.json` records `tsa: {"state": "anchored", ...}`. Read back over the anonymous release
URL and verified offline: `signature_verified: true`, `problems: []`, `gen_time`
2026-11-20T04:05:27Z, serial 171991794, attested digest
`8b3818af643a35eebe795397acce8ba47bbfc718117146dd9f6cf4af0a9628ab` — the SHA-256 of the
`CORPUS-DIGESTS.txt` the same release serves. `python tools/check_release_anchors.py` re-runs
that check in one command and exits 0/1/3.

The first workflow run, 20 minutes earlier, had recorded `unanchored` with
`NameError: name 'tsp' is not defined` — a missing package, not a TSA refusal; the fix is in
`#306`. Two of the three OpenTimestamps calendars (`alice`, `finney`) answered HTTP 503 on
2026-11-20 while `bob` answered, so the stamper now tries all three in order and names the one
that answered instead of reporting the first outage as "unavailable". The signature is still
absent: `UIBC_RELEASE_SEED_HEX` is not configured, and `UNSIGNED.txt` is what the page carries.

## What this protocol is not

- It is not the lab protocol `probityai/agent-evidence-vectors` publishes. Theirs
  carries evidence *kinds*, adoption claims, retained-byte manifests for the host
  project's dependencies, and a claim-level outcome table with denominators. Ours
  covers one corpus and one question, and the comparison is recorded against us in
  `docs/COMPETITIVE-STATE.md`.
- It cannot prove a run happened. Only the runner can attest to that, and they do
  it in `exposure.declared_by` and in the issue form. What a bundle makes
  impossible is *changing its mind later* about the bytes, the controls, or what
  was already known.
- It is not a certification, and a passing bundle does not raise any count on its
  own. A row in `docs/RUNS.md` still requires an independent runner and a receipt
  that passes `tools/check_outward_receipt.py`.
