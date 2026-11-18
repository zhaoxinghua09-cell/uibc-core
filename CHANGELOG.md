# Changelog

All notable changes to `uibc-core` are recorded here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html),
with one project-specific rule: **any change to what produces which verifier
verdict (PASS / FAIL / INCONCLUSIVE) is a breaking change**, regardless of how
small the code diff is.

Status reminder: everything up to and including `0.2.1` is a **PROPOSAL**.
Nothing here is a ratified standard.

---

## [0.4.0] - 2026-11-18

This is the release that makes the eighteen checks reachable. Everything below
that concerns S7-S18 exists in the tree and in no earlier artifact: the
published `0.3.3` verifier reports six checks on the same package that the tree
reports seventeen on (docs/RELEASE-PARITY.md records the measurement).

### Added

- **Twelve checks beyond `0.3.3`:** S7 index metadata, S8 whole-state
  checkpoint, S9 out-of-band pin, S10 attestation closure, S13 merkle proofs,
  S14 strict base64, S15 anchor resolution, S16 RFC 3161, S17 receipt chain,
  S18 policy artefacts, plus the S0 crash fallback and the S11/S12 strictness
  checks in their current form. `python3 tools/check_release_parity.py` prints
  the three-channel comparison.
- **`tools/outsider_audit.py`** -- five red-team stages over one command, with an
  auditor self-test (path gate + behaviour gate) and `--json` output.
- **`tools/build_evidence_index.py`** -- every check mapped to its tests, its
  red-team cover and its docs, measured by running the audit rather than grepping
  the source (`docs/EVIDENCE-INDEX.md`).
- **`tools/build_checks_reference.py`** -- the eighteen checks with the question
  each answers and an explicit three-way classification of their external basis
  (`docs/CHECKS-REFERENCE.md`).
- **`tools/build_outside_kit.py`** -- a whitelisted 43-file audit kit, runnable
  by someone who will not clone the repository.
- **`tools/serve_verify.py`** -- a verify endpoint that accepts bytes and
  refuses hostile archives.
- **`tools/emit_aac_capsule.py`** -- export to the Agent Action Capsule format,
  recomputing the capsule id under JCS and asking their verifier.
- **`tools/check_citation_scope.py`, `tools/preflight_release.py`** -- the two
  gates that stop a claim from outrunning the artifact.

### Changed

- **`pyproject.toml`:** version 0.4.0; the description no longer carries a
  version number, which had drifted from the field beside it.

### Notes on compatibility

Per this project's own rule, any change to what produces which verdict is a
breaking change. Twelve new checks necessarily change verdicts for packages
carrying the fields they inspect, so 0.4.0 is a major-looking bump under a
0.3.x series rather than a patch.

## [Unreleased]

### Fixed

- **The package reported its own version as 0.3.3 while shipping as 0.4.0.**
  `uibc_core/__init__.py` held a literal that had not moved with
  `pyproject.toml`, so every verification report stamped the wrong version. `tools/version_gate.py` now also reads that literal, making it a fourth
  place the gate compares rather than a fourth place to drift.
- **S15 lost its import during this work** and raised
  `NameError: _mk2 is not defined` on any package carrying an anchor; caught by
  the audit builder's own "a correct package must pass" assertion before it
  reached a commit.
- **S13 raised `IndexError` when an evidence file was deleted.** The declared
  order still listed the missing evidence, so `leaves[i]` ran past the end of
  the list the filesystem actually produced, and the exception was caught by
  the S0 fallback. The verdict was right (FAIL) but the reason was
  `IndexError: list index out of range`, which names neither the check nor the
  file. S13 now reports `proof names evidence 'files/action-log.txt' whose file
  is absent`.

### Added

- **Every check now carries its basis.** `uibc_core/basis.py` holds, for each
  check, whether a draft or RFC states the requirement (`direct`), the
  mechanism is borrowed from one (`related`), or this project defines it with
  nothing to point at (`none`) - and a citation for the first two, an empty
  string for the third. Rendered into every report as
  `checks[].basis = {class, citation, note}`.
- **`tests/test_basis.py`** -- 6 tests: only documented classes carry a
  citation, `none` never does, an unknown id borrows nothing, and the shipped
  report matches the module.

- **`tools/compare_diagnostics.py` → `docs/DIAGNOSTICS.md`.** The same six
  kinds of damage applied to our package and to `agent-action-capsule` 0.17.0,
  printing what each verifier says *after* it says FAIL. On the four attacks
  both formats can express, we reported 13 specific reasons against their 5;
  the other two have no counterpart in their format, and are marked n/a rather
  than scored.
- **`tests/test_diagnostics_compare.py`** -- 5 tests, including one that fails
  on purpose if the documented gap (an uncommitted file under `evidence/` is
  only a note, never a failure) ever changes, so the doc cannot drift from
  reality.

### Not changed, on purpose

An attempt to make S1 fail on any uncommitted file under `evidence/` was
reverted: this format itself keeps the anchor event, the policy artefacts and
the receipt chain there, and the tightening failed a dozen existing packages.
That is a format-version change, not a patch.


### Added

- **Handover worked example (`examples/link3-handover-evidence/`):**
  the Link-3 handbook pack — the receiving-side check of a fictional
  device evidence set, in five runs (approved open PASS / approved
  pinned PASS / report swapped after sealing FAIL / rebuilt and
  re-sealed under a substitute key PASS unpinned / same pack FAIL
  pinned). Rebuilt with the released 0.3.3 so the `pip install`
  path reproduces every verdict; the folder README states the
  coverage=legacy scope of these seals in the verifier's own terms.
  Includes the plain-language verify guide (EN + Chinese) and the
  recorded run transcript.

- **Change-evidence worked example (`examples/link1-change-evidence/`):**
  the Link-1 handbook pack — a fictional device AI model update
  (v1.1 -> v1.2) handed downstream as a sealed four-file evidence set,
  in three states (sealed / evaluation report swapped after sealing /
  submitted unsealed) with verdicts PASS / FAIL (S4 names the swapped
  file) / INCONCLUSIVE and gate decisions ALLOW / DENY / HOLD. Built
  with the released 0.3.3 so the `pip install uibc-core` path
  reproduces every verdict; includes a plain-language verify guide
  (EN + Chinese) and the recorded run transcript.

- **AEE rail (`uibc_core/aee.py`): an external verifier for the
  Adversarial Execution Evidence in-toto predicate v0.7**, so the
  `agent-evidence-vectors` conformance corpus (288 vectors) can run
  against uibc-core: `python3 -m uibc_core.aee <statement.json>` under
  the corpus contract (exit 0 = valid; last stdout line one JSON report
  with verdict / codes / result / tiers; consumer key policy via
  `AEE_SUBSTRATE_KEYS`). GATE 0 well-formedness (strict I-JSON,
  vocabulary and corpus digests, coverage partition), GATE 1
  byte-checkable coverage validity (run-binding derivation v2, kind
  constraints, method cap), the 0.7 statement-level commitments, the
  total result recompute, and GATE 2 evidence tiers against pinned
  substrate keys (strict Ed25519). Stdlib only; the RFC 6962 batch root
  reuses `uibc_core.merkle`. Corpus result at build time: 288/288
  (63 accept / 223 reject / 2 indeterminate), reason parity on all
  rejects. Spot-checks live in `tests/test_aee_rail.py` (skipped when
  the corpus package is not installed).

### Fixed

- **Browser verifier (`verify.html`) brought back to parity with the CLI.**
  The page still implemented the v0.3.0 semantics: its seal payload covered
  identity+manifest only, so every package sealed since v1.1 (seal payload
  identity+manifest+lifecycle) failed S6 in the browser while passing
  `uibc verify`. The page now ports the 0.3.3 verifier check-for-check
  (S1–S18 in the reference report order, including S11 strict serialization,
  S12 semantic strictness, and the conditional S7/S10/S13–S18 surfaces),
  canonicalizes with RFC 8785 JCS like the CLI, accepts the legacy payload
  as `coverage=legacy`, supports a pinned checkpoint head (S9), and embeds
  a sample package built with the current release. A 27-run parity corpus
  ships in `tests/verify_html_parity/`; the page and the CLI agree on every
  check. Declared limit: S16 (RFC 3161 tokens) is INCONCLUSIVE on the page
  by design — the port does not parse DER tokens.

v0.3.0 below is the release cut on 2026-11-12: tag `v0.3.0`, GitHub Release published,
and `uibc-core 0.3.0` uploaded to PyPI on 2026-11-12 (sdist + wheel, same bytes as the CI build —
sha256 listed in `docs/pypi-0.3.0-release.md`). The release-triggered `publish-pypi.yml` run
`43150166821` still fails at the upload step because the trusted-publisher registration is not in
place; that workflow is a convenience path, not the only one.


## [0.3.0] — 2026-11-12


### ⚠️ VERDICT-AFFECTING (breaking in effect)

Per this project's own rule above, this release changes what produces
which verdict, in two connected moves. The full semantics are specified
in `docs/verdict-and-seal-semantics.md`.

**1. Three-valued verdicts.** Through 0.2.x the top-level result was
PASS unless a check FAILed, so an INCONCLUSIVE S6 (seal present but not
checkable in open mode) rode under a PASS. An external review (2026-11)
demonstrated the consequence: a fully self-consistent forgery verified
PASS in open mode. From 0.3.0: any FAIL → FAIL; else any INCONCLUSIVE →
INCONCLUSIVE; else PASS. Exactly three fixture cells changed — clean /
malicious / malicious-keyswap in open mode, PASS → INCONCLUSIVE. No
individual check outcome moved; the forgery is still not *detected*
without a key, it is simply no longer *passed*.

**2. Ed25519 public seals.** The v0.2 notes promised an asymmetric seal
for v0.3, pending a `cryptography` dependency decision. The decision
landed differently: Ed25519 (RFC 8032) is implemented in pure Python on
the standard library, and the project stays zero-dependency. An
Ed25519 seal records its public key in the package, so anyone can
verify provenance without the owner's secret (`uibc keygen --ed25519`,
`uibc submit --key`, `uibc verify --pubkey <pin>`). Reports gain an
`assurance` field: `public-key` / `owner-key` / `unattested`.

Also in this release: an unsigned package in open mode is INCONCLUSIVE
at S6 (was SKIP under PASS); `uibc demo` now runs the v0.3 arc
(stranger-verifies → tamper → forge-and-reseal → pinning catch);
`examples/` ships a committed sample package verifiable by any
stranger; the independent verifier mirrors the new semantics so the
two implementations still cross-check; gate HOLD now also results
from an unattested (unsigned) package in open mode.

Note: `CITATION.cff` / `codemeta.json` still pin the archived 0.2.1
artifact and its version DOI; they will be updated when the 0.3.0
archive is deposited.


### ⚠️ VERDICT-AFFECTING (breaking in effect) — released as 0.2.2

Per this project's own rule above, *a change to what produces which verifier
verdict is a breaking change*. This release contains one, in the **memory
migration verifier**:

| Input | Before | After |
|---|---|---|
| migration `target` contains a duplicate `memory_id` | `PASS` when the real entry happened to be kept by dict collapse — reported as "no injections" | `FAIL` / `MALFORMED_INPUT`; duplicate ids rejected on **both** sides |
| `source` and `target` both empty | `PASS` on all four Preservations | `INCONCLUSIVE` / `VACUOUS_INPUT` |

The patch number is used deliberately. `0.3.0` is already committed in the
public narrative to Ed25519 + a public key registry (the standing answer to the
`malicious-keyswap` boundary), and silently renumbering that promise would be a
more confusing change than an honest patch with this notice. **The substance is
breaking; this notice exists so nobody discovers it from a failing suite.**

> **Release status — which version number lives where.**
> `0.2.1` is **already published** (Zenodo DOI `10.5281/zenodo.22821835`; see
> `dist/`) and therefore must never be redefined. So this fix ships as `0.2.2`,
> and the files that describe the *published artifact* — `CITATION.cff`,
> `.zenodo.json`, `codemeta.json`, `dist/` — deliberately still read `0.2.1`.
> `__init__.py` and `pyproject.toml` carry the *working-tree* version.
>
> Consequence worth stating plainly: **the published `0.2.1` contains the two
> memory-migration gaps fixed here.** A `0.2.2` release should be published
> (the existing concept DOI supports "new version"), so that the version a
> researcher cites is not the one with a silent injection path. Publishing is
> an outbound, irreversible action and is left to the maintainer.

### Added
- `fixtures/generate_memory_fixtures.py` — a 22-case memory-migration mutation
  corpus (M0-M5), with the same hand-derived expectation matrix and non-zero
  exit gate as the package fixtures. It is what found the two defects above.
- `fixtures/_matrix_gate.py` — the comparison/rendering/gate logic shared by
  both fixture generators, so the two cannot drift apart.
- `tests/test_fixture_expectations.py` (16 tests) and
  `tests/test_memory_fixtures.py` (19 tests) — gate tests in both directions
  (green when the prior holds, red when it breaks) plus regression locks.
- `MEM_VERIFIER_VERSION` in `uibc_core/memory.py`, carried in every migration
  report so a rubric score can cite which verify produced it (SS31 field).

### Changed
- `fixtures/EXPECTED.md` and `README.md` no longer claim "S4 + S6 signature
  invalid" for the evidence-content mutations. A seal over
  `identity+manifest` cannot be invalidated by rewriting an evidence file, so
  S6 stays `PASS` in those cases and the detection comes from S4/S5/S3. The old
  wording described a defence that never fired.
- Memory migration reports now always carry a `result_code`
  (`OK` / `MALFORMED_INPUT` / `VACUOUS_INPUT`).

### Fixed
- Memory injection was possible through a duplicate `memory_id` in the target:
  the entry was collapsed away before comparison and the report still said
  "no injections" — a silent pass through M2 Fact Preservation (rubric weight
  0.30, the heaviest dimension).
- A migration of nothing scored `PASS` on all four Preservations.
- An empty field value (`{"content": ""}`) was reported as a *missing* field.

### Added
- `LICENSE` (Apache-2.0). Previously `pyproject.toml` declared Apache-2.0 but no
  licence file existed, and `CITATION.cff` warned against redistribution. This
  was a blocking gap for any standards or academic use; it is now closed.
- `codemeta.json` (CodeMeta 2.0) — required for indexing in the Software
  Heritage archive and for cross-repository software metadata exchange.
- `.zenodo.json` — per-deposit metadata so future Zenodo releases inherit the
  correct title, creators, ORCID, licence and keywords.
- `SECURITY.md` — scope, out-of-scope, supported versions, private reporting
  channel, and an explicit statement of the adversarial-testing posture.
- `CONTRIBUTING.md` — ground rules, the full local gate, what we want and what
  we decline.
- `CODE_OF_CONDUCT.md`.
- `CHANGELOG.md` (this file).
- `NOTICE` — third-party attribution.

### Changed
- `CITATION.cff` licence field now points at the real `LICENSE` file.

### Fixed
- `CITATION.cff`: replaced an unverified Software Heritage identifier with the
  values confirmed against the archive API (origin SWHID + snapshot SWHID), and
  corrected the neighbour-benchmark reference — the previous entry paraphrased
  the arXiv title instead of quoting it.
- `sbom.spdx.json` / `tools/gen-sbom.py`: SPDX 2.3 conformance. Element
  identifiers no longer contain underscores, the invalid
  `hasExtractedLicensingInfos` block was dropped (Apache-2.0 is on the SPDX
  licence list, so extracting it as a `licenseId` was wrong), and
  `licenseListVersion` now tracks the current list (3.29.0).
- `NOTICE`: removed a third-party company name from the redistribution note.
- `adapters/tencentdb-agent-memory/SPEC.md`: neutral wording for the runtime
  environment.
- Zenodo record `10.5281/zenodo.22821835`: metadata corrected from MIT to
  Apache-2.0 so the DOI-fixed artifact matches this repository, and the
  description now carries the canonical UIBC expansion and abstract. The
  deposited file bytes are unchanged; only metadata was corrected.
- All of the above came out of an independent three-way expert review
  (standards/compliance, endorsement channels, privacy and credential red
  lines). The review record is `docs/expert-review-2026-09-18.md`.

### Packaging / distribution (no verdict change)

- The MCP server now ships inside the package as `uibc_core.mcp_server`
  with a `uibc-mcp` console script, so `pip install uibc-core` is enough
  to run it; `mcp_server/server.py` remains as a compatibility shim.
- `verify_package` and `gate_check` MCP tools accept `pubkey_hex` to pin
  the expected Ed25519 signer (a substituted key FAILS S6), matching the
  CLI `--pubkey` behaviour.
- README (中文 / English) updated from v0.2.1 to v0.3.0; PyPI metadata
  description and development-status classifier updated to match.

---

## [0.2.1] — 2026-09-17

First publicly archived release. Triple-anchored: GitHub tag + OpenTimestamps
proof + Zenodo DOI.

- **Zenodo DOI:** version `10.5281/zenodo.22821835`, concept
  `10.5281/zenodo.22821834` (resolves to latest version).
- **OpenTimestamps:** `timestamps/uibc-core-0.2.1.zip.ots`, submitted to two
  independent calendars; upgrades to a Bitcoin block attestation on its own
  schedule.
- **Release artifact:** `dist/uibc-core-0.2.1.zip`,
  SHA-256 `59cc1c917ff766af8f6528ceadfea522b8627a2c591e57334aa4afd2a07959f4`.

### Added
- Read-only HTTP registry server (POST refused with 405; corrupt JSONL surfaces
  honestly rather than being swallowed). 9 tests.
- Static registry query page (`registry/index.html`).
- A2A adapter HTTP server — JSON-RPC 2.0 `card` / `verify` / `gate` / `inspect`,
  path-traversal rejection. 15 tests.
- `examples/showcase.py` + `SHOWCASE.md` — a full-lifecycle recorded run.
- `uibc_core/runtime.py` — one-line integration hooks
  (`record_action` / `seal` / `event` / `snapshot`). 9 tests.
- `README.en.md` — full English documentation.
- Contest package: charter, seven curated problems (P-01…P-07) mapped to
  `uibc-core` capabilities with AIGC provenance labels, weighted rubric
  (M2–M5, evidence-required scoring), submission spec with a verify-first gate,
  and a pilot-run record that includes honest tool limitations.
- Resident-benchmark charter v0.2: three-stage evaluation (machine gate →
  hidden set → top-submission re-run), `experiments/` append-only archive,
  starter kits, and a 10-competitor landscape review.

### Changed
- Test counts re-synced across `README.md`, `/ai/faq`, `llms.txt` and the
  manifest (the earlier `71` figure had drifted; the suite is now **115** unit
  cases plus 7 stress scenarios).
- `__version__` and `SPEC_VERSION` aligned to `0.2.1` so that verifier output
  reports match the released package.
- `uibc demo` step 6 now tampers *actual evidence content* instead of appending
  new evidence — the previous version could pass for the wrong reason.
- FAQ clarified the difference between `S6 SKIP` and `S6 INCONCLUSIVE`.
- `llms.txt` no longer implies Merkle-tree construction; the evidence root is a
  canonical hash over the ordered evidence set.

### Fixed
- External-audit findings: FAQ quickstart rewritten and verified command-by-
  command against the CLI; `docs/benchmarks.md` expectations aligned to
  `EXPECTED.md`; README gains an explicit test section; `submit` now returns a
  readable error for an unregistered package instead of failing obscurely.

---

## [0.2.0] — 2026-09-17

The release that closed the v0.1 blind spot.

### Added
- **Seal signatures** (HMAC-SHA256, provisional; Ed25519 planned for v0.3) —
  `seal_sign` / `seal_verify`, CLI `keygen` / `submit --key` / `verify --key`.
- Verifier **S6** with two modes: `open` (unsigned tolerated, verdict stated)
  and `strict` (unsigned or wrongly-keyed ⇒ FAIL).
- `malicious-keyswap` fixture, documenting the out-of-band key-pinning boundary.

### Fixed
- **Full forgery is now detected.** In v0.1, a package whose evidence was
  entirely fabricated verified as clean. `failure_corpus/` keeps the original
  case public rather than quietly patching it away.

### Notes
- Stress scenario `g` added to cover the signing path: 10k `seal_sign` /
  `seal_verify` throughput, and strict `S6` verification on a 500-entry package.
  Re-run live after v0.2: 7/7 OK.

---

## [0.1.0] — 2026-09-17

Initial proposal.

### Added
- Canonical serialization (provisional).
- Lifecycle state machine L1–L7.
- Verifier with scoped report (S1–S5). PASS is explicitly defined as "no
  violation found within the observed evidence boundary" — not absolute trust.
- CLI: `init` / `register` / `event` / `evidence` / `submit` / `verify` /
  `inspect`.
- `uibc demo` — build → seal → verify PASS → tamper → FAIL.
- Golden fixtures across 7 categories (clean / tampered / deleted / duplicated /
  reordered / migrated / malicious), with `EXPECTED.md` recording
  expected-vs-observed. The malicious full-forgery case was **UNDETECTED**; this
  is the documented motivation for v0.2 signatures.
- Determinism check: 7 independent builds produced an identical evidence root.
- Test hardening: 31 unit cases (including a stale-seal S5 regression) and a
  pre-push gate that was itself deliberately violated to confirm it blocks.

### Known issues at this version
- No signatures ⇒ malicious forgery undetected.
- No certificate, gate-decision, memory-migration or registry layer.
