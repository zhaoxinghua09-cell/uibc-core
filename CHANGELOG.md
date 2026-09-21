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

## [Unreleased]

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
