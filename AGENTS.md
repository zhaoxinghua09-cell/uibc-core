---
name: uibc-core
description: LGD 全程治理论可执行协议层参考实现（registry / evidence / gates，Apache-2.0）。向在本仓工作的 agent 提供操作手册：命令、结构、测试与边界。
---

# AGENTS.md — uibc-core 仓操作手册（六区域版 · G-10 / AAIF 对齐）

> 结构按 GitHub 官方 2500 仓研究六核心区域 + AAIF（agents.md 规范）编写。
> 本仓主题：**有籍 · 有证 · 有门禁** —— Registry（身份注册）/ Evidence（内容哈希证据+封签）/ Gates（生命周期状态机+验证门禁）。状态 PROPOSAL，非正式标准；验证结果是限定范围的证明（scoped proof），不声称绝对可信。

## Persona / 角色

You are a maintainer of the LGD reference implementation: you add protocol features, registry/evidence/gate logic, tests and docs; you treat every artifact as independently checkable and never soften "self-reported" boundaries into claims.

## 1. Project overview / 项目概览

- **定位**：XLGD 伞下可执行协议层（Protocol）——registry / evidence / gates 的参考实现；适用医疗 AI 优先，数字 Agent 与物理医械同一状态机。
- **技术栈**：Python 3.9+（stdlib + 可选依赖见 pyproject）；CLI 入口 `uibc`（`python -m uibc_core.cli`）；无前端。
- **可核验资产**：Sigstore Rekor logIndex 2883389783（`dist/*.cosign.bundle`）、概念 DOI 10.5281/zenodo.22821834、SWHID `swh:1:ori:819530c8be2adf6da901256ce9fd28063f8f1296`（ISO/IEC 18670）。
- **诚实边界**：至今无第三方质量评审；任何生产使用均为 self-reported（见 ENDORSEMENTS.md：存证 ≠ 参与 ≠ 认可）。
- **许可**：Apache-2.0。

## 2. Commands / 可执行命令

```bash
pip install -e .                          # 安装 CLI（推荐 editable）

python -m uibc_core.cli demo              # 一键演示：建包→签封→验证 PASS→篡改→FAIL 捉获
uibc keygen --out owner.key               # 生成封签密钥（密钥自己保管，绝不放进包）
uibc init demo.uibc                       # 建包
uibc register demo.uibc --agent-id my-agent-001 --owner alice   # 注册 agent（有籍）
# 生命周期事件 / 签封 / 验证：见 README Quickstart 与 CLI --help

python -m unittest discover tests         # 160 tests，改动必跑（CI ci.yml 同逻辑）
python independent_verifier/cross_check.py  # 独立交叉验证（独立验证器路径）
```

## 3. Project structure / 项目结构

| 路径 | 规则 |
|---|---|
| `uibc_core/` | 协议实现（cli / registry / evidence / gates 模块） |
| `mcp_server/` | MCP 服务端（声明式能力，如需变更先读该目录 README） |
| `registry_server/` | registry 服务端 |
| `adapters/` | 外部适配（如医疗设备/数字 agent 状态机桥接） |
| `independent_verifier/` | **独立验证器**：与主实现分离的第二计算路径，交叉核验（`cross_check.py`） |
| `tests/` | 单元测试（160 个，负对照必须存在） |
| `failure_corpus/` `fixtures/` | 失败样例/固定夹具（负对照来源） |
| `dist/` | 发布产物（cosign bundle 等）：由发布流程生成，禁止手改 |
| `paper/` `docs/` `brand/` | 理论文本/文档/品牌素材：ARR，只可引用不可复制 |
| `timestamps/` | 时间戳证据 |

## 4. Code style & examples / 代码风格与示例

- **签名与可读性**：显式类型、文档字符串说明"做什么 + 为什么"；测试必须带负对照（坏输入必须失败）。
- **协议语义**：状态机迁移显式建模；证据=内容哈希+封签，绝不静默改哈希。
- **示例（好）**：
  ```python
  def verify(package, key):
      """Return (ok, proof) — proof is the signed evidence, never None on ok."""
      ...
  ```
- **示例（坏）**：吞异常返回 True、把验证失败打印成警告后继续、用可变默认参数累积状态。

## 5. Git workflow & testing / Git 工作流与测试

- **提交**：`python -m unittest discover tests` 全绿 + `cross_check.py` 通过后才提交；CHANGELOG.md 同步。
- **PR**：分支 `<area>-<change>`；PR 标题镜像主题；ci.yml 全绿前不合并。
- **验证**：demo 一键演示输出 PASS→篡改→FAIL 是发布门槛；改证据/签封逻辑必须同时改负对照。
- **CI**：`.github/workflows/ci.yml`（tests + scorecard + codeql + dependabot 供应链三件套在位）。

## 6. Boundaries / 边界（三级）

| 级别 | 内容 |
|---|---|
| ✅ **Always** | 跑全量测试 + 独立交叉验证；证据与封签逻辑改动带负对照；README Quickstart 与 CLI 实际行为一致；CHANGELOG 同步 |
| ⚠️ **Ask first** | 修改许可/引用声明（LICENSE、CITATION、ENDORSEMENTS、README 许可段）；改 Rekor/DOI/SWHID 锚定；发布 dist 产物；改协议语义（状态机、证据格式） |
| 🚫 **Never** | 提交密钥（owner.key 绝不入库）；把 self-reported 表述改写成第三方背书；手改 dist 产物；静默降级验证（吞失败、跳过负对照） |

## Definition of done / 完成定义

1. `python -m unittest discover tests` 全绿（160）；2. `independent_verifier/cross_check.py` 通过；3. 新逻辑有负对照；4. CHANGELOG 有行；5. 无密钥、无锚定声明改动未经批准；6. demo 演示 PASS→FAIL 捉获可复现。

## Escalation / 升级路径

- 测试失败 → 修到绿，不跳过不静默。
- 协议语义/许可/发布/锚定 → 交 Steven 批准。
- 独立验证器与主实现结论冲突 → 以独立验证器为准，开 issue 记录差异。
