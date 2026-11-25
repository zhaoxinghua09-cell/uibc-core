# 引用可达性实测（每次 `--run` 重写本页）

审计日 2026-11-26，实测于 2026-11-26T04:04:41。**25 条引用：19 条 200，6 条被重定向（仓已改名/迁移），0 条死。**
本表逐条打的是 `github.com/<repo>/tree/<sha>`：sha 固定只保证内容不变，不保证这条链接今天还能打开。

| 状态 | 耗时 ms | 仓库 | 引用 | 落点 |
|---|---|---|---|---|
| 200 | 913 | `WeBankBlockchain/WeIdentity` | `2f8e4b5a7e20` | — |
| 200 | 984 | `caict-4iot-dev/uni-registrar-driver-did-bid` | `68f69ec419c0` | — |
| 200 | 919 | `caict-4iot-dev/uni-resolver-driver-did-bid` | `5a933656eb96` | — |
| 200 | 1008 | `ceramicnetwork/js-did` | `def0a5fed152` | — |
| 200 | 963 | `decentralized-identity/did-jwt` | `63663c1f40b4` | — |
| 200 | 877 | `decentralized-identity/did-resolver` | `005411b26ac3` | — |
| 200 | 932 | `decentralized-identity/ethr-did-resolver` | `6e0bd4770249` | — |
| 200 | 959 | `decentralized-identity/ion` | `424ec87dda60` | — |
| 301 | 553 | `decentralized-identity/sidetree-core` | `bb4bb16d2383` | https://github.com/decentralized-identity/sidetree/tree/bb4bb16d23838cc02bbde0b4ac634e0491ae85fd |
| 200 | 986 | `decentralized-identity/universal-resolver` | `99838d52a7a6` | — |
| 200 | 979 | `decentralized-identity/veramo` | `ac953d9a28db` | — |
| 200 | 1049 | `digitalbazaar/did-io` | `940555f002fb` | — |
| 200 | 936 | `docknetwork/sdk` | `1eadcdc7a9c1` | — |
| 301 | 518 | `hyperledger/aries-cloudagent-python` | `daf7ff8d208a` | https://github.com/openwallet-foundation/acapy/tree/daf7ff8d208a56bbfe5f66d879c638b2d2fb4a77 |
| 301 | 559 | `hyperledger/aries-framework-go` | `64dd8acc0750` | https://github.com/hyperledger-aries/aries-framework-go/tree/64dd8acc07506884f480719f7d9d960447d9a5ac |
| 301 | 549 | `hyperledger/indy-sdk` | `2d47f2ff1ca6` | https://github.com/hyperledger-indy/indy-sdk/tree/2d47f2ff1ca62563f0f85e52cc9378f133ad8a0d |
| 301 | 539 | `hyperledger/indy-vdr` | `e4902fcd5638` | https://github.com/hyperledger-indy/indy-vdr/tree/e4902fcd5638efb0aaded3a854a56e077f8b32f3 |
| 200 | 948 | `ontio/ontology-did` | `9902c8f80f06` | — |
| 200 | 1002 | `sphereon-opensource/ssi-sdk` | `4f8b21c24659` | — |
| 200 | 1008 | `spruceid/didkit` | `57a3b45111f8` | — |
| 200 | 1225 | `spruceid/ssi` | `726f49e7fefb` | — |
| 200 | 1100 | `transmute-industries/sidetree.js` | `0b17eb9ed7aa` | — |
| 200 | 1025 | `uport-project/ethr-did` | `4bbd2ef539ba` | — |
| 301 | 611 | `w3c-ccg/did-method-key` | `2cc490c38c5a` | https://github.com/w3c-ccg/did-key-spec/tree/2cc490c38c5aacf58497a87fc0cf8794668bf716 |
| 200 | 1046 | `w3c-ccg/did-test-suite` | `addafb08c84e` | — |

复跑：`python tools/refs_check.py --run`（联网）；`--check` 离线比对快照与报告。
