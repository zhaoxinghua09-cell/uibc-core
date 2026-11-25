# 变异探针（参考验证器单字段变异）

源包 `conformance/oracle/cases/oracle-clean`；变异 12 个，杀掉 11，归因正确 8。

| 变异 | 目标检查 | verdict | 失败集 | killed | attributed |
|---|---|---|---|---|---|
| evidence-byte | S4 | FAIL | S4,S8 | 是 | 是 |
| index-hash | S4 | FAIL | S4 | 是 | 是 |
| index-type | S4 | FAIL | S7,S8 | 是 | **否** |
| index-duplicate | S12 | FAIL | S12,S7,S8,S5 | 是 | 是 |
| manifest-count | S5 | FAIL | S12 | 是 | **否** |
| manifest-agent | S2 | FAIL | S2 | 是 | 是 |
| manifest-root | S5 | FAIL | S5 | 是 | 是 |
| extra-root-file | S1 | FAIL | S1 | 是 | 是 |
| evidence-removed | S4 | FAIL | S4,S8 | 是 | 是 |
| lifecycle-state | S3 | FAIL | S3,S8 | 是 | 是 |
| lifecycle-drop | S3 | FAIL | S8 | 是 | **否** |
| index-extra-field | （无检查声明此约束） | PASS | — | **否** | **否** |
