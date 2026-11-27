# 五方护照对照：实测表

生成时间：2026-11-27T03:36:27+00:00　·　JSON sha256[:16] `e329d6d9f841fe39`

**这张表此前没有人做过。** 原因是五套规范里只有一家提供可安装的第三方实现。

## 一、总表

| 体系 | C1 | C2 | C3 | C4 | C5 | C6 |
|---|---|---|---|---|---|---|
| APS（IETF） | ● | ● | ● | ◐ | ● | ● |
| AIAgentMark | ● | ● | ● | ◐ | ○ | ✕ |
| APIS v2.1 | ○ | ◐ | ◐ | ○ | ◐ | ✕ |
| AIP·singla | ○ | ◐ | ◐ | ○ | ◐ | ✕ |
| AIP·prakash | ○ | ◐ | ● | ◐ | ○ | ✕ |

合计 **9 ● / 10 ◐ / 7 ○ / 4 ✕**，共 30 项判读。

**图例**：● 实测通过　◐ 依规范可判、未能实测　○ 规范内无解析入口 / 不可判定　✕ 缺该功能

## 二、六项检查是什么意思

- **C1 签名可离线验**：拿凭证 + 签发公钥，不联网能否验通。
- **C2 内容绑定**：改一个字段，验签是否必然失败。
- **C3 规范化确定**：键序打乱后规范串是否一致（JCS 是否写死）。
- **C4 标识可解析**：只给标识串，无上下文能否解析出文档。
- **C5 吊销可追**：吊销是否是一条第三方可验的证据，而非后台数据库里的记录。
- **C6 第三方可跑**：有没有别人能装、能跑的东西（有实现≠有测试，但没实现一定没第三方测试）。

## 三、逐条判读

| 体系 | 检查 | 判读 | 依据 |
|---|---|---|---|
| APS（IETF） | 签名可验（离线，第三方持公钥） | ● | verify_passport(allow_self_signed=True) -> valid=True, self_signed_accepted=True |
| APS（IETF） | 内容绑定（改一个字段验签必失败） | ● | 篡改 mission 后 verify -> valid=False（应为 False） |
| APS（IETF） | 规范化确定（换键序规范串不变） | ● | JCS 换键序 -> 同串（e69bb60d894e5e34） |
| APS（IETF） | 标识可解析（无上下文） | ◐ | 护照自带 verification_method + keyPair；agent_id 本身不是可解析标识，解析靠随护照携带的文档，不需网络 —— 与 DID 的"可解析"不是同一含义 |
| APS（IETF） | 吊销可追（吊销=一条可验证据） | ● | 撤销记录离线可验：canonical 后 Ed25519 验签 True；改 reason 后 False；换 revokedBy 后 False。draft 路径 issue_authority_revocation / verify_authority_revocation / verify_authority_revocation_signature 三个符号均在场（3/3）。边界：委派工件本身不携带吊销态，拿不到该记录者仍判 valid=True，判定需外部源 |
| APS（IETF） | 第三方可独立跑（有可安装实现） | ● | pip install agent-passport-system 4.3.0 与 npm i agent-passport-system 8.1.1 均成功；跨实现字节对照 8/8 一致（含 333333333.33333329、1e30、-0.0、1e-27、30 位整数、UTF-16 键序）；Python 现造自签护照由 TS 独立进程 verifyPassport 验通 valid=true，篡改后 TS 转 Invalid signature —— 厂商自测之外的第一条第三方证据 |
| AIAgentMark | 签名可验（离线，第三方持公钥） | ● | 按白皮书三条 conformance 条款（Ed25519 + RFC8785 JCS + 规范字段）复现一份，自建验签器验通 |
| AIAgentMark | 内容绑定（改一个字段验签必失败） | ● | 给 capabilities 追加一项后验签必失败（内容绑定成立） |
| AIAgentMark | 规范化确定（换键序规范串不变） | ● | 白皮书明确 RFC 8785 JCS；换键序串不变（与 APS 同一实现验证） |
| AIAgentMark | 标识可解析（无上下文） | ◐ | 白皮书明言"不注册、无服务器、无中间商"——标识不可在线解析，靠持 owner 公钥离线验 |
| AIAgentMark | 吊销可追（吊销=一条可验证据） | ○ | 白皮书 v1.0 未给吊销机制（到期 + 换钥是唯一手段） |
| AIAgentMark | 第三方可独立跑（有可安装实现） | ✕ | 无公开实现、无 SDK、无样例凭证 —— 第三方无法独立跑，只能按白皮书复现 |
| APIS v2.1 | 签名可验（离线，第三方持公钥） | ○ | 未获发任何 APIS 凭证；一致性基线未公开下载，无法取得样例 |
| APIS v2.1 | 内容绑定（改一个字段验签必失败） | ◐ | 规范要求 issuer/principal/delegate 三签与链式托管；未获样例，判规范可设不可验 |
| APIS v2.1 | 规范化确定（换键序规范串不变） | ◐ | 规范未统一指定 canonicalization（与 APS/AIAgentMark 不同），跨实现有风险 |
| APIS v2.1 | 标识可解析（无上下文） | ○ | realm-scoped DID（did:passport:[realm]:[uuid]）；未公开解析入口，试探 example.com → HTTP 404 |
| APIS v2.1 | 吊销可追（吊销=一条可验证据） | ◐ | 规范定义即时吊销与 issuer 登记镜像；无公开实例可测 |
| APIS v2.1 | 第三方可独立跑（有可安装实现） | ✕ | 一致性测试"初始基线"由联盟自发布，未见第三方复核；无公开实现 |
| AIP·singla | 签名可验（离线，第三方持公钥） | ○ | 无公开实现、无样例凭证 |
| AIP·singla | 内容绑定（改一个字段验签必失败） | ◐ | 规范定义了 token/capability 结构与确定性校验；未获样例 |
| AIP·singla | 规范化确定（换键序规范串不变） | ◐ | 规范要求 canonical JSON（引用自身规则），未统一到 RFC 8785 |
| AIP·singla | 标识可解析（无上下文） | ○ | did:aip 明确"单独一个 did 串不编码其 Registry，解析需要 Registry 上下文"——本探针未获 Registry 地址；同目录下 did:cn 平台列表 HTTP 200（不同方法，仅作对照） |
| AIP·singla | 吊销可追（吊销=一条可验证据） | ◐ | AID 不可变、一次性；吊销走 Registry，无公开实例可测 |
| AIP·singla | 第三方可独立跑（有可安装实现） | ✕ | 两份 draft 均无测试数字、无实现 |
| AIP·prakash | 签名可验（离线，第三方持公钥） | ○ | 无公开实现、无样例凭证 |
| AIP·prakash | 内容绑定（改一个字段验签必失败） | ◐ | 身份文档自签、Ed25519 + JCS（规范明确 RFC 8785）——与 APS/AIAgentMark 同法 |
| AIP·prakash | 规范化确定（换键序规范串不变） | ● | 规范明确 RFC 8785 JCS（唯一一处与 APS 完全对齐的地方） |
| AIP·prakash | 标识可解析（无上下文） | ◐ | 机制确定：GET https://<domain>/.well-known/aip/<path>.json；无公开实例，example.com 试探 → HTTP 404 |
| AIP·prakash | 吊销可追（吊销=一条可验证据） | ○ | 吊销只在令牌过期层面；无证书吊销语义 |
| AIP·prakash | 第三方可独立跑（有可安装实现） | ✕ | 无公开实现、无测试数字 |

## 四、自限（不藏）

1. 30 项里只有 9 项是实测，其余因对象无公开实现而无法实测；
2. 只做 `example.com` 的 `.well-known` 试探，未扫任何私有端点；
3. AIAgentMark 的 ● 为本仓库按白皮书 conformance 条款复现，非厂商实现，字段命名可能有细微出入；
4. 未复核厂商自述的测试数字（APS 1,634 例、APIS 初始基线），只记“自发布”。

复跑：`python tools/passport_matrix.py --check`（离线）　`--run`（联网重读，需 `pip install agent-passport-system`）

环境：Python 3.13.18 / agent-passport-system 4.3.0 / cryptography 50.0.2
