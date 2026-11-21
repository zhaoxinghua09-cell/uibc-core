# First-hand verification addendum — peers, scanners, standards (2026-11-21)

Purpose: close the "no dimension where we are silent" gap with a falsifiable record.
Every row carries a source, a date, and a credibility label. Where a first-hand
source could not be retrieved, the row says so and makes **no** claim. This file
supersedes the stale version strings in `ECOSYSTEM-MAP.md` (corrected in place the
same day).

Credibility labels: `official` (project/org/standards body source) · `author-self`
(project's own reported number, not independently replicated) · `third-index`
(package index, not publisher-confirmed) · `unverified` (no first-hand source).

## 1. Agent-skill scanners (newly verified — previously missing)

| Tool | Source | What it actually is | Version / date | Label |
|---|---|---|---|---|
| NVIDIA **SkillSpector** | github.com/NVIDIA/SkillSpector + docs.nvidia.com/skills/skillevaluator/tier1-validation | Security scanner for agent skills; 71 vulnerability patterns / 17 categories; part of NVIDIA Verified Skills pipeline; Apache-2.0 | v2.13.3 (NVIDIA docs + conda-forge, 2026-11) | `official` (repo + NVIDIA docs; version via official reference + index) |
| Cisco **Skill Scanner** | github.com/cisco-ai-defense/skill-scanner + cisco-ai-defense.github.io/docs | YAML+YARA-X patterns + AST/dataflow + optional LLM judge + bounded CEL layer. **Explicitly "best-effort", no findings ≠ safe.** Supports OpenAI Codex / Cursor Agent Skills formats | pip 2.2.2 install docs (2026) | `official`; recall numbers (7.7% HIGH rules-only, 66.7% MEDIUM+ with LLM judge) are `author-self` on held-out MaliciousSkillBench |
| Snyk **Agent Scan / Skill Inspector** | github.com/snyk/agent-scan + labs.snyk.io/resources/agent-scan-skill-inspector | Open-source CLI (`uvx`, no npm package) + free self-service web scanner. v0.6+ risk-based output, 14 risk classes for MCP + skills. **Evo skill support = "coming soon", not shipped.** Needs `SNYK_TOKEN`; scanning MCP config may execute commands/network | v0.6+ / 2026-07-10 API | `official` (Snyk GitHub org + labs); 3,984 skills / 76 malicious stats are `author-self` |
| **AgentNotary** | github.com/CharanBharathula/agentnotary | Personal open-source CLI (`seal`/`attack`/`compliance`/`drift`), framework-agnostic. **Not an institutional product.** Avoid confusion with unrelated `io.github.jdhart81/agent-notary` MCP server | no verifiable release | `author-self`; marketing figures ($47K, "202 tests", tool comparisons) **not cited** |

Impact on our positioning: the "skill scanning" lane is crowded by well-resourced
vendors. We do not compete there and should not imply we do. Our adjacent surface
is *evidence verification after a skill/agent has run*, not pre-publication scanning.

## 2. Peer corrections (change what the ecosystem map says)

| Peer | Old line | Corrected line (first-hand) | Label |
|---|---|---|---|
| Tracekit | "two verifiers" vs README "three" | arXiv v2 abstract: **two independent verifier implementations** (Python, TypeScript; browser page is the TS form). README mirror says 1.5.3 vs abstract 1.4.1 — version drift. Numbers author-reported; preprint ≠ peer review | `official` abstract, `author-self` numbers |
| Treeship | v0.31.14 | **v0.31.2** first-hand confirmed; 0.31.1 and earlier had a `package verify` false-green defect (TS-2026-002) | `official` |
| Vaara | 2.17.0 confirmed | Version **unresolved** (1.78.0 / 2.5.0 / 2.17.0 conflict, PyPI CAPTCHA); license changed Apache-2.0 → AGPL-3.0-or-later. "Second implementation reproduces vectors" repo not found | `third-index` / `unverified` |
| promptfoo | "acquired 2026-03" | Both blogs confirm "agreed to be acquired / subject to closing" (2026-03-09); About page says "now part of OpenAI" without date. Safest: *acquisition announced, closing date unconfirmed* | `official` announcement |

## 3. Standards layer (see CROSSWALK-STANDARDS-LAYER.md for clause mapping)

- **RFC 9943 (SCITT)**, companion RFC 9942 (COSE receipts): the only published
  Standards Track RFC we can cite directly. `official`. Claiming alignment requires
  emitting COSE receipts — we do not.
- **EU AI Act (EU) 2024/1689**: general application date 2026-08-02. **Regulation (EU)
  2026/1744 (Digital Omnibus on AI)**, OJ 2026-07-24, in force 2026-07-27, changed the
  timetable — high-risk obligations to 2027-12-02 / 2028-08-02; Art.50 transparency
  still applied from 2026-08-02. Whether Art.12 / Art.55 were individually amended
  was **not verified** (EUR-Lex正文 fetch returned empty). Do not cite a per-article
  effective date. `official` for the amending regulation's existence, `unverified`
  for Art.12/55 text.
- **ISO/IEC 24970** (AI system logging): stage **60.00 publication-in-progress**,
  not published. `official` (iso.org standard 88723). No alignment claim permitted.
- **OWASP AISVS v1.0**: published, 191 requirements `official`. We have not mapped
  all 191; "aligned with AISVS" would be false.

## 4. What we actually have on this machine (measured 2026-11-21, not claimed from docs)

| Asset | Old doc claim | Measured reality | Command |
|---|---|---|---|
| Second implementation | "one Python implementation" | 70 checks / 0 mismatches, AGREEMENT PASS | `python independent_verifier/cross_check.py` |
| Language-neutral corpus | "15 vectors" | **29 vectors**, 29/29 reproduced by a checker importing nothing from uibc_core | `python tools/conformance_check.py` |
| Browser verifier | "we require clone" | `verify.html` runs S1–S18 client-side, nothing uploaded | open `verify.html` |
| MCP interception | "no interception" | `tools/mcp_gate_proxy.py` JSON-RPC proxy, per-call decision log (honest: "not a gateway") | `python tools/mcp_gate_proxy.py --help` |
| Negative results | "one-off" | `failure_corpus/` F-001…F-006 + `EXTERNAL-ANCHOR.md` four-layer evidence | read files |

These five correct an over-modest self-assessment in the older comparison docs. The
corrections go *toward* accuracy, not toward inflation: each still names its boundary
(second implementation is ours, not a third party's; browser verifier needs hosting;
proxy is not a security boundary; Rekor inclusion still fails).

## Boundary

Internal judgement aid containing competitive assessment — do not publish without
review. GitHub full-page fetches returned empty this round; repo links are official
but key sentences came from search-result page text, so version numbers from GitHub
are marked as official-reference + third-index, not direct full-text verification.
PyPI JSON API was CAPTCHA-blocked. Rows marked `unverified` must stay grey in any
external material until a first-hand source is obtained.
