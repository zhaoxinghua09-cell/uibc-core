# What each must-reject case rests on

Generated from `conformance/oracle/grounds.json`, which is derived from the
basis table the verifier ships (`uibc_core/basis.py`). Do not edit this page;
edit the data. `tools/build_grounds_page.py > docs/GROUNDS.md`.

The corpus is **31 cases**: 21 must-reject, 9 must-accept, 1 control
(`oracle-clean`). Every one of the 21 must-reject cases names what it rests on;
**5 of them quote the sentence** and `tools/check_grounds.py` re-finds that
sentence in the vendored draft after collapsing whitespace. The rest say what
the requirement is and which document owns it, without claiming a sentence.

Three kinds, and they are not interchangeable:

| kind | what it means | cases |
|---|---|---|
| `draft_mandated` | the draft states the requirement | 5 |
| `borrowed_idea` | the mechanism is borrowed, the check is ours | 9 |
| `own_choice` | nothing to point at: this project defines it | 7 |

## The table

| case | check | kind | points at | the sentence, if there is one |
|---|---|---|---|---|
| `oracle-s01-undeclared-file` | S1 | `own_choice` | this project | — |
| `oracle-s02-identity` | S2 | `draft_mandated` | `draft-noa-scitt-ai-agent-receipt-00.txt` 2 | > Identity manifest:* an out-of-band, operator-vouched binding of agent.id to its authorized key identifier(s) (kid), used to authenticate _which agent_ acted, not merely that a trusted key signed. |
| `oracle-s03-calendar` | S3 | `borrowed_idea` | `draft-maintainer-1f916-agent-record-01` | no sentence quoted |
| `oracle-deleted` | S4 | `own_choice` | this project | — |
| `oracle-tampered` | S4 | `own_choice` | this project | — |
| `oracle-duplicated` | S5 | `borrowed_idea` | `RFC 6962` | no sentence quoted |
| `oracle-unsealed` | S6 | `borrowed_idea` | `RFC 8032` | no sentence quoted |
| `oracle-s07-index-extra-member` | S7 | `own_choice` | this project | — |
| `oracle-s07-index-metadata` | S7 | `own_choice` | this project | — |
| `oracle-s08-log-truncated` | S8 | `borrowed_idea` | `draft-maintainer-1f916-agent-record-01` | no sentence quoted |
| `oracle-s09-rollback-pin` | S9 | `borrowed_idea` | `draft-bailey-scitt-agent-session-receipt` | no sentence quoted |
| `oracle-s10-closure` | S10 | `draft_mandated` | `draft-sharif-agent-audit-trail-03.txt` 13.6 | > An attestation is CLOSED when every component of the closure is covered by a recorded digest or by a recorded, pinned configuration value; it is OPEN when any component is not. |
| `oracle-s11-duplicate-member` | S11 | `borrowed_idea` | `RFC 8785` | no sentence quoted |
| `oracle-s12-id-only` | S12 | `own_choice` | this project | — |
| `oracle-s13-merkle-root` | S13 | `borrowed_idea` | `RFC 6962` | no sentence quoted |
| `oracle-s14-base64-padding` | S14 | `borrowed_idea` | `RFC 4648 §4` | no sentence quoted |
| `oracle-s15-anchor-time` | S15 | `own_choice` | this project | — |
| `oracle-s16-token-byte` | S16 | `draft_mandated` | `rfc3161.txt` 2.4.2 | > The messageImprint MUST have the same value as the similar field in TimeStampReq, provided that the size of the hash value matches the expected size of the hash algorithm identified in hashAlgorithm. |
| `oracle-s17-receipt-body` | S17 | `draft_mandated` | `draft-marques-asqav-compliance-receipts-01.txt` 4.3 | > Implementations MUST emit a previousReceiptHash field, populated as specified by [ACTA-RECEIPTS] (lowercase hex SHA-256 of the JSON Canonicalization Scheme [RFC8785] encoding of the predecessor receipt). The first receipt in a chain MUST set this field to the all-zero SHA-256 value. |
| `oracle-s18-policy-artefact` | S18 | `draft_mandated` | `draft-marques-asqav-compliance-receipts-01.txt` 4.2.2 | > The value MUST be of the form sha256:<hex> and MUST reference a policy artefact that the Deployer retains for the applicable retention window. Verifiers MUST reject Compliance Receipts whose policy_digest does not resolve in the Audit Pack. |
| `oracle-s19-stale-state` | S19 | `borrowed_idea` | `draft-bailey-scitt-agent-session-receipt` | no sentence quoted |

## How to check this page

```
python tools/check_grounds.py      # every quoted sentence, re-found in the draft
python -m unittest tests.test_grounds tests.test_grounds_page
```

`tests/test_grounds.py` also refuses a `clause_absent` row: a check that claims
a draft without a locatable clause has to be reclassified in `uibc_core/basis.py`,
not shipped as an absence.

## What this page does not prove

- Quoting a sentence shows the requirement exists in the document. It does not
  show that this project reads the sentence the way its author intended, nor
  that the check implements all of it.
- A basis is not a defence of the verdict: `own_choice` rows are decisions, and
  a decision can be wrong. What the page buys is that a reader can see which
  kind each case is before arguing with it.
- Nothing here speaks for a third party. The quotations are checked against
  our own copy of the drafts in `docs/spec-sources/`.
