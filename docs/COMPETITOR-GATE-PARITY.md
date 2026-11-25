# 竞品门禁对照：外人能在仓库里复跑什么

审计日期 2026-11-26。17 个 DID 解析/驱动/工具仓库，全部按 **固定 commit** 取 tarball，
记录 tarball 的 sha256，用同一组正则计数，分数由原始计数机械重算（`tools/competitor_gate_parity.py --check`）。
本表量的是**仓库内可被外人复跑的证据**，不是团队能力：计数为 0 只说明"在其源码文本里检索不到"，不说明"他们没做过"。

## 一、怎么量的

1. `codeload.github.com/<repo>/tar.gz/<sha>` 下载，解包，跳过 `.git/node_modules/dist/target/build/vendor` 与缓存目录。
2. 每个文件按路径判断是否测试文件（`tests/`、`spec/`、`__tests__/`、`*Test.java`、`test_*.py`、`*.test.ts`…）。
3. 七个正则分别计数，测试文件内记 `test_hits`、其它记 `nontest_hits`：
   fuzz / mutation-testing / property-based / bit-level / address-derive / exit-code-gate / reject-assertion。
4. 五个维度机械打分：0 无证据、1 点状证据、2 系统性探针 + 可失败的门（只有本仓库）。
5. 规则写在一处（`score_one`），`--check` 用同一函数重算，快照与表格不一致就退出 1。

## 二、对照表

| repository | code files | test files | test KB | D1 | D2 | D3 | D4 | D5 | score |
|---|---|---|---|---|---|---|---|---|---|
| `caict-4iot-dev/uni-registrar-driver-did-bid` | 10 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `caict-4iot-dev/uni-resolver-driver-did-bid` | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `decentralized-identity/did-resolver` | 14 | 1 | 21 | 0 | 0 | 0 | 0 | 0 | 0 |
| `decentralized-identity/ethr-did-resolver` | 120 | 44 | 1190 | 1 | 0 | 1 | 1 | 0 | 3 |
| `decentralized-identity/ion` | 67 | 4 | 1 | 0 | 0 | 0 | 1 | 0 | 1 |
| `decentralized-identity/sidetree-core` | 62 | 21 | 132 | 1 | 0 | 1 | 0 | 0 | 2 |
| `decentralized-identity/universal-resolver` | 155 | 20 | 26 | 1 | 0 | 0 | 0 | 0 | 1 |
| `decentralized-identity/veramo` | 576 | 99 | 771 | 1 | 0 | 1 | 1 | 0 | 3 |
| `digitalbazaar/did-io` | 14 | 3 | 8 | 0 | 0 | 0 | 0 | 0 | 0 |
| `hyperledger/indy-vdr` | 254 | 54 | 174 | 1 | 0 | 1 | 1 | 0 | 3 |
| `sphereon-opensource/ssi-sdk` | 1448 | 260 | 3678 | 1 | 0 | 1 | 1 | 0 | 3 |
| `spruceid/didkit` | 132 | 10 | 41 | 0 | 0 | 1 | 0 | 0 | 1 |
| `spruceid/ssi` | 448 | 59 | 424 | 0 | 0 | 1 | 0 | 0 | 1 |
| `transmute-industries/sidetree.js` | 500 | 82 | 101 | 0 | 0 | 1 | 0 | 0 | 1 |
| `uport-project/ethr-did` | 17 | 4 | 43 | 0 | 0 | 1 | 0 | 0 | 1 |
| `w3c-ccg/did-method-key` | 4 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| `w3c-ccg/did-test-suite` | 21 | 12 | 21 | 0 | 0 | 1 | 0 | 0 | 1 |
| `zhaoxinghua09-cell/uibc-core` (this repository) | 1806 | 273 | 1068 | 2 | 2 | 2 | 2 | 2 | 10 |

D1 门槛＝测试文件内拒绝类断言 ≥10 次；D2＝位级关键词 ≥1；D3＝base58/地址派生关键词 ≥1；
D4＝非测试代码里出现失败退出码 ≥1；D5 对 17 家一律记 0——"注入假断言要求门失败"这种用例，检索不到就当没有。
**最好的一家 3/10，本仓库 10/10。**

## 三、结论（每条都带可数的分母，可被上表打掉）

1. **逐位变异：17 家里有 0 家。** 这一维要的是"把一条报文的每一位翻一遍并归类"；
   没有二进制报文层的实现，连可翻的对象都没有——RFC-011 在本轮之前没有公开实现（`docs/CODEC.md` 有取证）。
2. **跨层单一退出码：17 家里有 5 家。** 那 5 家记 1 是因为仓内有失败退出码（CLI 行为），
   不是把多层证据收进一个码。
3. **门自证：17 家里有 0 家。** 一个没人证伪过的门，通过时说的话只是自我声明。
4. **文档层拒绝断言：17 家里有 6 家**，其中达到 D1 门槛（≥10 次）的按点状证据记 1；
   本仓库记 2 的依据是 31 个变异体、25 个必拒、silent 必须为空——同分不同质，见第四节。

所以"全面超越"这句，能成立的范围只有一句：**在公开仓库里，把文档层、二进制层、地址层的变异证据收进
一道可失败的门，并让门与自证一起随仓交付——17 家里只有本仓库具备完整闭环（10/10，最好的一家 3/10）。**
其余任何"比竞品强"的说法都超出本表。

## 四、本表量不到的

- 关键词检索漏报：竞品可能用别的词（"negative cases"、把 fuzz 写进 CI 配置而非源码）。
- 私有仓库与内部流水线：他们内部做没做，本表无从判断。
- 质量差异：D1 记 1 的家，其拒绝用例是点状的；本仓库量的是另一件事。
- 抽样：17 家是"能代表各条技术路线"的取样，不是 DID 生态的全集。

## 五、复跑

```
python tools/competitor_gate_parity.py --check                   # 离线：快照+重算+表格一致性
python tools/competitor_gate_parity.py --refresh --cache <dir>   # 联网：按固定 sha 重新下载并重算
python tools/competitor_gate_parity.py --json                    # 机读
```

快照：`docs/competitor-parity.json`（含每个仓库的 sha、tarball sha256、字节数、原始计数）。
矩阵图：`docs/COMPETITOR-GATE-PARITY.svg`（由快照生成，字节可复现）。

## 六、引用

- `caict-4iot-dev/uni-registrar-driver-did-bid` @ `68f69ec419c0`：https://github.com/caict-4iot-dev/uni-registrar-driver-did-bid/tree/68f69ec419c0f23c1a7faf95dd8d73aeb5ff30a4
- `caict-4iot-dev/uni-resolver-driver-did-bid` @ `5a933656eb96`：https://github.com/caict-4iot-dev/uni-resolver-driver-did-bid/tree/5a933656eb9631bc65ba535f4bb69aa893d79a79
- `decentralized-identity/did-resolver` @ `005411b26ac3`：https://github.com/decentralized-identity/did-resolver/tree/005411b26ac3002aa4f501673ee4e2ecc96b2a71
- `decentralized-identity/ethr-did-resolver` @ `6e0bd4770249`：https://github.com/decentralized-identity/ethr-did-resolver/tree/6e0bd47702495d259674c6a53e8be3037069dcc1
- `decentralized-identity/ion` @ `424ec87dda60`：https://github.com/decentralized-identity/ion/tree/424ec87dda60c89c0b3c4e46c274eff3124fe484
- `decentralized-identity/sidetree-core` @ `bb4bb16d2383`：https://github.com/decentralized-identity/sidetree-core/tree/bb4bb16d23838cc02bbde0b4ac634e0491ae85fd
- `decentralized-identity/universal-resolver` @ `99838d52a7a6`：https://github.com/decentralized-identity/universal-resolver/tree/99838d52a7a6c7424bf8c895d03d317dcd8cdb3a
- `decentralized-identity/veramo` @ `ac953d9a28db`：https://github.com/decentralized-identity/veramo/tree/ac953d9a28db1faa57266636de7c4ed891bf1b0b
- `digitalbazaar/did-io` @ `940555f002fb`：https://github.com/digitalbazaar/did-io/tree/940555f002fbf69e081e4db5b44b3cd9e0234404
- `hyperledger/indy-vdr` @ `e4902fcd5638`：https://github.com/hyperledger/indy-vdr/tree/e4902fcd5638efb0aaded3a854a56e077f8b32f3
- `sphereon-opensource/ssi-sdk` @ `4f8b21c24659`：https://github.com/sphereon-opensource/ssi-sdk/tree/4f8b21c24659259843b4b802e4a68a635989a590
- `spruceid/didkit` @ `57a3b45111f8`：https://github.com/spruceid/didkit/tree/57a3b45111f8b1003ef1a50cf7cf21c81cd59cb1
- `spruceid/ssi` @ `726f49e7fefb`：https://github.com/spruceid/ssi/tree/726f49e7fefbb726ff41deba331428088bfa782d
- `transmute-industries/sidetree.js` @ `0b17eb9ed7aa`：https://github.com/transmute-industries/sidetree.js/tree/0b17eb9ed7aa787230bfdeaff92cc7eca05d0e7e
- `uport-project/ethr-did` @ `4bbd2ef539ba`：https://github.com/uport-project/ethr-did/tree/4bbd2ef539ba532731508198e5828657c169ff66
- `w3c-ccg/did-method-key` @ `2cc490c38c5a`：https://github.com/w3c-ccg/did-method-key/tree/2cc490c38c5aacf58497a87fc0cf8794668bf716
- `w3c-ccg/did-test-suite` @ `addafb08c84e`：https://github.com/w3c-ccg/did-test-suite/tree/addafb08c84ef3c4dd4a596ebe71f164daa4ceab

