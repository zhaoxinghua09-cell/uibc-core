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

### The comparison now re-checks itself (2026-11-18)

- **`tools/check_competitors.py`** re-fetches what a stranger can fetch (PyPI
  JSON, GitHub repo record) for both projects, diffs it against
  `docs/COMPETITORS.json`, and exits non-zero when the world has moved. An
  endpoint that fails to answer is recorded as unmeasured, not estimated.
- **`docs/COMPETITORS.svg`**, built by `tools/build_competitors_svg.py` from the
  recorded baseline, so the picture cannot go stale on its own. Four of its six
  rows point their way; the two that point ours are the two a test count cannot
  buy.
- **`tests/test_competitors.py`** holds the offline half: the baseline is
  complete, and the picture states the same numbers. The network half is
  deliberately not in CI - a flaky gate teaches people to ignore gates.

### A depth ceiling, and a measured peer (2026-11-18)

- **Nesting ceiling, both implementations.** 4000 levels of `[` used to end in a
  stack exhaustion reported as S0 - "the verifier broke", a statement about us
  and not about the input. `MAX_NESTING = 512`, counted outside string literals,
  refuses it as S11. Taken from `agent-action-capsule`, which refuses at 128 with
  a message naming the limit.
- **A manifest that parses as an array** used to reach `.get()` on the Python
  side and raise `AttributeError`, again landing on S0. S1 now reports it.
- **Both sides stop when the bytes never became JSON**: invalid UTF-8, a repeated
  member name, a document past the ceiling, unparseable bytes. Nothing downstream
  is claimed about bytes nobody read.
- **`docs/COMPETITORS.md`** measures `agent-action-capsule` 0.17.0 and this
  project on the same day, with the command for each number, and states plainly
  where this project is behind (specification standing, release cadence, surface
  area, test count) as well as ahead (a second implementation, gated in CI).

### Hostile input: ten cases, ten verdicts, no crashes (2026-11-18)

- **`tools/redteam_robustness.py`** builds ten packages that are not packages:
  not JSON, an array where an object belongs, duplicate member names, a bare
  `NaN`, 4000 levels of nesting, invalid UTF-8, a path that climbs out of the
  package, a symlink to the host, an empty directory, an 8 MB manifest. All
  ten are answered by both implementations and refused by both.
- **A real hole, closed:** Python's `json` module accepts `NaN` by default.
  A manifest carrying `"remark":NaN` used to parse, pass every element check,
  and come out **INCONCLUSIVE** - an honest-looking answer about bytes that
  are not JSON. S11 now refuses it, on both sides: Python via
  `parse_constant`, JavaScript via `JSON.parse` inside S11.
- **S11 moved first in the JavaScript verifier, with an early return.** Bytes
  that are not JSON cannot be judged by any later check; falling through
  reported S0 ("the verifier broke") and hid the check that had the answer.
- `docs/ROBUSTNESS.md` records the table and explains why the two verdict lists
  differ on early failures without being inconsistent.

### The two implementations now agree on every package (2026-11-18)

- **S3 in JavaScript**, both families of rules: the L1-L7 state machine and the
  L8-L12 semantic layer. Coverage 18 of 19; the only check absent is S0, which
  exists only when the verifier itself throws.
- **`agree_with_python: 36 of 36`.** The cross-implementation check no longer
  asks only "does it name an expected check" - the same set of failing checks
  now comes out on every package. It was five apart.
- **A hole found in the Python verifier by the JavaScript one.**
  `manifest.evidence_count` was never compared with the number of index entries,
  so a package declaring two entries and shipping one passed. Fixed.
- **One root cause scored twice.** The JavaScript verifier derived the evidence
  root from hashes S4 had just shown to be wrong, reporting S5 as a second
  failure. S5 is now INCONCLUSIVE when S4 fails, matching Python: it is the
  same finding, not a second one.
- A test that had been naming a case directory that no longer exists
  (`09-edit-the-evidence-root`; the case is `10-...`) was corrected - it had
  been passing against a stale unpacked fixture rather than the shipped suite.

### The second implementation verifies a stranger's timestamp (2026-11-18)

- **S16 in JavaScript, with no dependency and no shared code.** `tools/verify-js/rfc3161.mjs`
  reads an RFC 3161 token with a minimal DER reader built from `node:crypto` alone, checks
  the CMS signature over `signedAttrs` (encoded as `SET OF`, not `SEQUENCE` — the tag that
  catches naive implementations), locates the ESS `signingCertificate` certHash by walking
  the subtree, and proves the signing certificate was issued by a supplied CA and was valid
  at its stamping time. A real Free TSA token for the head in `tests/fixtures/anchor/`
  verifies: `stamped 20261117081135Z, TSA O=Free TSA`.
- **This is the one witness the project cannot mint.** Every other check is witnessed by
  parties we choose: our tree, our head, our pin. A token is dated by somebody else's key,
  and now two implementations built from the spec — with no shared code — reach the same
  verdict on it, in both the accept and the refuse direction.
- **Red team, seven of seven:** the token as received is accepted; a flipped signature bit,
  a wrong anchored digest, a CA that did not issue it, no CA at all, one mutated digit inside
  a signed attribute, and a truncated token are each refused with a distinct reason.
- **S9 in JavaScript.** `--expect-head <head>` supplies the observation made outside the
  package and compares it with the checkpoint state. The pin is never read from the package;
  without it S9 does not appear, because an unchecked rollback must not look like a pass.
- `node tools/verify-js/rfc3161.mjs <token.tsr> <digest-hex> <ca.pem>` is a standalone entry
  point: anyone with Node can reproduce the token verdict without installing anything.
- **Coverage: seventeen of nineteen checks** in the second implementation; `--strict` and
  lenient modes now agree with the Python verifier's defaults.

### Added

- **CI now fails when the second implementation drifts.** `tools/assert_second_impl.py`
  asserts that every package the suite accepts is accepted, every package it
  refuses fails for a reason one of its expected checks names, and no package
  expects a check the JavaScript side does not carry. Verified by breaking it
  on purpose: with S15 forced to pass it names the four anchor packages and
  exits 1; with S15 removed from the covered set it does the same. The new
  `second-implementation` job runs it on every push and pull request. Set
  equality is not required, because the two implementations legitimately
  differ on five packages and forcing equality would make one of them lie.
- **The gate was tested against itself, in the pipeline.** Pull request #134
  removed `S15` from `COVERED` while four packages still expected it: the
  `second-implementation` job failed, `mergeable_state` stayed `blocked` for
  thirty consecutive samples, and the pull request was closed unmerged. The
  required checks on `main` are now `test (3.13)` and `second-implementation`,
  with `strict` and `enforce_admins` on. Recorded in `docs/NEGATIVE-CONTROL.md`.

### Added

- **The JavaScript verifier covers ten of nineteen checks, up from eight.**
  S14 strict base64: pad bits set, missing padding and stray characters all
  decode permissively, so two decoders can disagree about what was signed.
  Only fields the package itself marks as base64 are examined, so a schema
  that does not use base64 cannot be false-flagged. S10 the closure
  declaration: six components must be present and shaped like digests --
  declaration only, because whether those digests match what actually ran is
  not decidable from a package.
- Both checks are silent on a package that declares neither, exactly as the
  Python verifier is: the correct package's report still shows eight checks,
  not ten.

### Measured

- Python: `strict 36/36   refused 30/36`
- JavaScript: `strict 36/36   refused 30/36`
- Identical FAIL set to Python: 31 of 36; named an expected check: 30 (+6 positives)
- Out of scope: 0 packages -- the JavaScript verifier now agrees on all 36

### Added (S17, S18)

- **The second implementation now agrees with the first on all 36 packages.**
  S17 recomputes `previousReceiptHash` over the JCS of the predecessor's signed
  envelope and insists the first receipt of a chain carries 64 zeros. S18
  resolves every `policy_digest` to the artefact shipped next to it, and rejects
  one a receipt declares that resolves nowhere. A tree answers "was this byte
  changed"; only the linear link answers "is this record the successor of that
  record".
- Fifteen of nineteen checks now have two independent implementations. The
  four without one are S0 and S3 (not modelled as separate checks on this side),
  and S9/S16, which need an observation or a key this checker does not hold.
- Measured honestly: the FAIL *sets* still differ on 5 of 30 vectors -- the
  JavaScript side reports a superset (an edited byte also moves the root,
  S4 and S5). Same verdict, finer diagnosis. `named an expected check` is 30
  of 30.

### Added (S15)

- **The JavaScript verifier resolves anchors.** Four vectors, one code path:
  a corrupt inclusion proof, a leaf hash that is not a digest, 30 February,
  and a root this package cannot recompute. The lesson from the Python side
  carries over: the claimed leaf must be the leaf that actually sits at that
  index, or the proof is being checked against a subject the set does not
  contain at that position. Resolving against our own root proves the anchor
  was built from this package; it does not prove a third party saw it, and an
  anchor naming an external log stays unresolved rather than counted.
- Thirteen of nineteen checks now have two independent implementations. The
  four packages still out of scope are S9 (out-of-band pin) and S16/S17/S18.

### Added (S8)

- **The JavaScript verifier recomputes the package checkpoint.** One value
  committing to the whole state: lifecycle head, evidence root, index metadata
  digest, evidence count. A lifecycle-only head was not enough -- adding
  evidence changes the root but leaves the log untouched, so two different
  states shared one head. Truncation, rollback and post-seal replacement inside
  one package are what this detects. A whole-store rollback still needs an
  observation made elsewhere, which is S9 and stays out of scope.
- Both S8 vectors now fail on S8: a rewritten index with content untouched
  (also S7), and a truncated lifecycle log. Packages without a checkpoint_head
  are not examined, exactly as the Python verifier behaves. Twelve of nineteen.

### Added (S13)

- **The JavaScript verifier recomputes Merkle inclusion proofs (RFC 6962).**
  Leaf = SHA-256(0x00 || data), node = SHA-256(0x01 || l || r), an unbalanced
  tail is promoted rather than duplicated -- duplicating it would let two
  different trees share a root. It checks the declared algorithm, the declared
  size against the leaves it computed, the root, each proof's index against the
  order it recomputed, hex shape, and the path itself. All four S13 vectors
  (replaced root, inflated size, corrupted proof, swapped index) now fail on
  S13 rather than on something incidental. A package with no tree is still not
  penalised: eleven of nineteen covered.

---

## [0.4.1] - 2026-11-18 (the second implementation grows)

### Added

- **The second implementation verifies Ed25519 seals, not just structure.**
  `tools/verify-js/verify.mjs` now checks S6 for asymmetric seals: it re-derives
  the canonical payload (identity + manifest, plus lifecycle when the seal says
  so), builds an Ed25519 public key from the one recorded in the package, and
  verifies the signature with Node's own crypto. Coverage goes from seven checks
  to eight of nineteen. An HMAC seal is reported as INCONCLUSIVE, because it
  cannot be checked without the owner's key -- the verifier says so rather than
  guessing.
- **The suite now contains an asymmetric seal.** Two cases: "a package sealed with
  Ed25519" (must be accepted) and "flip one bit in an Ed25519 signature" (must
  fail S6). Until now every case carried an HMAC seal, so the property the
  project keeps claiming -- *a stranger verifies provenance with no secret* --
  had no vector. The seed is fixed, so the case is reproducible byte for byte.

### Measured

- Python: `strict 36/36   refused 30/36`
- JavaScript: `strict 19/36   refused 30/36`
- Identical FAIL set to Python: 13 of 36; named an expected check: 13 (+6 positives)
- `tests/test_conformance.py` no longer hard-codes "5 positives": the counts are
  read from the manifest, so the next case does not break the tests that guard
  the suite.

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

### Added

- **An independent JavaScript verifier** (`tools/verify-js/verify.mjs`): Node standard library only, no import of `uibc-core`, no npm package. It decides seven of the nineteen checks -- S1, S2, S4, S5, S7 (shape *and* the metadata digest), S11, S12 -- and refuses to pretend about the rest, so it never returns PASS. Measured against the same 34 packages: `strict 16/34 refused 29/34`, with an **identical FAIL set to Python on 10 packages** and the same expected check named on 11. Two implementations built from the spec, sharing no code, agreeing on what is broken and why.
- **`tools/cross_impl_check.py`** prints that comparison case by case, so the boundary is a number rather than a claim.
- **Two defects found by the exercise itself.** (a) The "one more declared evidence file" conformance package wrote its declaration under `files` instead of `entries`, so the file was undeclared while the name claimed otherwise; the case now grows the package through the shipped CLI. (b) The JS metadata-digest comparison caught an exception on an absent member and let a tampered note pass -- an `undefined` that Python writes as `null`. Both were caught only because a second implementation ran the same corpus.
- `tests/test_verify_js.py` (4 tests, skipped when Node is absent): a sound package must be INCONCLUSIVE, a flipped byte must fail S4, an edited root must fail S5, and every extra finding must come from a check the implementation claims to run.

### Added

- **The docs/ pages that describe the present now have to stay true.** `tools/check_doc_facts.py` scanned six top-level files; `docs/CONFORMANCE.md` said 305 tests, `docs/COMPOSITION-VERIFIER.md` said 180, `docs/ECOSYSTEM-MAP.md` and `docs/INTEROP-MATRIX.md` said 0.3.0 with 305 tests, all of them about the current project and all of them wrong. A page joins the check by saying so on its first lines, `<!-- facts: current -->`; the five present-tense pages that do are now scanned along with the six. Pages recording a past run (`REVIEW-LOG.md`, `RUN-RECORD-second-machine-20261118.md`) carry no marker and are left alone, because rewriting a run record's numbers would falsify history rather than correct it.
- **One checker bug fixed on the way.** `"15 red-team cases"` was matched by the `cases` rule against the *conformance package* count, so a correct sentence looked stale. Red-team cases now have their own key, and the generic `cases` rule is gone rather than guessed at.
- `tests/test_doc_facts.py` gained two assertions: a marked page that carries a wrong number must be caught, and an unmarked one must not be scanned.

### Added

- **Five positive vectors in the conformance suite**, so it measures correctness instead of pessimism. Twenty-nine packages had to be refused and nothing had to be accepted, which meant a verifier that refused everything scored 29/29 -- full marks for being useless. Now **29 refused + 5 accepted**: the shipped package untouched, the tree-and-chain / extended-evidence / checkpoint shapes appended correctly, and one case where an extra evidence file is added *and declared in the index* so S1 must not fail. Expected verdicts come from this repo's measured run.
- **The positive cases found a real gap at once.** Archived v0.2.1 refuses all 34, the five correct ones included: it cannot read the newer shapes, so its blanket refusal was hiding a forward-compatibility hole. A property of that older release, made visible by the suite.
- `tests/test_conformance.py` asserts that a verifier refusing everything fails every positive case. Measured: always-PASS 5/34, always-FAIL naming S1 1/34, current 34/34 (refused 29/34). Test count 513 -> 514; `docs/REPRODUCE.md` regenerated so its conformance row reads `strict 34/34 refused 29/34`.

### Added

- **`docs/REPRODUCE.md` and `tools/build_reproduce.py`** -- ten rows: the figure in the paper, the command a reader types, and the output recorded when the generator ran it. Every row has its own reader (JSON field, tail line, or regex) because six of the tools print progress before their figure, and taking the first line reported `{` for three of them. Latency here reads 1.367 ms against the paper's 1.225 ms, and the sheet says so rather than smoothing it: a figure from another host is another measurement.
- **`tests/test_reproduce.py`** -- 5 tests, including one that runs a real claim end to end and one that refuses placeholder output anywhere in the sheet.
- The published test count moved 508 -> 513 across README, README.en, AGENTS and the paper, as `check_doc_facts` requires.

### Fixed

- **The paper's own numbers were wrong in three places.** `paper/paper.md` claimed 122 tests (507 run), "three modules" within 24 files (25), and "zero-dependency (stdlib only)" when `[verify]` pulls in `cryptography` and `asn1crypto`. Rewritten to state the stdlib-only core, the optional extra, the INCONCLUSIVE-on-absence behaviour, 507 tests, and 25 modules. The skipped count is described rather than pinned, because it moves between 16 and 17.
- **`tools/check_doc_facts.py` now covers the paper and module counts.** `paper/paper.md` is a target, and `modules` is a measured fact, so a stale count there fails CI too.

### Fixed

- **The README's test count was 328; the suite runs 507.** Corrected in `README.md`, `README.en.md`, `AGENTS.md`, together with the skipped count (6 -> 16) and the recorded runtime.

### Added

- **`tools/check_doc_facts.py`** -- measures tests, checks, audit attacks, red-team cases and conformance vectors, then reads the documents a reader treats as current and reports every number that disagrees. Dated records under `docs/` are excluded on purpose: they are findings from a moment, and rewriting them would falsify a record rather than correct a claim. `--json` and `--files` supported.
- **`tests/test_doc_facts.py`** -- 4 tests: every fact is measurable, no published number is stale, a planted wrong number must be caught, and the two attack counts (36 audit / 15 red-team) must stay distinguishable. Adding a test without updating the README now turns CI red.

### Added

- **Rate limiting on the verify endpoint.** A token bucket per caller, `--rate`/`--burst`, `429` with `Retry-After`, and the limit advertised on `/health`. `X-Forwarded-For` is ignored unless `--trust-forwarded` is passed, because a bucket keyed on a caller-controlled header is not a bucket. Measured at burst 10: 11 of 320 calls under 16 concurrent clients succeeded, 309 refused.
- **`tools/stress_verify.py`** -- concurrency measurement, unlimited and limited in one run.
- **`deploy/`** -- a Dockerfile and instructions so a stranger can run their own endpoint; the image is untested here (no Docker on this machine) and the README says so.
- **`tests/test_rate_limit.py`** -- 8 tests, including the spoofed-header test.

### Added

- **Conformance suite.** 29 packages, each correct and then broken in exactly one way, with the checks a verifier must report. `tools/run_conformance.py --verify "<cmd>"` runs them against any implementation. Expectations come from the audit's measured run, so the suite cannot drift from the report. Measured: current implementation 29/29; archived v0.2.1 (6 checks) 0/29 while still refusing all 29; a verifier that refuses nothing scores 0. See `conformance/README.md`.
- **`tests/test_conformance.py`** -- 6 tests, including the archive-vs-manifest digest check and the rubber-stamp check.

### Added

- **`--strict` mode for S1.** `verify(pkg, strict=True)` and `uibc verify <pkg> --strict` fail any file under `evidence/` that the index never declared, while exempting the five structural members the format places there (`merkle.json`, `chain.json`, `anchors.json`, `policies.json`, `policies/*`). The default stays lenient, because a tightening that invalidates every existing package is a version change, not a fix. See `docs/STRICT-MODE.md`.
- **`tests/test_strict_mode.py`** -- 5 tests covering lenient, strict, exempt, clean, and the real CLI exit code.

- **`tools/build_thesis_tables.py` -> `docs/THESIS-CH5-TABLES.md`.** The six tables a chapter-5 could cite (checks and their basis, basis distribution, attack incidence summary, the two-implementation comparison, the three-channel coverage, the hot-path latency), each generated from the tools' JSON with a "how to regenerate" line beneath it, and an explicit section listing what the chapter must not claim.
- **`tests/test_thesis_tables.py`** -- 6 tests tying each table to the tool it reads.
### Added

- **`tools/check_matrix.py` -> `docs/CHECK-MATRIX.md` and `docs/CHECK-MATRIX.svg`.** Reads the audit's own JSON and prints which attacks move which checks. Two numbers fall out: 32 of 36 attacks isolate exactly one check, and no check is unreachable. The two attacks that move two checks (an impossible date also trips the lifecycle state machine; rewritten index metadata also moves the checkpoint head) are recorded rather than smoothed over.
- **`tests/test_check_matrix.py`** -- 6 tests holding those two claims.

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
- **`uibc explain <pkg>`** -- the same verifier, printed for a person: one line
  per check, then its class and citation, then the failure text. `verify` keeps
  emitting JSON unchanged, because scripts parse that and a citation four
  levels down in a JSON blob is not readable.
- **`tests/test_basis.py`** -- 8 tests: only documented classes carry a
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
