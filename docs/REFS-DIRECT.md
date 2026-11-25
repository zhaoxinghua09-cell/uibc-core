# 引用可达性实测（每次 `--run` 重写本页）

审计日 2026-11-26，实测于 2026-11-26T07:21:43。**25 条引用：19 条 200；6 条被重定向（仓已改名/迁移），其中 6 条按同一 sha 在新名下复核仍为 200；0 条死。**
本表逐条打的是 `github.com/<repo>/tree/<sha>`：sha 固定只保证内容不变，不保证这条链接今天还能打开。被 301 的条目**不算死，也不算完成**——必须到 `Location` 给出的新名下、用同一个 sha 再打一次，拿 200 才算这条引用仍然可点。

| 状态 | 耗时 ms | 仓库 | 引用 | 落点 | 新名下同 sha |
|---|---|---|---|---|---|
| 200 | 1007 | `WeBankBlockchain/WeIdentity` | `2f8e4b5a7e20` | — | — |
| 200 | 1110 | `caict-4iot-dev/uni-registrar-driver-did-bid` | `68f69ec419c0` | — | — |
| 200 | 1077 | `caict-4iot-dev/uni-resolver-driver-did-bid` | `5a933656eb96` | — | — |
| 200 | 1177 | `ceramicnetwork/js-did` | `def0a5fed152` | — | — |
| 200 | 1140 | `decentralized-identity/did-jwt` | `63663c1f40b4` | — | — |
| 200 | 1042 | `decentralized-identity/did-resolver` | `005411b26ac3` | — | — |
| 200 | 1479 | `decentralized-identity/ethr-did-resolver` | `6e0bd4770249` | — | — |
| 200 | 1021 | `decentralized-identity/ion` | `424ec87dda60` | — | — |
| 301 | 548 | `decentralized-identity/sidetree-core` | `bb4bb16d2383` | https://github.com/decentralized-identity/sidetree/tree/bb4bb16d23838cc02bbde0b4ac634e0491ae85fd | `decentralized-identity/sidetree` 200 |
| 200 | 939 | `decentralized-identity/universal-resolver` | `99838d52a7a6` | — | — |
| 200 | 985 | `decentralized-identity/veramo` | `ac953d9a28db` | — | — |
| 200 | 1143 | `digitalbazaar/did-io` | `940555f002fb` | — | — |
| 200 | 978 | `docknetwork/sdk` | `1eadcdc7a9c1` | — | — |
| 301 | 562 | `hyperledger/aries-cloudagent-python` | `daf7ff8d208a` | https://github.com/openwallet-foundation/acapy/tree/daf7ff8d208a56bbfe5f66d879c638b2d2fb4a77 | `openwallet-foundation/acapy` 200 |
| 301 | 588 | `hyperledger/aries-framework-go` | `64dd8acc0750` | https://github.com/hyperledger-aries/aries-framework-go/tree/64dd8acc07506884f480719f7d9d960447d9a5ac | `hyperledger-aries/aries-framework-go` 200 |
| 301 | 630 | `hyperledger/indy-sdk` | `2d47f2ff1ca6` | https://github.com/hyperledger-indy/indy-sdk/tree/2d47f2ff1ca62563f0f85e52cc9378f133ad8a0d | `hyperledger-indy/indy-sdk` 200 |
| 301 | 587 | `hyperledger/indy-vdr` | `e4902fcd5638` | https://github.com/hyperledger-indy/indy-vdr/tree/e4902fcd5638efb0aaded3a854a56e077f8b32f3 | `hyperledger-indy/indy-vdr` 200 |
| 200 | 1022 | `ontio/ontology-did` | `9902c8f80f06` | — | — |
| 200 | 1209 | `sphereon-opensource/ssi-sdk` | `4f8b21c24659` | — | — |
| 200 | 1015 | `spruceid/didkit` | `57a3b45111f8` | — | — |
| 200 | 1110 | `spruceid/ssi` | `726f49e7fefb` | — | — |
| 200 | 2024 | `transmute-industries/sidetree.js` | `0b17eb9ed7aa` | — | — |
| 200 | 1036 | `uport-project/ethr-did` | `4bbd2ef539ba` | — | — |
| 301 | 752 | `w3c-ccg/did-method-key` | `2cc490c38c5a` | https://github.com/w3c-ccg/did-key-spec/tree/2cc490c38c5aacf58497a87fc0cf8794668bf716 | `w3c-ccg/did-key-spec` 200 |
| 200 | 1144 | `w3c-ccg/did-test-suite` | `addafb08c84e` | — | — |

复跑：`python tools/refs_check.py --run`（联网）；`--check` 离线比对快照与报告。
