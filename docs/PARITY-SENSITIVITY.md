# 敏感性检验：把 D1 的规则放松，结论会不会翻（每次 `--run` 重写本页）

审计日 2026-11-26。**25 家，严格规则下最好 3/10，放宽后最好 3/10 → 结论不翻（最好仍是同一家）。**

- 严格规则（现行）：一行里既要出现断言、又要出现拒绝词。
- 放宽规则：断言行前后 ±2 行内出现拒绝词即可。放宽只会加分，不会减分。

| 仓库 | 严格断言行 | 放宽后 | D1 | 得分 |
|---|---|---|---|---|
| `decentralized-identity/did-jwt` | 51 | 117 | 1 → 1 | 3 → 3 |
| `decentralized-identity/ethr-did-resolver` | 6 | 23 | 1 → 1 | 3 → 3 |
| `decentralized-identity/veramo` | 66 | 129 | 1 → 1 | 3 → 3 |
| `docknetwork/sdk` | 15 | 54 | 1 → 1 | 3 → 3 |
| `hyperledger/aries-cloudagent-python` | 22 | 50 | 1 → 1 | 3 → 3 |
| `hyperledger/aries-framework-go` | 11 | 11 | 1 → 1 | 3 → 3 |
| `hyperledger/indy-sdk` | 10 | 53 | 1 → 1 | 3 → 3 |
| `hyperledger/indy-vdr` | 9 | 9 | 1 → 1 | 3 → 3 |
| `sphereon-opensource/ssi-sdk` | 123 | 148 | 1 → 1 | 3 → 3 |
| `ceramicnetwork/js-did` | 28 | 43 | 1 → 1 | 2 → 2 |
| `WeBankBlockchain/WeIdentity` | 0 | 0 | 0 → 0 | 0 → 0 |
| `caict-4iot-dev/uni-registrar-driver-did-bid` | 0 | 0 | 0 → 0 | 0 → 0 |
| `caict-4iot-dev/uni-resolver-driver-did-bid` | 0 | 0 | 0 → 0 | 0 → 0 |
| `decentralized-identity/did-resolver` | 0 | 2 | 0 → 0 | 0 → 0 |
| `decentralized-identity/ion` | 0 | 0 | 0 → 0 | 0 → 0 |
| `decentralized-identity/sidetree-core` | 0 | 0 | 0 → 0 | 0 → 0 |
| `decentralized-identity/universal-resolver` | 2 | 6 | 0 → 1 | 0 → 1 **← 变了** |
| `digitalbazaar/did-io` | 0 | 0 | 0 → 0 | 0 → 0 |
| `ontio/ontology-did` | 0 | 0 | 0 → 0 | 0 → 0 |
| `spruceid/didkit` | 0 | 0 | 0 → 0 | 0 → 0 |
| `spruceid/ssi` | 0 | 3 | 0 → 0 | 0 → 0 |
| `transmute-industries/sidetree.js` | 0 | 0 | 0 → 0 | 0 → 0 |
| `uport-project/ethr-did` | 1 | 1 | 0 → 0 | 0 → 0 |
| `w3c-ccg/did-method-key` | 0 | 0 | 0 → 0 | 0 → 0 |
| `w3c-ccg/did-test-suite` | 0 | 0 | 0 → 0 | 0 → 0 |

## 读法

结论没有翻：25 家里只有 1 家（`decentralized-identity/universal-resolver`）因放宽而 +1 分，最好仍是 3/10。

这说明「最好 3/10」不是我们正则拼写方式的产物。反过来，如果哪天有人在宽松规则下拿到 4 分，`--check` 会直接失败并写出「withdraw the headline」——那时该撤回的是主张，不是改规则。

复跑：`python tools/parity_sensitivity.py --run --cache <tarball 缓存目录>`（需重新取 25 个固定 commit 的 tarball）；离线判定：`python tools/parity_sensitivity.py --check`。
