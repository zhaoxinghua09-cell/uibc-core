# S6 回执 · 20261117_23_ecosystem-map-claims-v1_siliconflow

| 项 | 值 |
|---|---|
| peer | `siliconflow-deepseek` |
| 模型 | `deepseek-ai/DeepSeek-V3` |
| 温度 | 0 |
| tokens | prompt=1992 / completion=140 |
| key 指纹 | sha256[:16] = `c16e5969afc0fa57`（不落明文） |
| 收到时间 | 2026-11-17T09:45:47Z |
| 输入 | 仅被审文本正文（已去 Subject 行），未附任何本方分析 |

## 回执原文（一字未改）

```
1. Yes: "A second implementation is exactly what NovaFabric's paper says does not exist for its own format."  
   - This claims interpretation of NovaFabric's paper ("does not exist") without providing the exact quote or verifiable source location. A GitHub record alone couldn't validate this paraphrasing.

2. Yes: "two verifiers: Python and TypeScript, the latter also a single browser page; 63 bundles agreed, 33 forgeries rejected"  
   - The claim of independence between verifiers is unfalsifiable without access to both codebases' commit histories or authorship metadata to confirm no shared development.

OVERALL = SAFE-AS-IS
```

## 被审文本（供复核）

```
# Ecosystem map: who is building agent evidence, and what each one actually finished

Compiled 2026-11-17. Every row was read from the project's own published text on
that date. "Stage" is the project's own word for itself where it gives one;
where it does not, the stage is inferred from what is published and marked so.

This document exists to stop us from writing claims that a reader can falsify in
one click. It replaced the earlier assumption that the field was thin.

## The field is crowded, and several entries are further along than we are

| project | stage (their word) | signature / canonicalization | time | log / anchoring | independent verification | what we do not have |
|---|---|---|---|---|---|---|
| **Tracekit** — [arXiv 2609.35659](https://arxiv.org/html/2609.35659) | MIT, **v1.4.1** | Ed25519 over RFC 8785 canonical JSON, hash chain per run | not stated as external | RFC 6962 Merkle tree, **C2SP signed notes** with cosigning witnesses | **two verifiers: Python and TypeScript, the latter also a single browser page**; 63 bundles agreed, 33 forgeries rejected | cross-language verifier; witness cosigning; browser verifier |
| **Treeship** — [treeship.dev](https://www.treeship.dev/) | **v0.31.14**, Apache-2.0, Rust core | Ed25519 / DSSE | not stated | Merkle log + signed checkpoints, local, optional Hub, **Rekor DSSE entries** | receipts verified offline against the verifier's own trust roots | Rekor DSSE publishing; Rust-grade packaging |
| **NovaFabric** — [novafabric.ai](https://novafabric.ai/) | **v0.108.0 experimental**, pip-installable, Apache-2.0 | DSSE, ECDSA P-256, verifier-pinned alg set | RFC 3161 | append-only Merkle log + witness cosigning + MMR | paper says offline path **"has not yet been exercised by an independently implemented verifier"** | four-mode replay; fifteen-entity schema; redaction attestation |
| **agent-receipts** — [npm](https://www.npmjs.com/package/agent-receipts-cli) | v0.1.3, MIT | Ed25519, `sig.alg` in envelope | none | none (roadmap Phase 6) | **spec + 8 conformance vectors + Python reference implementation** | MCP interception with zero code change; language-neutral vector corpus |
| **AIAuditLog** — [PyPI 0.1.0a3](https://pypi.org/project/aiauditlog/0.1.0a3/) | **alpha** | RFC 8785 canonical JSON, SHA-256 digests, optional hash chain | checkpoints, **optional Ed25519 checkpoint signatures** | checkpoints, no external log | schema export, JSONL + SQLite, redaction modes | signed checkpoint policy as a first-class object |
| **fact0** — [fact0.io](https://fact0.io/) | **experimental**, MIT, self-hosted | hash-chained audit records | none | none | signed export files verified against a separately trusted key; ZIP itself not signed | replay; honest "capture gaps remain visible" is the same stance we take |
| **Attested Logs** — [paper](https://pys8vc40ox3z7qxp.public.blob.vercel-storage.com/files/2277477cbbe69000-554a6703-fac0-4715-84a6-d6613c72cda3-Attested-Multi-Agent-Conversation-Logs.pdf) | research library, AutoGen + LangGraph integrations | Ed25519 per message, SHA-256 chain | none | none (Merkle checkpoints planned) | "20+ passing tests", offline self-contained verification | framework integration breadth |
| **Vaara** — [PyPI 0.63.0](https://pypi.org/project/vaara/0.63.0/) | released | hash chain, export signature | none stated | none | offline verify of exported trail | call-site interception |
| **us** — `uibc-core` | 0.3.0, Apache-2.0, public repo | Ed25519 over DSSE PAE of JCS payload | RFC 3161 verified + OTS pending calendar | Rekor entry written; inclusion **not verified** | **one Python implementation**, public anonymous clone + 303 tests + 15 red-team cases | second verifier; witnesses; replay; call-site interception |

## The three findings that change our story

1. **Tracekit is ahead of us on the dimension we were calling our moat.** We said
   "outsiders can re-run it". Tracekit ships *two independent verifiers* in two
   languages, one of which runs as a single browser page, and reports that both
   agree on 63 bundles and reject all 33 forgeries. A second implementation is
   exactly what NovaFabric's paper says does not exist for its own format. So the
   "re-runnable" claim is no longer ours alone - it is now table stakes, and
   Tracekit holds the stronger version of it.<RichMediaReference>["https://arxiv.org/html/2609.35659"]</RichMediaReference>
2. **We are still alone on one thing: publishing a failed verification.** Our Rekor
   inclusion proof does not verify, our own RFC 6962 walk fails, and the third-party
   `rekor_log_verifier` fails on the same proof with a different root. None of the
   projects above publishes that kind of negative result; they publish passing
   experiment counts. A negative result with a reproduction command is the one asset
   nobody in this table is competing for.
3. **The cheapest real gap to close is the conformance corpus.** agent-receipts
   publishes 8 vectors so that "any conforming implementation produces byte-identical
   signatures". We publish Python tests, which is not the same object. A language-neutral
   vector file is a day of work and it converts our "we have tests" into "anyone can
   check us without our code".

## What "total dominance" honestly means here

It cannot mean "nobody else has anything". Six of these projects are shipped or
installable. What it can mean, and what is achievable this quarter:

* **no dimension where we are silent** - each of the six above, we state our
  position and, where they lead, say so in the same sentence;
* **one dimension where we lead with evidence** - a public negative result plus a
  reproduction command, which is rarer than any green feature;
* **one dimension we must upgrade from "claimed" to "demonstrated"** - a second
  verifier or a language-neutral corpus, because Tracekit already did it.

## Sources, direct

* Tracekit paper: <https://arxiv.org/html/2609.35659>
* Treeship: <https://www.treeship.dev/>
* NovaFabric site: <https://novafabric.ai/> ; paper: <https://arxiv.org/html/2609.12582>
* agent-receipts: <https://www.npmjs.com/package/agent-receipts-cli> ; repo: <https://github.com/agent-viscro/agent-receipts>
* AIAuditLog: <https://pypi.org/project/aiauditlog/0.1.0a3/>
* fact0: <https://fact0.io/>
* Vaara: <https://pypi.org/project/vaara/0.63.0/>
* Attested Logs paper: <https://arxiv.org/abs/2609.35659> (HTML edition linked above)

## What was not tested, stated plainly

None of the packages above was installed on this machine. Every cell about their
behaviour comes from their published text. Running them - `pip install novafabric`
and `nova verify`, `npm i -g treeship`, `pip install aiauditlog` - would replace
"documented" with "measured", and that is the next step, not a finished claim.
```
