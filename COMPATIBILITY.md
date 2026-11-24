# UIBC compatibility registry

One row per implementation, republished whenever the test suite or the
supported-identity list changes. The point of this file is not to look
impressive — it is that **every row can be checked by someone else**, and the
`reviewer independence` column says plainly who ran it.

A row with `maintainer` in that column describes our own run. That is useful and
it is not independent validation. `UIBC/uibc-bench` exists so a second party can
run the same instruments and add a row with their own name in it.

| # | Implementation | Repository | Version | Identity methods | Test suite | Result | Evidence | Verified on | Reviewer independence | Known limitations |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | uibc-core (Python, stdlib only) | `zhaoxinghua09-cell/uibc-core` | `0.4.33` + Unreleased (six China-registry DID methods, seven-state result vocabulary) | `did:key`, `did:web`, `did:cn`, `did:ioa`, `did:cndid`, `did:ctid` (validate only), `did:oan` (validate only), `did:cndomain` | `pytest -q` (full suite) + `tests/test_did_cn.py` + `tests/test_interop_result.py` | full suite `1430 passed / 25 skipped / 0 failed`; DID subset `56 passed`; result vocabulary `14 passed` | CI log of the branch, `uibc-bench` gate `GREEN 5/5` on the public snapshot | 2026-11-24 | **maintainer** (author-run, not third-party) | single implementation — cross-implementation parity not yet demonstrated; `did:wba` not wired; `did:ctid` / `did:oan` validate only, no resolution channel published |

Note on one flake seen during this run: `tests/test_registry_server.py::test_07_post_refused_405`
failed once under full-suite load with `ConnectionAbortedError [WinError 10053]` (Windows
loopback, a client-side abort while the server wrote a 405), then passed on isolated re-run
`9 passed` and on the full-suite re-run above. Recorded here rather than quietly retried —
a test that is timing-sensitive on one platform is a fact about the test, not about the code.


## How to add a row

1. Run this repository's conformance suite against your implementation, not ours:
   `python tools/run_conformance.py --verify "<your verifier cmd> {pkg}" --name <you> --json`
   Record every case verdict, not just the totals. If your implementation emits
   check identifiers, compare them case by case — `conformance/manifest.json`
   states which checks each case must report.
   Then run the language-neutral corpus in `docs/conformance/vectors.json` with
   `python tools/conformance_check.py` and record `n/29`.
2. `git clone https://github.com/zhaoxinghua09-cell/uibc-core && cd uibc-core && python -m pytest -q`
   Record `passed / skipped / failed`.
3. Fill the table. In `reviewer independence`, write `independent` only if you
   are not the author and you can attach the execution record (log path, run
   date, machine). Otherwise write `maintainer` or `affiliated:<org>`.
4. Never edit another party's row. Add yours.

## What this table deliberately does not claim

- It does not claim any of these implementations are *good* — only that they
  produced a stated result under a stated suite.
- It does not claim interoperability between rows until a parity run exists
  (same fixtures, two implementations, compared result by result). One row
  cannot show parity; the `0 (not yet run)` in Known limitations is the honest
  reading.
- It does not claim endorsement by any registry, foundation or standards body.
