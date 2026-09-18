---
title: 'uibc-core: Verifiable Evidence Packages and Gate Validation for Autonomous AI Agent Lifecycle Governance'
tags:
  - Python
  - AI governance
  - agent identity
  - reproducibility
  - AI transparency
authors:
  - name: Xinghua Zhao
    orcid: 0009-0001-0512-1237   # 已核验：claimed、邮箱已验证、公开记录
    affiliation: 1
affiliations:
  - name: Independent Researcher
    index: 1
date: 18 September 2026
bibliography: paper.bib
---

# Summary

Autonomous AI agents are increasingly deployed across systems and service boundaries,
yet the accountability question — *who did what, and on what evidence, after an agent
moves between contexts* — lacks both a benchmark and a tooling baseline. `uibc-core`
is a reference implementation of the Universal Identity & Behavior Credentials (UIBC)
proposal [PROPOSAL, non-standard]: a registry for agent identity registration, an
evidence layer binding content hashes to tamper-evident seals, and a gate layer
enforcing lifecycle state transitions through machine-checkable validation rules.

The toolchain produces a structured evidence package (`.uibc` bundle) for each agent
identity, runs four preservation checks plus injection-detection and anti-gaming
heuristics against it, and emits a scoped validation report: a PASS verdict asserts
only that *no violation was observed within the evidenced boundary* — never absolute
trustworthiness. Release artifacts are anchored in public transparency infrastructure
(Sigstore Rekor transparency log, OpenTimestamps, Software Heritage archive, and a
Zenodo versioned archive), making the toolchain itself an operating example of the
evidence discipline it proposes.

# Statement of need

Multi-agent and agent-migration scenarios (re-binding an agent to a new runtime,
model, or operator) currently have performance benchmarks but no accountability
baseline: after a move, there is no standard, machine-verifiable answer to whether
the agent that operates is the agent that was validated, nor what evidence survives
the transition. Existing identity systems (OAuth/OIDC, W3C DID/VC) model *who an
agent is*, but not *what evidence binds a behaviour claim to that identity over a
lifecycle*. `uibc-core` fills this gap for researchers studying agent governance,
for platform teams implementing agent registries, and for auditors needing
reproducible checks on agent provenance claims.

# State of the field

Verifiable-credential frameworks and content provenance standards (W3C VC Data
Model, C2PA) address credential issuance and media provenance respectively.
Supply-chain transparency tools (Sigstore, in-toto, SLSA) protect artifact
integrity in software delivery. None of these, individually or combined, define a
lifecycle-scoped evidence bundle for *agent behaviour claims* with gate semantics
for state transitions. `uibc-core` composes the above primitives into an
application-layer discipline and defines the validation vocabulary that the
adjacent ecosystems do not specify.

# Software design

`uibc-core` is a zero-dependency Python package (stdlib only) with three modules:
registry (identity records), evidence (hash/seal construction), and gates (state
machine + validators). The CLI supports package creation, validation, and report
emission; validation semantics are intentionally conservative and scoped (see
Summary). Test coverage comprises 122 unit/integration tests and 7 subtests,
executed in CI on both Python 3.12 and 3.13.

# Research impact statement

`uibc-core` is intended to be cited as the reference tooling in studies of agent
accountability, agent migration auditing, and AI transparency compliance. It has
been deployed as the enforcement mechanism for a public software competition
benchmarks suite (post-migration judgement and accountability track) and is under
community discussion as an implementation reference in relevant standards
communities.

# AI usage disclosure

Development of `uibc-core` used AI assistance (Claude-family models via the
WorkBuddy agent environment, 2026) for code drafting, test scaffolding,
documentation, and paper text. All AI-assisted outputs were reviewed, edited, and
validated by the author, who made all core design decisions (evidence model, gate
semantics, scoped-validation doctrine, disclosure-first governance stance). The
author affirms full responsibility for accuracy, originality, and licensing of all
materials.

# References

<!-- TODO: bib 条目见 paper.bib；正式投稿前逐条核验 DOI -->
