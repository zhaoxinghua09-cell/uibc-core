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
