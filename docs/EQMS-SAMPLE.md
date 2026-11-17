# eQMS 交接样例：他们的变更记录 → 我们的裁决

> 示范一件很小、但决定定位的事：QMS 已经记了，我们只补"第三方能离线复算"那一步。
>
> **重要前提**：字段命名参考 Cloudtheapp / Modern Requirements 的公开文档，**不是官方集成**，也**没有在真实租户里验证过**。这是一份 shape-level 样例，用来说明接缝在哪。

## 文件

| 文件 | 内容 |
|---|---|
| `docs/samples/eqms-sample-1.json` | 两次变更（1.0.0 → 1.1.0），QMS 风格字段 |
| `docs/samples/eqms-verdict-1.json` | 裁决（`PASS records=2 origins=2 codes=-`） |
| `tools/eqms_sample.py` | 生成上面两个文件的脚本，可重跑 |

## 字段对照（我们的样例 ↔ QMS 常见字段）

| QMS 常见字段 | 我们样例里的位置 | 说明 |
|---|---|---|
| change_id / CC 编号 | `payload.change_id` | 直接透传，不改名 |
| modification category | `payload.modification_category` | PCCP 变更类别，直接透传 |
| validation dataset reference | `payload.validation_dataset_ref` | 只存引用，不存数据（避免把数据集搬进来） |
| performance data | `payload.performance_data` | 结构化小对象；大表给哈希 |
| impact assessment | `payload.impact_assessment` | 文本或 ID，建议 ID + 哈希 |
| approver / approved_at | `payload.approved_by` / `approved_at` | 电子签名另议，这里只做引用 |
| 版本 | `payload.device_version` | 用于跨版本引用（`refs` 指向上一版摘要） |

## 裁决里最该被读到的一行

`not_claimed` 字段里固定写了四条，其中两条是给别人挑毛病的：

- 导出后现算的摘要，**无法证明导出前没被改过**；
- 我们**不判断变更是否在已授权 PCCP 范围内**（那是合规判断，不是我们的活）。

## 与三家 PCCP 产品的差别（一句话版）

他们：变更 → 平台判断 → 平台展示结论。
我们：变更 → 记录外流 → **任何人都能重算同一个结论**，包括不装我们软件的人。

差别不在功能多少，在**结论归谁**。
