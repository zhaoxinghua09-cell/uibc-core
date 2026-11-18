# 证据索引（由 `tools/build_evidence_index.py` 生成）

每条检查对应到：验证器里的定义、覆盖它的测试、指向它的红队攻击、以及提到它的文档。**重新生成即可复核**，不会随记忆漂移。

| 检查 | 名称 | 出厂包是否走到 | 测试 | 红队 | 文档 |
|---|---|---|---|---|---|
| S0 | verifier robustness | 否 | 4 | 0 | 9 |
| S1 | package structure | 是 | 8 | 1 | 25 |
| S2 | identity consistency | 是 | 7 | 1 | 17 |
| S3 | lifecycle state machine + semantics | 是 | 9 | 1 | 15 |
| S4 | evidence integrity | 是 | 12 | 3 | 26 |
| S5 | evidence root | 是 | 9 | 3 | 22 |
| S6 | seal signature | 是 | 16 | 1 | 26 |
| S7 | evidence index metadata | 否 | 5 | 1 | 12 |
| S8 | package checkpoint head | 否 | 6 | 2 | 16 |
| S9 | head pinned out-of-band | 否 | 6 | 1 | 17 |
| S10 | attestation closure declared | 否 | 5 | 2 | 7 |
| S11 | strict serialization | 是 | 5 | 1 | 15 |
| S12 | timestamp and identifier strictness | 是 | 6 | 2 | 15 |
| S13 | merkle inclusion proofs | 否 | 8 | 4 | 10 |
| S14 | strict base64 | 否 | 4 | 2 | 6 |
| S15 | anchor event resolution | 否 | 6 | 4 | 9 |
| S16 | external timestamp (RFC 3161) | 否 | 7 | 4 | 10 |
| S17 | linear receipt chain | 否 | 6 | 2 | 12 |
| S18 | policy artefact resolution | 否 | 7 | 2 | 16 |

出厂包判定：`INCONCLUSIVE`，走到 8/19 项（未签名的包停在 S6，后面不越过去）。

**每项检查都至少有一个测试文件提到**。

**红队实测中从未被任何攻击抓到的检查**：S0
（S0 不是检查：它是验证器自身异常时的兜底条目，没有可构造的攻击，因此不计入缺口。）

## 这份索引不能证明什么

- 提到 ≠ 覆盖：一个测试文件里出现 `S4` 不代表它真的构造了越界符号链接。
- 「出厂包是否走到」只反映未签名包的路径；后面的检查由红队阶段的合成包覆盖，不在这里。
- **外部第三方验证：0。** 本索引里的每一行都是我们自己产出的。
