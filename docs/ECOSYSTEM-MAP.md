# Ecosystem map: who is building agent evidence, and what each one actually finished

<!-- facts: current -->


Compiled 2026-11-17. Every row was read from the project's own published text on
that date. "Stage" is the project's own word for itself where it gives one;
where it does not, the stage is inferred from what is published and marked so.

This document exists to stop us from writing claims that a reader can falsify in
one click. It replaced the earlier assumption that the field was thin.

**Source status, stated before the table**: most entries below are read from arXiv
preprints and project sites, i.e. individual drafts and vendor pages, **not** adopted
standards and **not** peer-reviewed publications. Nothing here should be read as a
committee position.

**Verdict words, and what they do not mean**: where this document says a project
"verified" something, it reports what that project's own text claims, not an audit we
performed. Our own verdict has one meaning only, and it is narrower:
"A uibc PASS means: within the observed evidence boundary, no violation was detected.
It does not claim the agent was correct, safe, or wise; that the recorded inputs were
true or complete; or that any real-world outcome followed."

(Six projects, measured rather than described: `docs/PEER-SURVEY.md`.)

## Adoption: the part local tests cannot reach

`docs/IMPLEMENTATION-STATUS.md` records this project in the RFC 7942 four-bucket
format, and all four buckets are empty. `docs/UPSTREAM-SUBMISSION-PLAN.md` says
what each route would cost. Neither is a criticism of the code; both are facts
about where the code has been.

## Head-to-head with the nearest peer

`agent-action-capsule` 0.17.0 is measured against this project in
[COMPETITORS.md](COMPETITORS.md): same day, same hostile inputs, every number
with its command. Short version: it has the Internet-Draft and 23 releases, we
have the second implementation and the shippable suite.

## The field is crowded, and several entries are further along than we are

| project | stage (their word) | signature / canonicalization | time | log / anchoring | independent verification | what we do not have |
|---|---|---|---|---|---|---|
| **Tracekit** — [arXiv 2609.35659](https://arxiv.org/html/2609.35659) | MIT, **v1.4.1** | Ed25519 over RFC 8785 canonical JSON, hash chain per run | not stated as external | RFC 6962 Merkle tree, **C2SP signed notes** with cosigning witnesses | **two verifiers by the same authors: Python, and TypeScript which also runs as one browser page**; they report agreement on 63 bundles and rejection of 33 forgeries (authors' own report, not a third-party replication) | a verifier written by someone other than us; witness cosigning; browser verifier |
| **Treeship** — [treeship.dev](https://www.treeship.dev/) | **v0.31.14**, Apache-2.0, Rust core | Ed25519 / DSSE | not stated | Merkle log + signed checkpoints, local, optional Hub, **Rekor DSSE entries** | receipts verified offline against the verifier's own trust roots | Rekor DSSE publishing; Rust-grade packaging |
| **NovaFabric** — [novafabric.ai](https://novafabric.ai/) | **v0.108.0 experimental**, pip-installable, Apache-2.0 | DSSE, ECDSA P-256, verifier-pinned alg set | RFC 3161 | append-only Merkle log + witness cosigning + MMR | paper says offline path **"has not yet been exercised by an independently implemented verifier"** | four-mode replay; fifteen-entity schema; redaction attestation |
| **agent-receipts** — [npm](https://www.npmjs.com/package/agent-receipts-cli) | v0.1.3, MIT | Ed25519, `sig.alg` in envelope | none | none (roadmap Phase 6) | **spec + 8 conformance vectors + Python reference implementation** | MCP interception with zero code change; language-neutral vector corpus |
| **AIAuditLog** — [PyPI 0.1.0a3](https://pypi.org/project/aiauditlog/0.1.0a3/) | **alpha** | RFC 8785 canonical JSON, SHA-256 digests, optional hash chain | checkpoints, **optional Ed25519 checkpoint signatures** | checkpoints, no external log | schema export, JSONL + SQLite, redaction modes | signed checkpoint policy as a first-class object |
| **fact0** — [fact0.io](https://fact0.io/) | **experimental**, MIT, self-hosted | hash-chained audit records | none | none | signed export files verified against a separately trusted key; ZIP itself not signed | replay; honest "capture gaps remain visible" is the same stance we take |
| **Attested Logs** — [paper](https://pys8vc40ox3z7qxp.public.blob.vercel-storage.com/files/2277477cbbe69000-554a6703-fac0-4715-84a6-d6613c72cda3-Attested-Multi-Agent-Conversation-Logs.pdf) | research library, AutoGen + LangGraph integrations | Ed25519 per message, SHA-256 chain | none | none (Merkle checkpoints planned) | "20+ passing tests", offline self-contained verification | framework integration breadth |
| **Vaara** — [PyPI](https://pypi.org/project/vaara/) | **2.17.0**, AGPL-3.0, installed and CLI inspected | hash chain, export signature | `trail verify-anchor` for external time anchor | `trail publish-head` to a public transparency log (opt-in) | offline verify of signed trail zip; `attest verify` per tool call | call-site policy depth; permissive licensing for bundling (AGPL) |
| **us** — `uibc-core` | 0.4.0, Apache-2.0, public repo | Ed25519 over DSSE PAE of JCS payload | RFC 3161 verified + OTS pending calendar | Rekor entry written; inclusion **not verified** | **two implementations** — Python (20 checks) plus an independent JavaScript checker (18 of 19: structure, Ed25519 seals, Merkle inclusion, anchors, the package checkpoint, the out-of-band pin, RFC 3161 timestamps, the receipt chain, policy artefacts, strict base64, the closure declaration), public anonymous clone, full suite (count in `docs/EVIDENCE-INDEX.md`), 16 red-team scenarios, 37 attacks | witnesses; the checks the JavaScript verifier does not cover (one: S0, which only exists when the verifier itself throws); replay; call-site interception |

## Measured on this machine (Windows, Python 3.13, 2026-11-17)

Not documentation. Actual runs:

| package | installed version | what we ran | outcome |
|---|---|---|---|
| `novafabric` | **0.108.0** | `nova capture` ×3 (default and `--runner local --no-daemon`), `nova seal init`, `nova verify`, `nova inspect` | capture writes a capsule, but its own guard fires every time: *"the capsule directory was replaced while the workload ran (moved, or swapped for a link) … must not be trusted"*. `nova seal init` created a local identity, the capsule still has no `.seal/`, so `nova verify` refuses ("not sealed with NovaSeal"). `nova inspect` reports the asset not found. **The capture → seal → verify path was not executable here.** We did not debug their code. |
| `vaara` | **2.17.0** (PyPI moved from 0.63.0; **AGPL-3.0**) | `vaara --help`, `trail --help`, `attest --help`, `keygen` | subcommand set is far wider than the 0.63.0 page: `trail export` (signed regulator-handoff zip), `trail export-threshold` (k-of-n, no single-key issuance), `trail verify`, **`trail publish-head` to a public transparency log**, **`trail verify-anchor`**, `attest verify` (tool-call envelope with TTL). **The "no anchoring" line we wrote for 0.63.0 must be retired.** |
| `aiauditlog` / `ai_audit_log` | **0.2.0b1** (PyPI moved from 0.1.0a3) | import, `AuditRecorder`, `EventBuilder.create`, `ChainVerifier` | installs and imports; the API is nested pydantic models (`Source`, `Actor`, `Outcome(status=, code=)`). Our end-to-end smoke run **did not complete** - each attempt failed model validation. `ChainVerifier` exists. Recorded as *not established*, not as a product failure. |
| `treeship` | not installed | - | npm/Rust toolchain not attempted this round. |
| `tracekit` | not installed | - | paper only; no package located. |

Two previously documentation-only cells are now measured, and one came back negative: NovaFabric's
sealing path did not yield a verifiable capsule here. That is the first case where our matrix shows a
competitor's instrumented claim failing outside its home setup. It must be stated the way we state our own
Rekor failure - as an observation with a reproduction, never as a verdict on their design.

## The three findings that change our story

1. **Tracekit has already built the thing we were calling our moat.** We said
   "outsiders can re-run it". Tracekit ships two verifiers in two languages, one of
   which runs as a single browser page, and reports agreement on 63 bundles and
   rejection of 33 forgeries; that is the authors' own report, and its verifiers
   were not written by a third party. Note what NovaFabric writes about its own
   format, verbatim: "Neither a second implementation nor that corpus exists yet."
   [arXiv 2609.12594, Determinism of the signed bytes](https://arxiv.org/html/2609.12594).
   So "re-runnable" is no longer ours alone; it is table stakes, and Tracekit holds
   a stronger form of it than we do.
2. **We used to be alone on one thing: publishing a failed verification — and then
   we had to retract it.** Our Rekor inclusion proof did not verify for weeks, and
   neither did a third-party verifier on the same proof. On 2026-11-21 we found that
   both failures came from the same two mistakes on our side: the leaf is
   `SHA-256(0x00 ‖ body)`, not `SHA-256(0x00 ‖ SHA-256(body))`, and a proof folds
   against `inclusionProof.logIndex`, which is a **different number** from
   `entry.logIndex`. The proof verifies
   (`python tools/verify_rekor_inclusion.py --log-index 2883389783`), and it also
   verifies on a third party's entry. See `docs/REKOR-INCLUSION-2026-11-21.md`.
   What survives is the habit, not the claim: the failure was published with a
   reproduction, which is why it could be found wrong. A project that published only
   passing counts would still be asserting it.
3. **The cheapest real gap to close is the conformance corpus.** agent-receipts
   publishes 8 vectors so that "any conforming implementation produces byte-identical
   signatures". We publish Python tests, which is not the same object. A language-neutral
   vector file is a day of work and it converts our "we have tests" into "anyone can
   check us without our code".

## Standards we did not map, and one an external reviewer caught

This map compares projects, not standards. Two published standards that any committee
reader would expect beside it are absent, and one of them was pointed out by an external
review of this document rather than by us:

* **ISO/IEC 23053** — Framework for AI systems using machine learning. None of the
  projects above, and not this repository, maps its record-keeping to that framework's
  model-documentation requirements. Absent means absent: we have no mapping, and no
  project here has published one either.
* **ISO/IEC 24970** — AI system logging. We reference it but publish no clause-by-clause
  mapping; the crosswalk is a separate task, not a claim we make here.

Source for both, direct: <https://www.iso.org/standard/88723.html> is the 24970 page;
23053 has no free full text, so the claim above is limited to "we have no mapping" and
makes no claim about the standard's contents.

## What "total dominance" honestly means here

It cannot mean "nobody else has anything". Six of these projects are shipped or
installable. What it can mean, and what is achievable this quarter:

* **no dimension where we are silent** - each of the six above, we state our
  position and, where they lead, say so in the same sentence;
* **one dimension where we lead with evidence** - a public negative result plus a
  reproduction command, which is rarer than any green feature;
* **one dimension we must upgrade from "claimed" to "demonstrated"** - a second
  verifier or a language-neutral corpus, because Tracekit already did it.
  Status 2026-11-17: the **corpus half** exists (`docs/conformance/vectors.json`, 15
  vectors, reproduced 15/15 by a checker that imports nothing from this repository);
  the **second-implementation half** does not, and no quantity of vectors produces it.

## What was not tested, stated plainly

Three packages were installed and exercised (NovaFabric, Vaara, AIAuditLog); see the
measured section above for exactly what happened, including the two runs that did not
complete. Not tested: Treeship and Tracekit (no install attempted this round), any peer's
behaviour on Linux, and the reverse direction - **no peer has been asked to verify one of
our packages**, so every "they verify ours" cell remains unknown, not passing.

Also not done, and now stated as a gap rather than a plan: the conformance corpus covers
only canonical bytes and Ed25519. Receipt structure, chain linkage, anchoring and policy
have tests, not vectors, so an implementation written elsewhere cannot be measured against
those steps yet. `docs/CONFORMANCE.md` says the same thing to a reader who arrives there
first.

## Sources, direct

* Tracekit paper: <https://arxiv.org/html/2609.35659>
* Treeship: <https://www.treeship.dev/>
* NovaFabric site: <https://novafabric.ai/> ; paper: <https://arxiv.org/html/2609.12594>
* agent-receipts: <https://www.npmjs.com/package/agent-receipts-cli> ; repo: <https://github.com/agent-viscro/agent-receipts>
* AIAuditLog: <https://pypi.org/project/aiauditlog/0.1.0a3/>
* fact0: <https://fact0.io/>
* Vaara: <https://pypi.org/project/vaara/> (2.17.0 measured; 0.63.0 page is stale)
* Attested Logs paper: same PDF linked in the table above (the project has no arXiv
  identifier of its own; the HTML edition above is Tracekit's)
