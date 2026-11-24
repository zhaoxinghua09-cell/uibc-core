# 身份适配器：一个接口，两种诚实

2026-11-24。对应战略 P1-1。代码：`uibc_core/identity_adapter.py`；测试：`tests/test_identity_adapter.py`（10 条）。

“身份无关”这句话，没有接口就只是一句口号。这一层给的是接口，以及两家实现——**每家只说自己有资格说的那句话**。

## 接口允许说的五种话

| 状态 | 含义 | 谁能给 |
|---|---|---|
| `VERIFIED` | 这个标识控制这把钥匙，按这份文档；文档摘要已钉进 evidence | `did:key`（离线自描述） |
| `INCONCLUSIVE` | 绑定的形状读得出来，但周边信任没评估（没建链、没验锚） | `pkix` 证书解析——**止步于此** |
| `INVALID` | 标识不符合它自己那套语法的文法 | 两种都会 |
| `UNSUPPORTED` | 这套方案我不做，或依赖不在 | `did:wba` 等未接方法；缺 `cryptography` |
| `UNRESOLVED` | 方案支持、标识合法，但拿不到文档（无端点、网络断） | `did:cn` 没给端点 |

**没有任何适配器可以返回 `REVOKED` 或 `EXPIRED`。** 解析一个标识不是对主体“随时间变化的处境”的陈述——那属于验证路径，不属于身份路径。这条由测试钉住（`test_no_adapter_may_speak_about_standing_over_time`）。

## 这一层抓到的真 bug

写测试时发现：`did:cn` 在**没给端点**时抛的是 `RegistryEndpointRequired`，它是 `DIDError` 的子类，于是适配器最初把它归进 `INVALID`——“标识写法不合法”。

这是**我们自己身上的一次信息坍缩**：一个完全合法、只是没有端点可取的标识，被说成“你的标识是错的”。修法是把 `RegistryEndpointRequired` 单独拦出来归 `UNRESOLVED`（`uibc_core/identity_adapter.py` 里那段带注释的 `except`）。

值得记下的是：**这正是七态存在的理由**，出现在写它的人自己身上。凡是接口边界的映射，都值得逐格检查一遍。

## 证书为什么停在 `INCONCLUSIVE`

`pkix` 适配器只做解析：把 PEM 读成证书，取 SPKI 的 sha256，返回 `INCONCLUSIVE` 并写明“no chain built, no trust anchor evaluated, no revocation fetched”。

为什么不给 `VERIFIED`：解析成功只能说明“这段字节是一张证书”，不能说明“这张证书被谁背书、现在是否还有效”。把前者说成后者，就是我们在别人身上批评的那件事。建链与验锚是 P1 的下一步，不是这一层偷着做。

## 现在能干什么

```
python -c "from uibc_core import identity_adapter as ia; print(ia.check('did:key:z6MkpTHR8VNsBxYAAWHut2Geadd9jSwuBV8xRoAnwWsdvktH'))"
```

带 `endpoint` 时，`did:cn` / `did:ioa` 等注册中心方法走同一条路径；没有端点就老实报 `UNRESOLVED`。证书：`ia.check(pem_text)`。

## 边界

- 只做了两种：DID（8 方法）与 X.509 只读。VC、SD-JWT、DNS、企业目录仍是 0 个适配器（见 `docs/IDENTITY-MAPPING.md` 的六个数字）。
- 没有建链、没有撤销获取、没有新鲜度——这三件在验证路径里，不在这一层。
- 适配器的 `VERIFIED` 只是“身份绑定”层面的，不构成对该主体行为可信的判断。混用会被 `claims-register` 的规矩挡住。
