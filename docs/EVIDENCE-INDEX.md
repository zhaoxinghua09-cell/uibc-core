# 证据索引（由 `tools/build_evidence_index.py` 生成）

每条检查对应到：验证器里的定义、覆盖它的测试、指向它的红队攻击、以及提到它的文档。**重新生成即可复核**，不会随记忆漂移。

**测试套件：745 个用例**（本页由生成器现数，别处只引用本页，不再抄写这个数字）。


| 检查 | 名称 | 出厂包是否走到 | 测试 | 红队 | 文档 |
|---|---|---|---|---|---|
| S0 | verifier robustness | 否 | 5 | 0 | 10 |
| S1 | package structure | 是 | 11 | 1 | 31 |
| S2 | identity consistency | 是 | 8 | 1 | 20 |
| S3 | lifecycle state machine + semantics | 是 | 10 | 1 | 19 |
| S4 | evidence integrity | 是 | 19 | 3 | 40 |
| S5 | evidence root | 是 | 12 | 3 | 33 |
| S6 | seal signature | 是 | 20 | 1 | 35 |
| S7 | evidence index metadata | 否 | 6 | 1 | 16 |
| S8 | package checkpoint head | 否 | 8 | 2 | 23 |
| S9 | head pinned out-of-band | 否 | 8 | 1 | 26 |
| S10 | attestation closure declared | 否 | 6 | 2 | 8 |
| S11 | strict serialization | 是 | 6 | 1 | 17 |
| S12 | timestamp and identifier strictness | 是 | 11 | 2 | 20 |
| S13 | merkle inclusion proofs | 否 | 9 | 4 | 11 |
| S14 | strict base64 | 否 | 5 | 2 | 7 |
| S15 | anchor event resolution | 否 | 7 | 4 | 11 |
| S16 | external timestamp (RFC 3161) | 否 | 8 | 4 | 15 |
| S17 | linear receipt chain | 否 | 7 | 2 | 15 |
| S18 | policy artefact resolution | 否 | 9 | 2 | 15 |
| S19 | freshness state | 否 | 3 | 1 | 8 |

出厂包判定：`INCONCLUSIVE`，走到 8/20 项（未签名的包停在 S6，后面不越过去）。

**每项检查都至少有一个测试文件提到**。

**红队实测中从未被任何攻击抓到的检查**：S0
（S0 不是检查：它是验证器自身异常时的兜底条目，没有可构造的攻击，因此不计入缺口。）

## 这份索引不能证明什么

- 提到 ≠ 覆盖：一个测试文件里出现 `S4` 不代表它真的构造了越界符号链接。
- 「出厂包是否走到」只反映未签名包的路径；后面的检查由红队阶段的合成包覆盖，不在这里。
- **外部第三方验证：0。** 本索引里的每一行都是我们自己产出的。
