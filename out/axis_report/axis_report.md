| case | expected | measured | structure | seal | anchor | freshness | first fail (exp/obs) | ok |
|---|---|---|---|---|---|---|---|---|
| oracle-clean | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| oracle-tampered | FAIL | FAIL | FAIL | PASS | N/A | N/A | S4/S4 | ✓ |
| oracle-deleted | FAIL | FAIL | FAIL | PASS | N/A | N/A | S4/S4 | ✓ |
| oracle-duplicated | FAIL | FAIL | FAIL | PASS | N/A | N/A | S5/S5 | ✓ |
| oracle-unsealed | FAIL | FAIL | PASS | FAIL | N/A | N/A | S6/S6 | ✓ |
| oracle-s12-id-only | FAIL | FAIL | FAIL | PASS | N/A | N/A | S12/S12 | ✓ |
| oracle-s01-undeclared-file | FAIL | FAIL | FAIL | INCONCLUSIVE | N/A | N/A | S1/S1 | ✓ |
| oracle-s02-identity | FAIL | FAIL | FAIL | INCONCLUSIVE | N/A | N/A | S2/S2 | ✓ |
| oracle-s03-calendar | FAIL | FAIL | FAIL | INCONCLUSIVE | N/A | N/A | S3/S3 | ✓ |
| oracle-s08-log-truncated | FAIL | FAIL | FAIL | INCONCLUSIVE | N/A | N/A | S8/S8 | ✓ |
| oracle-s10-closure | FAIL | FAIL | PASS | INCONCLUSIVE | N/A | N/A | S10/S10 | ✓ |
| oracle-s11-duplicate-member | FAIL | FAIL | FAIL | INCONCLUSIVE | N/A | N/A | S11/S11 | ✓ |
| oracle-s13-merkle-root | FAIL | FAIL | PASS | INCONCLUSIVE | N/A | N/A | S13/S13 | ✓ |
| oracle-s14-base64-padding | FAIL | FAIL | FAIL | INCONCLUSIVE | PASS | N/A | S14/S14 | ✓ |
| oracle-s15-anchor-time | FAIL | FAIL | PASS | INCONCLUSIVE | FAIL | N/A | S15/S15 | ✓ |
| oracle-s16-token-byte | FAIL | FAIL | PASS | INCONCLUSIVE | FAIL | N/A | S16/S16 | ✓ |
| oracle-s17-receipt-body | FAIL | FAIL | PASS | INCONCLUSIVE | N/A | N/A | S17/S17 | ✓ |
| oracle-s18-policy-artefact | FAIL | FAIL | PASS | INCONCLUSIVE | PASS | N/A | S18/S18 | ✓ |
| oracle-s07-index-metadata | FAIL | FAIL | FAIL | INCONCLUSIVE | N/A | N/A | S7/S7 | ✓ |
| accept-one-file | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-many-files | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-unicode-names | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-binary | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-large-text | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-resubmitted | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-typed-evidence | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-lifecycle-events | PASS | PASS | PASS | PASS | N/A | N/A | —/— | ✓ |
| accept-anchored-policy | PASS | PASS | PASS | PASS | PASS | N/A | —/— | ✓ |
| oracle-s09-rollback-pin | FAIL | FAIL | PASS | PASS | N/A | FAIL | S9/S9 | ✓ |
| oracle-s19-stale-state | FAIL | FAIL | PASS | PASS | N/A | FAIL | S19/S19 | ✓ |
合计 30 例，一致 30，分歧 0。
