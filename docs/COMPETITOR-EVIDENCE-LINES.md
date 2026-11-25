# 竞品表的每一分，指到哪一行（每次 `--run` 重写本页）

审计日 2026-11-26。这张表此前只有计数；本页把计分维度的**原始命中行**贴出来（每维最多 3 条），让你能直接判断那一分是断言还是注释里蹭到的词。

| 仓库 | 得分 | 计分明细 |
|---|---|---|
| `WeBankBlockchain/WeIdentity` | 0/10 | — |
| `caict-4iot-dev/uni-registrar-driver-did-bid` | 0/10 | — |
| `caict-4iot-dev/uni-resolver-driver-did-bid` | 0/10 | — |
| `ceramicnetwork/js-did` | 2/10 | D1, D3 |
| `decentralized-identity/did-jwt` | 3/10 | D1, D3, D4 |
| `decentralized-identity/did-resolver` | 0/10 | — |
| `decentralized-identity/ethr-did-resolver` | 3/10 | D1, D3, D4 |
| `decentralized-identity/ion` | 0/10 | — |
| `decentralized-identity/sidetree-core` | 0/10 | — |
| `decentralized-identity/universal-resolver` | 0/10 | — |
| `decentralized-identity/veramo` | 3/10 | D1, D3, D4 |
| `digitalbazaar/did-io` | 0/10 | — |
| `docknetwork/sdk` | 3/10 | D1, D3, D4 |
| `hyperledger/aries-cloudagent-python` | 3/10 | D1, D3, D4 |
| `hyperledger/aries-framework-go` | 3/10 | D1, D3, D4 |
| `hyperledger/indy-sdk` | 3/10 | D1, D3, D4 |
| `hyperledger/indy-vdr` | 3/10 | D1, D3, D4 |
| `ontio/ontology-did` | 0/10 | — |
| `sphereon-opensource/ssi-sdk` | 3/10 | D1, D3, D4 |
| `spruceid/didkit` | 0/10 | — |
| `spruceid/ssi` | 0/10 | — |
| `transmute-industries/sidetree.js` | 0/10 | — |
| `uport-project/ethr-did` | 0/10 | — |
| `w3c-ccg/did-method-key` | 0/10 | — |
| `w3c-ccg/did-test-suite` | 0/10 | — |

## 逐家证据行

### `ceramicnetwork/js-did` — 2/10（commit `def0a5fed152`）

- **D1**（reject_assertion，测试 文件）
  - `packages/codecs/test/binary.test.ts:22` — `test('throws on invalid encoding', () => {`
  - `packages/did-session/test/lib.test.ts:225` — `await expect(DIDSession.get(account, authMethod, {})).rejects.toThrow(/Required:/)`
  - `packages/did-session/test/lib.test.ts:226` — `await expect(DIDSession.get(account, authMethod, { resources: [] })).rejects.toThrow(`
- **D3**（address_derive，测试 文件）
  - `packages/did-session/test/lib.test.ts:450` — `const address = toString(ed25519.getPublicKey(walletKey.subarray(0, 32)), 'base58btc')`
  - `packages/dids/test/jws-verification-behavior.test.ts:15` — `publicKeyBase58: '2BS946XE3ZGDEsFSq5G3ndodLnAz2TZu1SN1FUw8EwZUC',`
  - `packages/dids/test/jws-verification-behavior.test.ts:21` — `publicKeyBase58: 'HZCZPM7PzCGow5WxopEKeQaKNGQgsZH2d9baiK3FpCYf',`

### `decentralized-identity/did-jwt` — 3/10（commit `63663c1f40b4`）

- **D1**（reject_assertion，测试 文件）
  - `src/__tests__/ConditionalAlgorithm.test.ts:148` — `await expect(verifyJWT(jwt, { resolver })).rejects.toThrow(JWT_ERROR.INVALID_SIGNATURE)`
  - `src/__tests__/ConditionalAlgorithm.test.ts:242` — `await expect(verifyJWT(jwt, { resolver })).rejects.toThrow(JWT_ERROR.INVALID_SIGNATURE)`
  - `src/__tests__/ConditionalAlgorithm.test.ts:410` — `await expect(verifyJWT(jwt, { resolver })).rejects.toThrow(JWT_ERROR.INVALID_SIGNATURE)`
- **D3**（address_derive，测试 文件）
  - `src/__tests__/didkey.test.ts:9` — `publicKeyBase58: 'A12q688RGRdqshXhL9TW8QXQaX9H82ejU9DnqztLaAgy',`
  - `src/__tests__/didkey.test.ts:37` — `publicKeyBase58: '4zvwRjXUKGfvwnParsHAS3HuSVzV5cA4McphgmoCtajS',`
  - `src/__tests__/EdDSASigner.test.ts:1` — `import { base64ToBytes, base58ToBytes, hexToBytes } from '../util.js'`
- **D4**（exit_code_gate，源码 文件）
  - `canary/canary.cjs.cjs:56` — `process.exit(1)`
  - `canary/canary.cjs.cjs:178` — `process.exit(1)`
  - `canary/unpack.mjs:38` — `process.exit(1)`

### `decentralized-identity/ethr-did-resolver` — 3/10（commit `6e0bd4770249`）

- **D1**（reject_assertion，测试 文件）
  - `examples/ethr-7702/test/cross-chain-sync.test.ts:109` — `it('rejects replayed signature (nonce already used)', async () => {`
  - `examples/ethr-7702/test/cross-chain-sync.test.ts:147` — `).rejects.toThrow()`
  - `examples/ethr-7702/test/cross-chain-sync.test.ts:150` — `it('rejects signature with wrong chain ID', async () => {`
- **D3**（address_derive，测试 文件）
  - `examples/ethr-7702/test/batched-updates.test.ts:98` — `// 'ed25519pubkey' → publicKeyMultibase (base58btc of 0xed01 || bytes)`
  - `examples/ethr-7702/test/simple-update.test.ts:55` — `// (base58btc of 0xed01 || bytes). 'base64encodedpubkey' → zFaHNPrHzCnSudUfDV1Vfo1hkkrR4t`
  - `examples/ethr-7702/test/simple-update.test.ts:91` — `// (base58btc of 0xed01 || bytes) per the Multikey spec`
- **D4**（exit_code_gate，源码 文件）
  - `examples/ethr-7702/scripts/compile.ts:52` — `process.exit(1)`
  - `examples/ethr-7702/scripts/compile.ts:58` — `process.exit(1)`
  - `examples/ethr-7702/scripts/diagnose-did.ts:147` — `main().catch((e) => { console.error('FATAL:', e?.shortMessage ?? e); process.exit(1) })`

### `decentralized-identity/veramo` — 3/10（commit `ac953d9a28db`）

- **D1**（reject_assertion，测试 文件）
  - `packages/cli/src/__tests__/objectCreator.test.ts:37` — `).rejects.toThrow(/Error creating .*\['undefined']/)`
  - `packages/cli/src/__tests__/objectCreator.test.ts:91` — `).rejects.toThrow(/Error creating .*does-not-exist\.js\['Foo']/)`
  - `packages/cli/src/__tests__/objectCreator.test.ts:100` — `).rejects.toThrow(/Error creating .*\['doesNotExist']/)`
- **D3**（address_derive，测试 文件）
  - `packages/credential-ld/src/__tests__/golden-compat.test.ts:51` — `const DID_KEY = `did:key:${bytesToMultibase(hexToBytes(ED25519.publicKeyHex), 'base58btc', 'ed25519-pub')}``
  - `packages/credential-ld/src/__tests__/jws-detached-signature.test.ts:10` — `bytesToBase58,`
  - `packages/credential-ld/src/__tests__/jws-detached-signature.test.ts:22` — `const multikey = (prefix: number[], key: Uint8Array) => 'z' + bytesToBase58(concat([prefix, key]))`
- **D4**（exit_code_gate，源码 文件）
  - `packages/cli/src/config.ts:25` — `process.exit(1)`
  - `packages/cli/src/execute.ts:44` — `process.exit(1)`
  - `packages/cli/src/execute.ts:54` — `process.exit(1)`

### `docknetwork/sdk` — 3/10（commit `1eadcdc7a9c1`）

- **D1**（reject_assertion，测试 文件）
  - `packages/ap2/tests/mandates.test.js:188` — `test('rejects a Closed Checkout Mandate with a tampered checkout_hash', async () => {`
  - `packages/ap2/tests/mandates.test.js:225` — `test('rejects a Closed Checkout Mandate closed by an unauthorized key', async () => {`
  - `packages/ap2/tests/mandates.test.js:300` — `test('with userPublicKey, verifies the issuer signature and rejects the wrong key', async () => {`
- **D3**（address_derive，测试 文件）
  - `packages/credential-sdk/tests/base-x.test.js:4` — `encodeAsBase58,`
  - `packages/credential-sdk/tests/base-x.test.js:5` — `decodeFromBase58,`
  - `packages/credential-sdk/tests/base-x.test.js:6` — `encodeAsBase58btc,`
- **D4**（exit_code_gate，源码 文件）
  - `examples/src/blob.js:112` — `process.exit(1);`
  - `examples/src/chain-ops.js:240` — `process.exit(1);`
  - `examples/src/claim-deduction.js:143` — `process.exit(1);`

### `hyperledger/aries-cloudagent-python` — 3/10（commit `daf7ff8d208a`）

- **D1**（reject_assertion，测试 文件）
  - `acapy_agent/admin/tests/test_admin_server.py:152` — `side_effect=jwt.InvalidTokenError("Invalid token")`
  - `acapy_agent/admin/tests/test_admin_server.py:256` — `mock_extract.return_value = {"field": ["Invalid input"]}`
  - `acapy_agent/admin/tests/test_admin_server.py:265` — `validation_error = ValidationError({"field": ["Invalid input"]})`
- **D3**（address_derive，测试 文件）
  - `acapy_agent/anoncreds/default/legacy_indy/tests/test_recover.py:7` — `import base58`
  - `acapy_agent/anoncreds/default/legacy_indy/tests/test_recover.py:206` — `base58,`
  - `acapy_agent/anoncreds/default/legacy_indy/tests/test_registry.py:11` — `from base58 import alphabet`
- **D4**（exit_code_gate，源码 文件）
  - `acapy_agent/commands/start.py:97` — `sys.exit(1)`
  - `acapy_agent/commands/start.py:137` — `sys.exit(1)`
  - `demo/runners/agent_container.py:1475` — `sys.exit(1)`

### `hyperledger/aries-framework-go` — 3/10（commit `64dd8acc0750`）

- **D1**（reject_assertion，测试 文件）
  - `test/aries-js-worker/init.js:47` — `return new Promise((resolve, reject) => {`
  - `test/aries-js-worker/fixtures/data/agent-startup-contexts.json:82` — `"invalid":          "odrl:invalid",`
  - `test/aries-js-worker/test/common.js:21` — `return new Promise((resolve, reject) => {`
- **D3**（address_derive，测试 文件）
  - `test/aries-js-worker/karma.conf.js:34` — `pattern: "node_modules/base-58/Base58.js",`
  - `test/aries-js-worker/test/presentproof/presentproof.js:11` — `import "/base/node_modules/base-58/Base58.js";`
  - `test/aries-js-worker/test/presentproof/presentproof.js:418` — `let methodID = Base58.encode(`
- **D4**（exit_code_gate，源码 文件）
  - `cmd/aries-js-worker/src/worker-impl-node.js:24` — `process.exit(1);`
  - `component/log/internal/modlog/deflog.go:44` — `// Fatalf is CRITICAL log formatted followed by a call to os.Exit(1).`
  - `component/log/internal/modlog/deflog.go:47` — `os.Exit(1)`

### `hyperledger/indy-sdk` — 3/10（commit `2d47f2ff1ca6`）

- **D1**（reject_assertion，测试 文件）
  - `libindy/tests/anoncreds_demos.rs:1791` — `// - provide valid proof for invalid time`
  - `libindy/tests/anoncreds_demos.rs:1792` — `// - provide hacked proof: specify requested timestamp, actually use invalid TS`
  - `libindy/tests/ledger.rs:2527` — `let res = ledger::append_txn_author_agreement_acceptance_to_request("Invalid request string",`
- **D3**（address_derive，测试 文件）
  - `libindy/tests/anoncreds.rs:3823` — `let res = anoncreds::issuer_create_schema(INVALID_BASE58_DID,`
  - `libindy/tests/crypto.rs:23` — `use rust_base58::FromBase58;`
  - `libindy/tests/crypto.rs:29` — `assert_eq!(verkey.from_base58().unwrap().len(), 32);`
- **D4**（exit_code_gate，源码 文件）
  - `vcx/ci/scripts/create_npm_deb.py:15` — `sys.exit(1)`
  - `vcx/ci/scripts/create_npm_deb.py:19` — `sys.exit(1)`
  - `vcx/ci/scripts/create_npm_deb.py:48` — `sys.exit(1)`

### `hyperledger/indy-vdr` — 3/10（commit `e4902fcd5638`）

- **D1**（reject_assertion，测试 文件）
  - `libindy_vdr/tests/attrib.rs:406` — `helpers::check_response_type(&err, "REJECT");`
  - `libindy_vdr/tests/author_agreement.rs:371` — `helpers::check_response_type(&err, "REJECT");`
  - `libindy_vdr/tests/author_agreement.rs:396` — `// Try to send transactions using invalid TAA`
- **D3**（address_derive，测试 文件）
  - `libindy_vdr/tests/utils/crypto.rs:23` — `let verkey = public_key.as_base58().unwrap().to_string();`
  - `libindy_vdr/tests/utils/fixtures.rs:1` — `use bs58;`
  - `libindy_vdr/tests/utils/fixtures.rs:65` — `let did = bs58::encode(rand_arr).into_string();`
- **D4**（exit_code_gate，源码 文件）
  - `wrappers/javascript/indy-vdr-shared/installBinary.js:77` — `process.exit(1)`

### `sphereon-opensource/ssi-sdk` — 3/10（commit `4f8b21c24659`）

- **D1**（reject_assertion，测试 文件）
  - `packages/contact-manager/__tests__/shared/contactManagerAgentLogic.ts:73` — `await expect(agent.cmGetContact({ contactId })).rejects.toThrow(`No party found for id: ${contactId}`)`
  - `packages/contact-manager/__tests__/shared/contactManagerAgentLogic.ts:219` — `await expect(agent.cmUpdateContact({ contact })).rejects.toThrow(`No party found for id: ${contactId}`)`
  - `packages/contact-manager/__tests__/shared/contactManagerAgentLogic.ts:235` — `).rejects.toThrow(`No identity found for id: ${identityId}`)`
- **D3**（address_derive，测试 文件）
  - `packages/credential-vcdm/src/__tests__/message-handler.test.ts:52` — `publicKeyBase58: 'CHWxr7EA5adxzgiYUzq1Gn7zZxVudLR4wM47ioEcSd1F',`
  - `packages/credential-vcdm/src/__tests__/message-handler.test.ts:58` — `publicKeyBase58: 'A92PXJXX1ddJJdj6Av89WYvSWV5KgrhuqNcPMgpvPxj8',`
  - `packages/credential-vcdm-jsonld-provider/src/__tests__/diwala.test.ts:121` — `// publicKeyBase58: 'DYGA3LbwgD66VokM9CQsB3XwrPNzoyX79P19mpPjTp4m',`
- **D4**（exit_code_gate，源码 文件）
  - `packages/agent-config/src/agentCreator.ts:68` — `process.exit(1)`
  - `packages/agent-config/src/agentCreator.ts:77` — `process.exit(1)`
  - `packages/agent-config/src/agentCreator.ts:82` — `process.exit(1)`

## 怎么读

本页只证一件事：**每个 1 分都能指到具体的 test 行**。它不证那一行写得好、也不证它跑过。
如果某一分下面是注释或字符串，你看到的就是原样——请按 `docs/COMPETITOR-EVIDENCE-LINES.md` 的行号回仓核对，并在 Issue 里点名；`--check` 只能保证"有行可指"，判断"这行算不算证据"仍然是人做的事。
