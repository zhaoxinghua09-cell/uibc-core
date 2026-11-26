# 引用可达性实测（每次 `--run` 重写本页）

审计日 2026-11-26，实测于 2026-11-26T15:55:13。**42 条引用：33 条 200；9 条被重定向（仓已改名/迁移），其中 9 条按同一 sha 在新名下复核仍为 200；0 条死。**
本表逐条打的是 `github.com/<repo>/tree/<sha>`：sha 固定只保证内容不变，不保证这条链接今天还能打开。被 301 的条目**不算死，也不算完成**——必须到 `Location` 给出的新名下、用同一个 sha 再打一次，拿 200 才算这条引用仍然可点。
其中 1 条在本机网络里页面打不开（约 20 s 被切断），改用 REST API 的 commit 对象复核：sha 命中才算过，并在表里标 `200 (api)` —— 这证明固定提交存在且公开，不证明页面在你那边能打开。

| 状态 | 耗时 ms | 仓库 | 引用 | 落点 | 新名下同 sha |
|---|---|---|---|---|---|
| 200 (api) | 20011 | `WeBankBlockchain/WeIdentity` | `2f8e4b5a7e20` | — | — |
| 200 | 897 | `caict-4iot-dev/uni-registrar-driver-did-bid` | `68f69ec419c0` | — | — |
| 200 | 898 | `caict-4iot-dev/uni-resolver-driver-did-bid` | `5a933656eb96` | — | — |
| 200 | 1241 | `ceramicnetwork/js-did` | `def0a5fed152` | — | — |
| 200 | 1060 | `decentralized-identity/did-jwt` | `63663c1f40b4` | — | — |
| 200 | 863 | `decentralized-identity/did-resolver` | `005411b26ac3` | — | — |
| 200 | 919 | `decentralized-identity/ethr-did-resolver` | `6e0bd4770249` | — | — |
| 200 | 1121 | `decentralized-identity/ion` | `424ec87dda60` | — | — |
| 301 | 592 | `decentralized-identity/sidetree-core` | `bb4bb16d2383` | https://github.com/decentralized-identity/sidetree/tree/bb4bb16d23838cc02bbde0b4ac634e0491ae85fd | `decentralized-identity/sidetree` 200 |
| 200 | 1140 | `decentralized-identity/universal-resolver` | `99838d52a7a6` | — | — |
| 200 | 990 | `decentralized-identity/veramo` | `ac953d9a28db` | — | — |
| 200 | 1086 | `digitalbazaar/did-io` | `940555f002fb` | — | — |
| 200 | 1069 | `docknetwork/sdk` | `1eadcdc7a9c1` | — | — |
| 301 | 594 | `hyperledger/aries-cloudagent-python` | `daf7ff8d208a` | https://github.com/openwallet-foundation/acapy/tree/daf7ff8d208a56bbfe5f66d879c638b2d2fb4a77 | `openwallet-foundation/acapy` 200 |
| 301 | 605 | `hyperledger/aries-framework-go` | `64dd8acc0750` | https://github.com/hyperledger-aries/aries-framework-go/tree/64dd8acc07506884f480719f7d9d960447d9a5ac | `hyperledger-aries/aries-framework-go` 200 |
| 301 | 636 | `hyperledger/indy-sdk` | `2d47f2ff1ca6` | https://github.com/hyperledger-indy/indy-sdk/tree/2d47f2ff1ca62563f0f85e52cc9378f133ad8a0d | `hyperledger-indy/indy-sdk` 200 |
| 301 | 587 | `hyperledger/indy-vdr` | `e4902fcd5638` | https://github.com/hyperledger-indy/indy-vdr/tree/e4902fcd5638efb0aaded3a854a56e077f8b32f3 | `hyperledger-indy/indy-vdr` 200 |
| 200 | 817 | `ontio/ontology-did` | `9902c8f80f06` | — | — |
| 200 | 988 | `sphereon-opensource/ssi-sdk` | `4f8b21c24659` | — | — |
| 200 | 988 | `spruceid/didkit` | `57a3b45111f8` | — | — |
| 200 | 989 | `spruceid/ssi` | `726f49e7fefb` | — | — |
| 200 | 981 | `transmute-industries/sidetree.js` | `0b17eb9ed7aa` | — | — |
| 200 | 1475 | `uport-project/ethr-did` | `4bbd2ef539ba` | — | — |
| 301 | 618 | `w3c-ccg/did-method-key` | `2cc490c38c5a` | https://github.com/w3c-ccg/did-key-spec/tree/2cc490c38c5aacf58497a87fc0cf8794668bf716 | `w3c-ccg/did-key-spec` 200 |
| 200 | 803 | `w3c-ccg/did-test-suite` | `addafb08c84e` | — | — |
| 200 | 1073 | `TBD54566975/ssi-sdk` | `5ff932dc6d35` | — | — |
| 301 | 601 | `TBD54566975/dwn-sdk-js` | `0e9030144643` | https://github.com/decentralized-identity/dwn-sdk-js/tree/0e903014464388bcfcdcd42da74c40fdd902fd23 | `decentralized-identity/dwn-sdk-js` 200 |
| 200 | 946 | `cheqd/cheqd-node` | `ae52af92966e` | — | — |
| 200 | 931 | `cheqd/sdk` | `72e87f391829` | — | — |
| 200 | 893 | `kiltprotocol/kilt-node` | `2a3bd554a54c` | — | — |
| 301 | 594 | `iotaledger/identity.rs` | `7dd527087b96` | https://github.com/iotaledger/identity/tree/7dd527087b96bf26ea97d486225eff8278c9a89c | `iotaledger/identity` 200 |
| 200 | 947 | `digitalbazaar/jsonld-signatures` | `4bbef4646d91` | — | — |
| 200 | 890 | `digitalbazaar/vc` | `7ddb985a67e4` | — | — |
| 200 | 968 | `transmute-industries/verifiable-data` | `6e77985eb585` | — | — |
| 200 | 1743 | `alastria/alastria-identity` | `edffdfaaa0fb` | — | — |
| 200 | 1017 | `energywebfoundation/iam-client-lib` | `14156ae0b22f` | — | — |
| 301 | 7822 | `hyperledger/aries-framework-javascript` | `06930296a96c` | https://github.com/openwallet-foundation/credo-ts/tree/06930296a96c02519b8c01c0d1822f2a08bde646 | `openwallet-foundation/credo-ts` 200 |
| 200 | 930 | `openwallet-foundation/acapy-plugins` | `8acf77865188` | — | — |
| 200 | 1009 | `blockchain-lab-um/masca` | `fcfb07c9dd09` | — | — |
| 200 | 1044 | `web3id/web3id` | `0f6f7bb0eb25` | — | — |
| 200 | 998 | `walt-id/waltid-identity` | `5bf2ca51be1f` | — | — |
| 200 | 1249 | `zhaoxinghua09-cell/uibc-core` | `fb727c6929ca` | — | — |

复跑：`python tools/refs_check.py --run`（联网）；`--check` 离线比对快照与报告。
