# 真装真跑：两家竞品的测试套件跑出了什么（每次重写本页）

审计日 2026-11-26。主机 Windows 11, node v22.23.2, npm 10.9.8, pnpm 9.15.9。

**这不是加分项，也不是减分项。** 把竞品仓按同一批固定 commit 真装真跑一遍，只记录它们自己的测试套件跑出了什么；不改竞品表任何分数，也不把'它的测试能跑'读成'它更差'。

| 仓库 | 固定 commit | 用例 | 过 | 红 | 跳过 | 耗时 s | 退出码 |
|---|---|---|---|---|---|---|---|
| `decentralized-identity/did-jwt` | `63663c1f40b4` | 506 | 506 | 0 | 0 | 4.22 | 0 |
| `decentralized-identity/ethr-did-resolver` | `6e0bd4770249` | 182 | 178 | 1 | 3 | 19.51 | 1 |
| `decentralized-identity/did-resolver` | `005411b26ac3` | 25 | 25 | 0 | 0 | 3.25 | 0 |
| `uport-project/ethr-did` | `4bbd2ef539ba` | 38 | 37 | 1 | 0 | 92.10 | 1 |
| `digitalbazaar/did-io` | `940555f002fb` | 26 | 26 | 0 | 0 | 3.00 | 0 |
| `digitalbazaar/jsonld-signatures` | `4bbef4646d91` | 1 | 1 | 0 | 0 | 3.00 | 0 |
| `digitalbazaar/vc` | `7ddb985a67e4` | 119 | 119 | 0 | 0 | 17.00 | 0 |

## `decentralized-identity/did-jwt`

- 安装：npm install 失败（npm 读 pnpm workspace 时 `Cannot read properties of null (reading 'edgesOut')`）；改用 `pnpm install --ignore-workspace`，9.8s 完成。仓库自带的 pnpm-workspace.yaml 只有 allowBuilds 键，pnpm 9 要求 `packages` 字段，本地补了 `- .` 才能 `pnpm run`。
- 套件：`pnpm test → vitest run` → 16 文件 / 506 用例 / 0 红 / 0 跳过 / 4.22 s / exit 0
- 额外探针：pnpm run canary（他们的 ESM / CJS / tsc --noEmit 三层一次性探测） → exit 1。脚本自身的 Windows 路径缺陷：`canary/unpack.mjs:24` 用 `new URL(import.meta.url).pathname` 取路径，在 Windows 上得到 `/D:/...`，`resolve(HERE, '..')` 变成 `D:\D:\realrun\did-jwt`，在跑任何检查之前就 ENOENT。 读法：这条不代表它那三层一致性不存在，只代表该脚本是 POSIX-only；因此不作为任何关于 D4 能力的证据。
- 结论：它的测试套件是绿的：506 条全过。但那是 JWT 签名/校验的套件，不是'一条报文的每一位翻一遍'——绿不等于本表的 D2。

## `decentralized-identity/ethr-did-resolver`

- 安装：`pnpm install --no-frozen-lockfile` 24.7s 完成（workspace 里 3 个包）。
- 套件：`pnpm -r test` → 19 文件 / 182 用例 / 1 红 / 3 跳过 / 19.51 s / exit 1
- 按原样跑不动的部分：仓库里的 `test` 脚本写成 `HARDHAT_CONFIG=hardhat.config.mts vitest run`（POSIX 环境变量前缀），Windows 直接报 `'HARDHAT_CONFIG' is not recognized`——这是 shell 语法问题，不是测试失败。设 `$env:HARDHAT_CONFIG` 后重跑，才是下面这份结果。
- 红的那条：`src/__tests__/networks.integration.test.ts > ethrResolver (alt-chains) > eth-networks > resolves on mainnet with versionId` —— AssertionError: 与主网实时链状态深比较不一致 读法：该用例断言的是实时 mainnet 上的解析结果；链上状态随时间变化，所以它现在红。不是代码缺陷，也不是本表任何一维的证据。
- 结论：182 条里 178 绿、1 红（网络/链状态相关）、3 跳过；exit 1 来自那条实时链断言。

## `decentralized-identity/did-resolver`

- 安装：pnpm install --ignore-scripts --no-frozen-lockfile 22.5s 完成；唯一告警是 unmet peer @typescript/native（仓库钉的是 typescript 7.0.2，peer 要 >=7.1.0-dev），不影响测试。npm 路线在这类 pnpm 仓上会先撞 Cannot read properties of null (reading edgesOut)，没用。
- 套件：`pnpm test → vitest run` → 1 文件 / 25 用例 / 0 红 / 0 跳过 / 3.25 s / exit 0
- 结论：25 条全过、1 个测试文件、644 行测试、57 处 expect、2 处 rejects。命中本表六个变异维度全是 0（bit_level / fuzz / mutation_testing / property_based / address_derive / exit_code_gate），只有 3 处 reject_assertion —— 断言集中在解析结果的结构和拒绝路径上，没有一条把报文的位或地址从头推一遍。绿不等于本表任何一维。

## `uport-project/ethr-did`

- 安装：pnpm 拒绝（仓内 packageManager 指向 yarn，报 'This project is configured to use yarn'）；改用 npm install --legacy-peer-deps --ignore-scripts，2 分 0 秒装完 1334 个包。
- 套件：`jest --ci（仓内 test 脚本是 cross-env NODE_OPTIONS=--experimental-vm-modules jest）` → 3 文件 / 38 用例 / 1 红 / 0 跳过 / 92.10 s / exit 1
- 结论：38 条里 37 绿、1 红：src/__tests__/index.test.ts:187 的 'expire automatically > resolves document' 先 sleep(5) 卡过期窗口，再对解析结果做深比较——这是对时间的断言，本机上窗口没卡准就红。属测试自身对时钟敏感，不是代码缺陷，也不作为本表任何一维的证据。整套 92 秒，主要花在一条真实 RPC 链路上。

## `digitalbazaar/did-io`

- 安装：`npm install --ignore-scripts --no-audit --no-fund` 403 packages, 19s。无 workspace，无 lockfile 冲突。
- 套件：``mocha --preserve-symlinks -t 30000 test/**/*.spec.js`（package.json 的 test-node 脚本，去掉 cross-env 与 reporter 变量）` → 1 文件 / 26 用例 / 0 红 / 0 跳过 / 3.00 s / exit 0
- 额外探针：它自己的 `test` 脚本（经 cross-env 与 ${REPORTER:-spec} 展开） → exit 0。在 POSIX shell 下可用；本机 PowerShell 里 `${REPORTER:-spec}` 不会被展开，所以直接调 mocha 跑同一批 spec。 读法：同一批用例，换入口跑出来的数一样（26/26）。
- 结论：26 条全过，绿得干净。但这是个 DID 文档缓存/驱动层，测的是缓存与 driver 派发，不含任何逐位变异或跨实现比对——绿与本表 D2 无关。

## `digitalbazaar/jsonld-signatures`

- 安装：`npm install --ignore-scripts --no-audit --no-fund` 461 packages, 19s。
- 套件：``mocha --preserve-symlinks -t 10000 test/*.spec.js`（官方 test-node 的 glob，去掉 cross-env）` → 1 文件 / 1 用例 / 0 红 / 0 跳过 / 3.00 s / exit 0
- 额外探针：套件本身的体量 → exit 0。test/jsonld-signatures.spec.js 共 525 字节，只有一条 `it('should exist')`；文件头注释自认："The existing test suite has been extracted to each individual signature suite's repository. Test coverage of this package currently depends on indirect testing through other test suites." 读法：这是全表里最干净的反例：**exit 0、100% 通过、但一条断言都没测行为**。它证明'绿的套件'与'可复算的证据'是两件事，也证明我们不许用跑通来改分是对的。
- 结论：1/1 通过，但那条用例只断言模块能被 require。仓库自己声明覆盖率依赖别的仓，因此这个绿什么也不说明。

## `digitalbazaar/vc`

- 安装：`npm install --ignore-scripts --no-audit --no-fund` 505 packages, 20s。
- 套件：``mocha --preserve-symlinks -t 10000 test/*.spec.js`（官方 test-node 的 glob，去掉 cross-env）` → 1 文件 / 119 用例 / 0 红 / 0 跳过 / 17.00 s / exit 0
- 额外探针：签发/验签往返是否真在测 → exit 0。119 条里含 Ed25519 签发→验签、篡改后拒绝、过期凭证拒绝等用例，是真在跑密码学往返，不只是 smoke。 读法：这是本表目前最扎实的一家：它测的是凭证签发与校验的行为。但仍不等于 D2——它没有'把一条报文每一位翻一遍并断言形状'。
- 结论：119/119 全过，含真实签发/验签与篡改拒绝，是本表里最接近'行为级证据'的一家；但它仍不含逐位变异，所以门禁表不动。

## 为什么这些数字不进表

本表量的是'仓内有没有外人可复算的变异证据'；'它的测试套件能跑' 与这一维无关，所以无论绿红都不许改分。

改分条数：**0**。

复跑：`python tools/parity_realrun.py --check`（离线比对记录与快照）。真跑本身是可复现的人工步骤，命令与踩到的坑都写在记录里，不假装是一条命令能复现的流水线。
