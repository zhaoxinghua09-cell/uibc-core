# 判定词表能说什么：一次可复算的测量

2026-11-24。对应"我们凭什么说自己有优势"里最常被质疑的一条：**七个状态是不是过度设计。**

不辩论，只测。输入是七态，目标是另外两种已公开的形状各自能承载多少区分。命令：

```
python3 tools/state_collapse.py          # 打印下表 + receipt sha256
python3 tools/state_collapse.py --json   # 机器可读
```

## 三个模型怎么映射

| 状态 | `boolean`（AuthZEN 1.0 的 `decision: true/false`） | `ladder`（KYA-OS Core L1–L3，缺件即下调） | `seven` |
|---|---|---|---|
| VERIFIED | permit | L3 | VERIFIED |
| INVALID | deny | L1 | INVALID |
| REVOKED | deny | L1 | REVOKED |
| EXPIRED | deny | L1 | EXPIRED |
| INCONCLUSIVE | deny | L2 | INCONCLUSIVE |
| UNSUPPORTED | deny | L1 | UNSUPPORTED |
| UNRESOLVED | deny | L2 | UNRESOLVED |

## 测出来的三行

| 模型 | 不同输出 | 21 对里能区分 | 4 对"必须区分"里保住 |
|---|---|---|---|
| boolean | 2 | 6/21 | **0/4** |
| ladder | 3 | 14/21 | 2/4 |
| seven | 7 | 21/21 | **4/4** |

被合并掉的四对（每一对都对应不同的下一步动作）：

| 对 | boolean | ladder | 为什么必须区分 |
|---|---|---|---|
| UNSUPPORTED = REVOKED | 合并 | 合并 | "我们不认识你的方法" vs "你的凭证被撤了"。前者应引导去换方法，后者应停止信任。合成一个 `deny`，接收方会做错其中一件 |
| INCONCLUSIVE = REVOKED | 合并 | 分开 | "我们判不了" vs "你被撤了"。前者要补证据，后者要通报 |
| UNRESOLVED = UNSUPPORTED | 合并 | 分开 | "连不上" vs "不会做"。前者可重试，后者重试一万次也没用 |
| EXPIRED = INVALID | 合并 | 合并 | "过期了" vs "被伪造"。前者是流程问题，后者是安全事件 |

## 这份测量能证明什么、不能证明什么

**能**：在给定映射下，布尔形状把六种不同的失败压成一个 `deny`，四种"下一步动作不同"的对全部丢失；阶梯形状保住一半；七态全保。这是算术，`receipt_sha256` 可被任何人重算。

**不能**：

- **不是对 AuthZEN 或 KYA-OS 的指控。** 映射是我们对**公开文档**的读法，不是它们的系统；也没有主张它们"不能"增加状态——AuthZEN 的 profile 完全可以另加字段。这里量的是**今天这份形状承载的信息量**。
- **不是"信息越多越好"。** 七态也要求接收方明白七个词各自该触发什么动作；一个不知道自己该拿 `UNSUPPORTED` 干什么的实现，收益是零。词表的价值取决于**接收方是否据此分流**，这也是 P1「信任状态机」要补的转移表。
- **不解决采纳问题。** 词表再细，外部实现仍是 0；对面最接近的同侪有 13 个第三方实现（`COMPETITOR-FACTS.json`，2026-11-18）。

## 一句话

**优势不在"我们有七个状态"，而在"我们能在测量里显示：少两个状态，就有四种必须区分的失败被合并成一种。** 这句话可以被任何人用一条命令复算，也可以被任何人用一条命令反驳——只要能构造出反例。
