# 外人审计：一条命令，两类案子

`python3 tools/outsider_audit.py`

零依赖，不需凭据，默认不联网。`docs/OUTSIDER-RUN.md` 是邀请函，这个工具是邀请函能被兑现的方式——**文档可以请求，只有命令能执行**。

---

## 它做三件事，且拒绝把三件事混为一谈

### 1. 基线：出厂包必须给出文档声称的那个判定

`fixtures/clean.uibc` 未签名，因此判定必须是 **INCONCLUSIVE / unattested**。

如果这里报 PASS，等于宣布"没有签名也算签了"——那是最难撤回的错误，所以它是一条断言，不是一句说明。

### 2. 红队：11 条篡改 + 2 条反假阳性对照

| 篡改 | 期望 | 实测 | 被谁抓住 |
|---|---|---|---|
| 改证据文件 1 个字节 | FAIL | FAIL | S4 |
| 截断证据文件一半 | FAIL | FAIL | S4 |
| 删除证据文件 | FAIL | FAIL | S4 |
| 改 manifest 里的 evidence_root | FAIL | FAIL | S5 |
| 在包根加一个未声明文件 | FAIL | FAIL | S1 |
| 制造重复 JSON 成员名 | FAIL | FAIL | **S11（解析之前）** |
| 写一个不存在的日期（2 月 30 日） | FAIL | FAIL | S12、S3 |
| 改 identity 的 agent_id | FAIL | FAIL | S2 |
| 删掉尾部一条证据（截断） | FAIL | FAIL | S5 |
| 注销一条 index 但留下文件 | FAIL | FAIL | S5 |
| 篡改封签 | 不得为 PASS | FAIL | S6 |

**对照（这些不能当成伪造）**

| 操作 | 期望 | 实测 |
|---|---|---|
| 重排 index 顺序 | 与基线相同 | INCONCLUSIVE ✔ |
| 原样复制 | 与基线相同 | INCONCLUSIVE ✔ |

重排那条是这套审计里最有信息量的一格：**Evidence Root 覆盖的是排序后的内容哈希，不是文件顺序**，所以重排改了字节、没改承诺。一个把重排判成伪造的验证器，会在真实使用中不断制造假警报。只测"能不能抓"的红队是不完整的，必须同时测"不该抓的有没有乱抓"。

### 3. 互操作：有语料才跑，跳过不算通过

`--kit <path>` 时才跑 AER-1 四件事：出站 → 对方 runner 判、一条命令自证、入站 valid 期望 ACCEPTED、入站 invalid 期望 REJECTED。无语料时状态是 **SKIPPED**，且 `ok = null`——**跳过永远不计入通过**。

带语料实跑结果（`/tmp/aer1_kit`，143 向量）：

```
interop    : all pass
  emit -> publisher runner               exit=0 ok
  one-command interop demo               exit=0 ok
  inbound valid (expect ACCEPTED)        exit=0 ok
  inbound invalid (expect REJECTED)      exit=0 ok
```

## 退出码是诚实的

`0` 只在"基线对 + 11 条全抓 + 2 条不误抓"时给出。任何一条篡改没被抓、任何一条对照被误判、或某条变异根本没应用成功，都是 `1`。

## 这套工具自己的第一个 bug 值得留着

第一次跑，13 条里有 3 条显示"变异未应用"。原因不是验证器弱，是**我写脚本时假设 index.json 是 `{"entries": [...]}`，而出厂 fixture 里它是裸数组**。三条变异在动手之前就抛异常了。

如果那个 harness 把"异常"当成"已处理"，它会输出一片绿灯，而实际上什么都没发生——**这正是它要抓的那种失败，出现在自己身上**。

现在的实现要求：变异抛异常 = 该条判 FAILED，并写明 `mutation_error`。测试里 `test_every_attack_is_caught` 明写"变异没应用不能证明任何事"。

## 已知边界

- ~~只覆盖一种包形状~~ → **已补第二阶段（v11）**：先构造一棵正确的 Merkle 树和一条正确的收据链（构造不通过就直接报错，避免"攻击一个本来就坏的包"），再逐条打：改 root、虚报 size、改一个 inclusion proof、换 proof 索引、改首条收据正文、伪造 genesis 前驱。**6 条全部被抓，S13 抓 4 条、S17 抓 2 条。**
- **仍未覆盖**：S14（严格 base64）、S15（锚事件解析）、S16（外部时间戳 RFC 3161）、S18（策略文件解析）在 `fixtures/` 上没有对应文件，因此仍未刻意攻击。
- **一个如实列出的已知缺口**：改**最后一条**收据的正文，包里没有任何东西能发现——它没有后继，没有谁的 `previousReceiptHash` 覆盖它。工具把它列为 `known_gaps`（`not caught`），不计入抓到的条数；只能靠对链头做外部锚定（S15/S16）才可能发现。
- 红队是**规则型**，不是模糊测试；它不产生随机变异，因此不能声称"抗模糊测试"。
- 不带 `--kit` 时不触网，也不下载语料。

## 复跑

```bash
python3 tools/outsider_audit.py                      # 基线 + 红队
python3 tools/outsider_audit.py --kit /tmp/aer1_kit  # 再加互操作
python3 tools/outsider_audit.py --json               # 机器可读
python3 -m unittest tests.test_outsider_audit -v     # 6 项，0.12 s
```
