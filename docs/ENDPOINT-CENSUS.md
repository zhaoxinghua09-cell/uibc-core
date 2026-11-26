# 282 条 DID 方法：公开解析端点普查（ENDPOINT-CENSUS）

2026-11-27 · 分母 = W3C《DID Methods》2026-11-17 版全量 282 条 · 只读 GET · 复跑 `python tools/endpoint_census.py`

## 读数

| 档 | 条数 | 含义 |
|---|---|---|
| ENDPOINT_OK | **4** | 规范里给了地址，实测 2xx |
| ENDPOINT_NOT_OK | 14 | 规范里给了地址，实测非 2xx（记状态码） |
| NO_PUBLIC_ENDPOINT_IN_SPEC | **154** | 规范里没有可打地址（相对路径 / SDK / 私有网关） |
| SPEC_UNAVAILABLE | 110 | 规范本身取不到（98 超时 / 11 404 / 1 403） |
| 合计 | 282 | `--check` 断言分母与四档枚举一致 |

四条可打：`did:agentid`（getagentid.dev）、`did:ccp`（did.baidu.com）、`did:opena2a`、`did:oyd`（resolver.ownyourdata.eu）。

## 三条结论

1. **“在册”不证明“有端点”。** 以前这是三条样本的推断，现在是 282 条的读数：能按规范自己打通的只有 4 条。
2. **规范里没有地址，不等于平台没有端点。** `did:cn` 的规范只写相对路径 `/didservice/v1/did/get`，按本普查落在那 154 条里；但它的平台解析接口实测是 200（另一条记录 `docs/PLATFORM-PROBE` 系列）。这两件事必须分开写，否则会把“文档没写”记成“服务没有”。
3. **110 条规范取不到**，其中多数指向已消失的个人仓或私有站点。这不是我们的失败，是登记册的存量状态——引用这些方法时只能说“登记条目存在”，不能说“规范可读”。

## 方法

- 取每条登记项的 `specification` 链接（`github.com/.../blob/` 自动换成 `raw.githubusercontent.com`）。
- 在正文里按四种“可打形状”找候选：`/1.0/identifiers/`、`/resolve/`、`didservice|did/resolve|resolve-verify`、`/api/..resolve|did`。
- 每条最多 3 个候选，首个 2xx 即止；并发 8，单请求 6s，取规范两次尝试。
- **不对主机设黑名单**：第一版加了黑名单，把偶发超时放大成 146 条假的 SPEC_UNAVAILABLE，已废弃并在文件头写明原因。

## 自限

- 单次运行读数；110 条里的超时项换个时段可能转为可读，复跑请重跑 `--run` 而非只跑 `--check`。
- 只覆盖“规范里写出来的地址”，不覆盖只存在于 SDK 默认配置或厂商文档中的端点。
- 未推送远端：本文件与 `tools/endpoint_census.py` 只在本地 `D:\ci-repro3`，未 commit、未开 PR（对外动作需 owner 明确允许）。
