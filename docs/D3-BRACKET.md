# D3 是个区间，不是一个数（每次 `--run` 重写本页）

审计日 2026-11-26。**最好竞品：宽规则 3/10，严规则 3/10；本仓 10/10 与 10/10 两种规则下不变。**

本仓为什么两端同分：本仓 D3 来自可执行的地址探针（256 翻键 0 相撞 / 1710 次替换 0 通过），不依赖关键词，所以宽规则与严规则下同分。

- 宽规则（表现行）：test 文件里出现 `base58|bs58|deriveAddress|derive_address` 即记 1 分。
- 严规则：只认 `deriveAddress|derive_address|addressFrom(PublicKey|Key)?|publicKeyToAddress|toChecksumAddress`。

为什么两个都要给：宽规则会把 `publicKeyBase58: '...'` 这种字面量当成"地址派生"证据（证据行见 `docs/COMPETITOR-EVIDENCE-LINES.md`）；严规则又可能漏掉"绑定了地址但没写 derive"的仓。单一数字在这里一定是偏的，所以给区间，并标明区间两端各自的规则。

| 仓库 | D3 宽 | D3 严 | 得分 宽 → 严 |
|---|---|---|---|
| `decentralized-identity/did-jwt` | 1 | 1 | 3 → 3 |
| `decentralized-identity/ethr-did-resolver` | 1 | 0 | 3 → 2 **← 变了** |
| `decentralized-identity/veramo` | 1 | 0 | 3 → 2 **← 变了** |
| `docknetwork/sdk` | 1 | 0 | 3 → 2 **← 变了** |
| `hyperledger/aries-cloudagent-python` | 1 | 0 | 3 → 2 **← 变了** |
| `hyperledger/aries-framework-go` | 1 | 0 | 3 → 2 **← 变了** |
| `hyperledger/indy-sdk` | 1 | 0 | 3 → 2 **← 变了** |
| `hyperledger/indy-vdr` | 1 | 0 | 3 → 2 **← 变了** |
| `sphereon-opensource/ssi-sdk` | 1 | 0 | 3 → 2 **← 变了** |
| `cheqd/cheqd-node` | 1 | 0 | 3 → 2 **← 变了** |
| `hyperledger/aries-framework-javascript` | 1 | 0 | 3 → 2 **← 变了** |
| `ceramicnetwork/js-did` | 1 | 0 | 2 → 1 **← 变了** |
| `TBD54566975/dwn-sdk-js` | 0 | 0 | 1 → 1 |
| `WeBankBlockchain/WeIdentity` | 0 | 0 | 0 → 0 |
| `caict-4iot-dev/uni-registrar-driver-did-bid` | 0 | 0 | 0 → 0 |
| `caict-4iot-dev/uni-resolver-driver-did-bid` | 0 | 0 | 0 → 0 |
| `decentralized-identity/did-resolver` | 0 | 0 | 0 → 0 |
| `decentralized-identity/ion` | 0 | 0 | 0 → 0 |
| `decentralized-identity/sidetree-core` | 0 | 0 | 0 → 0 |
| `decentralized-identity/universal-resolver` | 0 | 0 | 0 → 0 |
| `digitalbazaar/did-io` | 0 | 0 | 0 → 0 |
| `ontio/ontology-did` | 0 | 0 | 0 → 0 |
| `spruceid/didkit` | 0 | 0 | 0 → 0 |
| `spruceid/ssi` | 0 | 0 | 0 → 0 |
| `transmute-industries/sidetree.js` | 0 | 0 | 0 → 0 |
| `uport-project/ethr-did` | 0 | 0 | 0 → 0 |
| `w3c-ccg/did-method-key` | 0 | 0 | 0 → 0 |
| `w3c-ccg/did-test-suite` | 0 | 0 | 0 → 0 |
| `TBD54566975/ssi-sdk` | 0 | 0 | 0 → 0 |
| `cheqd/sdk` | 0 | 0 | 0 → 0 |
| `kiltprotocol/kilt-node` | 0 | 0 | 0 → 0 |
| `iotaledger/identity.rs` | 0 | 0 | 0 → 0 |
| `digitalbazaar/jsonld-signatures` | 0 | 0 | 0 → 0 |
| `digitalbazaar/vc` | 0 | 0 | 0 → 0 |
| `transmute-industries/verifiable-data` | 0 | 0 | 0 → 0 |
| `alastria/alastria-identity` | 0 | 0 | 0 → 0 |
| `energywebfoundation/iam-client-lib` | 0 | 0 | 0 → 0 |
| `openwallet-foundation/acapy-plugins` | 0 | 0 | 0 → 0 |
| `blockchain-lab-um/masca` | 0 | 0 | 0 → 0 |
| `web3id/web3id` | 0 | 0 | 0 → 0 |

变了 11 家，全部是宽规则下多给的分（严规则不会加分）。

结论口径：对外只能说"**在宽规则下最好 3/10、严规则下 3/10**"，不能说"最好就是 2 或 3"。
