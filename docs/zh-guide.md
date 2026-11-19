# 中文导读 · uibc-core

> 这份文件只有一个目的：让第一次打开本仓的中文读者，在五分钟内知道**它是什么、它不承诺什么、它被篡改时到底拦不拦得住**。
> 全仓英文为主，本文是中文补充，不替代 README，也不改变任何对外口径。

---

## 一、一句话

uibc-core 是一个**智能体生命周期证据包**与**复核器**：它把"这个 agent 是谁、做了什么、凭什么被允许做"打成可被别人离线复算的包，并给出三值判定——`PASS` / `FAIL` / `INCONCLUSIVE`。

**`INCONCLUSIVE` 永远不能被洗成 `PASS`。** 这是本仓最硬的一条设计约束。

---

## 二、PASS 到底等于什么（原句照抄，不得改写）

> A uibc PASS means: within the observed evidence boundary, no violation was detected. It does not claim the agent was correct, safe, or wise; that the recorded inputs were true or complete; or that any real-world outcome followed.

中文：**在观测到的证据边界内，没有检出违规。** 它不宣称 agent 是正确的、安全的或明智的；不宣称记录的输入为真或完整；也不宣称现实世界里发生了什么结果。

这句话看着弱，但它是本仓能被外部信任的唯一原因：**别人能核验的只有"有没有检出违规"，核验不了"它是不是个好东西"。**

---

## 三、三律在这份代码里分别落在哪

| 三律 | 本仓对应物 | 位置 |
|---|---|---|
| **有籍**（Registry） | manifest 里的 agent_id / owner / agent_type / version；登记事件写进生命周期链 | `uibc_core/` + `registry/` |
| **有证**（Evidence） | 证据条目的内容哈希 + `evidence_root` + Ed25519 封签（公钥随包走，可 pin） | `uibc_core/signing.py`、`verify.py` |
| **有门禁**（Gates） | 16 组检查（S1–S16 系列）+ 组合校验（K1–K8）；任一不过即 FAIL 或 INCONCLUSIVE | `uibc_core/verify.py` |
| **触点即门** | 每一次"改状态/换钥/回滚"都必须被判一次，不存在"默认放行" | 同上 |

---

## 四、被篡改时到底拦不拦得住（2026-11-19 实跑）

复跑命令（不需要装依赖、不需要账号）：

```bash
python tools/mutation_benchmark.py
```

21 类单点篡改 × 两种验证模式，结果：

| 模式 | 含义 | 假接受率 | 未解释接受 |
|---|---|---|---|
| **open** | 陌生人只拿到包，公钥随包走，无预置信任 | **9.5%（2/21）** | **0/0/0** |
| **pinned** | 依赖方另持公钥，验证时 pin 住 | **4.8%（1/21）** | **0/0/0** |
| **head-pinned** | 专治"整包回滚"，需外部单调锚 | **0%（0/1）** | — |

**"未解释接受 = 0"的意思**：两处被 `PASS` 的篡改，都被检查项明确标为"低置信/需人工确认"，**没有一处是悄悄放过的**。

### 被放过的两类，性质完全不同

| 篡改 | open | pinned | 原因 | 怎么解 |
|---|---|---|---|---|
| **M17 换钥重签（keyswap）** | PASS | FAIL | open 模式公钥随包，密码学上无法区分"新钥"与"合法换钥" | 用 pinned，或与登记簿比对 |
| **M20 整包回滚（旧包冒充新包）** | PASS | PASS | 缺"单调性"——包本身自洽，看不出它比某个新包更旧 | 需外部锚（透明日志 / OTS）；**当前 OTS 仍 `PendingAttestation`，此格尚未覆盖** |

> 换句话说：**这 9.5% 不是漏洞清单，是定义域边界。** 我们主动把它写出来，因为它比"我们全都拦住了"更可信。

---

## 五、复核一次要多久（2026-11-19 实测）

| 指标 | 值 |
|---|---|
| n=160 次 `verify(package_dir)` | p50 **18.2ms** · p95 **27.3ms** · p99 **33.6ms** |
| 环境 | Python 3.13.18 / Windows / 单机单线程 |

**口径必须说清**：这是**整包复核**（全部证据文件哈希 + 生命周期链校验 + Ed25519 验签 + 索引一致性），不是"单次调用判定"。所以**不要**把它和策略引擎的亚毫秒指标直接对比——那不是同一个操作。

---

## 六、五分钟自证（陌生人视角）

```bash
git clone --depth 1 --branch release/v1.1-precheck https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core && python tools/external_node_check.py
```

只有同时满足两件事才会打印 `CONSISTENT`：另一个独立编写的复核器与参考实现结论一致，**且**三个必须被拒的包（无时区时间戳、`1900-02-29`、大写 UUID）确实被拒。

---

## 七、本仓现在还差什么（照实写）

1. **外部复核节点 = 0**：复核的独立性目前依赖同一作者的两份实现，这不是第三方复现的证据。
2. **OTS 外部锚 `PendingAttestation`**：所以 M20 那一格还不能宣称已覆盖。
3. **`gate()` 单次判定尚未单独基准化**：上面只有整包复核的分位数。
4. **版本真源曾出现双仓不一致**：本文件所属版本请以本仓 `CHANGELOG.md` 顶端为准。

---

## 八、延伸阅读

- 理论 SSOT（三律定义与判定顺序）：<https://github.com/zhaoxinghua09-cell/lgd-theory>
- 生态全量索引与中文解读（专栏《凡自治之物》）：**待发布，发布后在此回填链接**
- 国际现场（ITU-T FG-TIDA 身份与信任）：<https://www.itu.int/en/ITU-T/focusgroups/tida/Pages/default.aspx>

*本文 2026-11-19 写；数字来自本机单次运行，如需对外引用请注明"单机单次，可复跑"。*
