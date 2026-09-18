# Security Policy

## Scope

`uibc-core` is a **verification** toolkit: it seals agent actions into evidence
packages and lets a third party verify them offline. A flaw in this code is a
flaw in someone's evidence chain, so we take reports seriously.

In scope:

- **Seal / signature bypass** — a package that verifies PASS but whose contents
  were altered after sealing.
- **Evidence root collisions or non-determinism** — two different package
  contents producing the same evidence root, or the same content producing
  different roots across runs.
- **Verifier soundness** — a malformed, truncated, or crafted package that
  causes the verifier to return PASS when it should return FAIL or
  INCONCLUSIVE.
- **Gate bypass** — reaching a lifecycle state through a path the state machine
  should reject.
- **Denial of service in the verifier** — unbounded memory/CPU/time on
  adversarial input.
- **Registry integrity** — any path that can rewrite or delete an existing
  line in the append-only registries.

Out of scope (by design, and documented as such):

- **Truth of the content.** UIBC verifies *integrity and attribution*, not
  whether a claim is factually correct.
- **Semantic memory drift.** Our preservation checks compare recorded fields by
  memory id; they do not detect meaning change that leaves those fields intact.
- **Security of a producer's key handling.** If you lose or leak your own
  signing key, that is outside the protocol's guarantee.

## Supported versions

| Version | Status |
|---|---|
| 0.2.x (current) | Supported |
| 0.1.x | Unsupported — v0.1 had no signatures and a full-forgery case was **demonstrably UNDETECTED**. Do not rely on it. |

## Reporting a vulnerability

Please **do not open a public issue** for a security report.

Email: **zhaoxinghua06@126.com** with the subject prefix `[uibc-security]`.

Include, as far as you can:

1. Affected version / commit hash.
2. A minimal reproduction (a package file, or the commands that build it).
3. Expected vs observed verification verdict.
4. Impact assessment — what a real-world attacker gains.

We aim to acknowledge within **7 days**. This is a single-maintainer project
run as an independent research effort, with no commercial support contract and
no bug bounty — please calibrate your expectations accordingly. We will credit
reporters in `CHANGELOG.md` unless you ask us not to.

## Our own adversarial testing

We consider a claim credible only if it has been attacked. The repository
therefore contains, and keeps growing:

- `failure_corpus/` — real failure cases, including the v0.1 full-forgery case
  that motivated signatures, kept public rather than quietly patched.
- `tests/` — unit suite plus stress scenarios (large-payload hashing, long event
  chains, adversarial verify).
- `independent_verifier/` — a second, zero-dependency implementation used for
  cross-checking, so the specification's determinism is tested, not assumed.

If you find that any published claim in `README.md` overstates what the code
actually does, that is also a security-relevant bug. Report it.
