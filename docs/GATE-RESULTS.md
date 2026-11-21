# Gate results, 21 November 2026

What this page is: the numbers our own gates produced on a given commit, the command that
reproduces each one, and the places where the answer is not a clean pass. It exists so a
reader does not have to take a summary on trust, and so the parts that are still partial are
as visible as the parts that pass.

Commit: `dda2955` (main). Machine: Windows 11, Python 3.13, no network assumptions beyond
HTTPS to the hosts named below.

## The five gates

| Gate | Command | Result on `dda2955` |
| --- | --- | --- |
| Conformance against T/ISC 0174—2026 | `python tools/gateway_conformance.py --md docs/gateway-conformance-0174.md --json tools/out/gateway_0174.json --html docs/gateway-conformance-0174.html` | 43 rows: PASS 21 / PARTIAL 22 / MISSING 0; probes 37/37 |
| Citation reachability | `python tools/check_citations.py` | 46 of 49 links answer 200 from here; the three that do not are named in `tools/out/citations_result.json` |
| Red team | `python tools/redteam_suite.py` | 16 cases: 12 refused as required, 2 allowed by design (RT08 50 MB, RT10 re-signed after key rotation), 1 SKIP (symlink creation is restricted on this host), 1 INCONCLUSIVE (seal deleted, `trust=unattested`) |
| Outsider run from a clean clone | `python tools/outsider_run.py --repo . --label outsider_dda2955` | seven steps, exit code 0 each |
| External node receipt | `python tools/external_node_check.py --out tools/out/external_node_result.json` | `CONSISTENT`: independent PASS, reference PASS, probes 3/3 rejected |

Per-domain split of the 43 rows: identity distribution 6 PASS / 9 PARTIAL; protocol
adaptation 7 / 4; routing and addressing 4 / 3; security 4 / 6. No domain has a MISSING row.

Test suite on the same commit: `python -m pytest tests -q` → 1250 passed, 25 skipped. Two
tests that shell out to `git` fail on a host where `git` is not on `PATH`; with it on `PATH`
they pass (5 passed, 1 skipped), which is 1252 passed / 26 skipped overall.

## What "3/3 rejected" means here, and what it meant before

The external-node receipt has one field that changed meaning on 21 November, so it is worth
stating plainly. Until PR #356, `independent_verifier/iverify.py` had no `__main__` block:
`python iverify.py <package>` exited 0 without verifying anything, and every caller that read
the exit code recorded `independent=PASS`. The three negative probes were refused by the
reference verifier and **allowed** by the independent one, and the receipt still said
`CONSISTENT` because it only compared the clean package.

After #356 the verifier has an entry point, `external_node_check.py` imports it instead of
shelling out, and the receipt carries `reference_rejected` and `independent_rejected`
separately. On `dda2955` both are true for all three probes. Reading a receipt produced
before that commit as if it said the same thing would be wrong.

## Limits, stated rather than hidden

- **Seal verification is unanchored.** `signatures/seal.json` in the sample package is a
  symmetric HMAC. A stranger can confirm internal consistency, not authorship, so the
  independent verifier reports V8 as `INCONCLUSIVE` and the reference reports
  `trust_level=unanchored`. An Ed25519 seal with a published key is what turns that into a
  third-party check.
- **No distinct "stale answer" state.** IETF Agentproto CC1-10 asks a participant to tell a
  negative answer, an answer older than policy allows, and no answer apart. This repository
  distinguishes an active agent from a suspended one (suspended → 403 with `-32001`) and
  does not carry a separate expired-answer bit. That row is PARTIAL, not PASS.
- **Semantic routing is Jaccard on token sets**, not embeddings; the 0174 row for it is
  marked from that measurement, not from an intention.
- **Two red-team cases do not end in a refusal.** RT08 is accepted because a 50 MB body is
  within the configured ceiling; RT10 is accepted because the package was re-signed
  consistently after a key rotation. Both are recorded as allowed-by-design rather than
  quietly dropped.

## Reproducing without our machine

```
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core
cd uibc-core
python tools/conformance_harness.py --repo .
python tools/outsider_run.py --repo . --label mine
python tools/external_node_check.py --out my_receipt.json
```

`external_node_check.py` needs no credentials and no private package: it builds its probes
from the repository, runs both verifiers, and writes the receipt.
