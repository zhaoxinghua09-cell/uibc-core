# 双实现一致性矩阵（参考验证器 vs 独立读者）

语料 `conformance/oracle/`，两实现读同一批磁盘字节。

| 指标 | 值 |
|---|---|
| cases | 32 |
| compared | 32 |
| verdict_agree | 21 |
| first_agree | 18 |
| set_agree | 15 |
| both_match_oracle | 19 |
| coverage_gap | 7 |
| contradiction | 3 |

独立读者覆盖 10/19 项检查；未覆盖：S9, S11, S13, S14, S15, S16, S17, S18, S19。


| case | mode | 期望 | 参考 | 独立 | 判定同 | 首失败(参考/独立) | 失败集同 |
|---|---|---|---|---|---|---|---|
| oracle-clean | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| oracle-tampered | strict | FAIL | FAIL | FAIL | ✓ | S4/S4 | ✗ |
| oracle-deleted | strict | FAIL | FAIL | FAIL | ✓ | S4/S4 | ✗ |
| oracle-duplicated | strict | FAIL | FAIL | FAIL | ✓ | S5/S5 | ✗ |
| oracle-unsealed | strict | FAIL | FAIL | FAIL | ✓ | S6/S6 | ✓ |
| oracle-s12-id-only | strict | FAIL | FAIL | INCONCLUSIVE | ✗ | S12/— | ✗ |
| oracle-s07-index-extra-member | strict | FAIL | FAIL | PASS | ✗ | S7/— | ✗ |
| oracle-s01-undeclared-file | open | FAIL | FAIL | FAIL | ✓ | S1/V7 | ✗ |
| oracle-s02-identity | open | FAIL | FAIL | FAIL | ✓ | S2/S2 | ✓ |
| oracle-s03-calendar | open | FAIL | FAIL | FAIL | ✓ | S3/V9 | ✗ |
| oracle-s08-log-truncated | open | FAIL | FAIL | FAIL | ✓ | S8/V9 | ✗ |
| oracle-s10-closure | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S10/— | ✗ |
| oracle-s11-duplicate-member | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S11/— | ✗ |
| oracle-s13-merkle-root | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S13/— | ✗ |
| oracle-s14-base64-padding | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S14/— | ✗ |
| oracle-s15-anchor-time | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S15/— | ✗ |
| oracle-s16-token-byte | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S16/— | ✗ |
| oracle-s17-receipt-body | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S17/— | ✗ |
| oracle-s18-policy-artefact | open | FAIL | FAIL | INCONCLUSIVE | ✗ | S18/— | ✗ |
| oracle-s07-index-metadata | open | FAIL | FAIL | FAIL | ✓ | S7/V8 | ✗ |
| accept-one-file | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-many-files | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-unicode-names | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-binary | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-large-text | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-resubmitted | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-typed-evidence | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-lifecycle-events | strict | PASS | PASS | PASS | ✓ | —/— | ✓ |
| accept-anchored-policy | strict | PASS | PASS | INCONCLUSIVE | ✗ | —/— | ✓ |
| accept-unverifiable-seal | open | INCONCLUSIVE | INCONCLUSIVE | INCONCLUSIVE | ✓ | —/— | ✓ |
| oracle-s09-rollback-pin | strict | FAIL | PASS | PASS | ✓ | —/— | ✓ |
| oracle-s19-stale-state | strict | FAIL | PASS | PASS | ✓ | —/— | ✓ |
