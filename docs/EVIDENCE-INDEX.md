# 证据索引（由 `tools/build_evidence_index.py` 生成）

每条检查对应到：验证器里的定义、覆盖它的测试、指向它的红队攻击、以及提到它的文档。**重新生成即可复核**，不会随记忆漂移。

**测试套件：2074 个用例**（静态计数：`tests/` 下 `def test_*` 的个数，跨平台一致；这是**源码里有几个测试函数**，不等于运行期收集到的用例数——pytest 会把参数化展开成多条（实跑更多），平台跳过又会少一些。别处只引用本页，不再抄写这个数字）。


| 检查 | 名称 | 出厂包是否走到 | 测试 | 红队 | 文档 |
|---|---|---|---|---|---|
| S0 | verifier robustness | 否 | 5 | 0 | 12 |
| S1 | package structure | 是 | 17 | 1 | 37 |
| S2 | identity consistency | 是 | 9 | 1 | 22 |
| S3 | lifecycle state machine + semantics | 是 | 12 | 1 | 22 |
| S4 | evidence integrity | 是 | 24 | 3 | 45 |
| S5 | evidence root | 是 | 14 | 3 | 36 |
| S6 | seal signature | 是 | 26 | 1 | 42 |
| S7 | evidence index metadata | 否 | 7 | 1 | 19 |
| S8 | package checkpoint head | 否 | 9 | 2 | 31 |
| S9 | head pinned out-of-band | 否 | 9 | 1 | 41 |
| S10 | attestation closure declared | 否 | 6 | 2 | 12 |
| S11 | strict serialization | 是 | 7 | 1 | 22 |
| S12 | timestamp and identifier strictness | 是 | 12 | 2 | 22 |
| S13 | merkle inclusion proofs | 否 | 9 | 4 | 14 |
| S14 | strict base64 | 否 | 5 | 2 | 9 |
| S15 | anchor event resolution | 否 | 7 | 4 | 14 |
| S16 | external timestamp (RFC 3161) | 否 | 9 | 4 | 26 |
| S17 | linear receipt chain | 否 | 7 | 2 | 19 |
| S18 | policy artefact resolution | 否 | 9 | 2 | 18 |
| S19 | freshness state | 否 | 5 | 1 | 18 |

出厂包判定：`INCONCLUSIVE`，走到 8/20 项（未签名的包停在 S6，后面不越过去）。

**每项检查都至少有一个测试文件提到**。

**红队实测中从未被任何攻击抓到的检查**：S0
（S0 不是检查：它是验证器自身异常时的兜底条目，没有可构造的攻击，因此不计入缺口。）

## 这份索引不能证明什么

- 提到 ≠ 覆盖：一个测试文件里出现 `S4` 不代表它真的构造了越界符号链接。
- 「出厂包是否走到」只反映未签名包的路径；后面的检查由红队阶段的合成包覆盖，不在这里。
- **外部第三方验证：2 次执行（不是利益独立）** —— 以 `docs/EXTERNAL-NODES.md` 为唯一真源；本索引其余各行都由我们自己产出。
