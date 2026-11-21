# UIBC 版本一致性门禁 —— 候选补丁包（未应用）

**性质**：候选 PR 方案，仅新增文件（零改动风险）。**未修改任何仓库。**
**日期**：2026-11-19
**仓库**：`zhaoxinghua09-cell/uibc-core`，本地克隆 HEAD `2eb9763`

---

## 1. 先纠正我自己的一个说法

前几轮我写的是"三处版本不一致（Release v0.3.3 / PyPI 0.4.0 / SPEC_VERSION 0.3.3-proposal）"。

**这轮实测把它拆开了，我之前的表述不够准确：**

```
pyproject.toml [project].version   0.4.0
uibc_core/__init__.py __version__  0.4.0
PyPI latest release                0.4.0
uibc_core/__init__.py SPEC_VERSION uibc-core/0.3.3-proposal   ← 只有这一处不同
```

- `pyproject`、`__version__`、PyPI 三者**是一致的**（都是 0.4.0）。
- `__version__` 写成字面量是**有意设计**，`__init__.py:20-25` 的注释写明：从已安装包元数据推导版本会让干净克隆的人看到 `0.0.0-proposal`（曾是被评审打回的问题 P0-2）。
- 真正的问题只剩一条：**`SPEC_VERSION` 落后一个 minor**。

所以"三处全乱"的说法我撤回，改成精确表述：**一处标签滞后，但这一处会污染证据**。

---

## 2. 为什么这一处不是小事（FACT + INFERENCE）

- **FACT**：`spec_id()` = `SPEC_VERSION@impl_digest()[:12]`（`__init__.py:50-52`），而证据报告/验证输出携带的正是 `spec_id`。
- **INFERENCE**：一个 2026-11-18 发布的 PyPI 0.4.0 包，自报身份仍是 `uibc-core/0.3.3-proposal@<新字节的摘要>`。任何第三方按 `spec_id` 归档报告，都会把新代码的结果记到旧标签名下。这不是显示问题，是**可追溯性**问题。

---

## 3. 改了什么（只新增 3 个文件）

| 文件 | 说明 |
|---|---|
| `tools/check_version_consistency.py` | 门禁脚本：读 pyproject / `__version__` / `SPEC_VERSION` / git tag / PyPI，逐条比对 |
| `tools/selftest_version_gate.py` | 13 个 fixture 用例（自测脚本，不依赖 pytest） |
| `.github/workflows/version-consistency.yml` | CI：push / PR 触发，`permissions: contents: read`（最小权限），含"合并前固定到 SHA"的 TODO |

**明确不改 `SPEC_VERSION`**：把它从 0.3.3 改成 0.4.0 会改变证据标识的含义，属于协议决策，不是我的权限。这个补丁只负责**让不一致无处可藏**。

---

## 4. 对真实仓库的实测结果

```
repo: ...\uibc-core
  pyproject.toml [project].version              0.4.0
  uibc_core/__init__.py __version__             0.4.0
  uibc_core/__init__.py SPEC_VERSION            uibc-core/0.3.3-proposal
  latest git tag                                None
  PyPI latest release                           0.4.0

VERSION CONSISTENCY: FAIL
  - [spec_version_lags_package] SPEC_VERSION 标签=0.3.3 落后包版本=0.4.0；
    证据报告携带 spec_id，会以旧标签指向新字节
```

即：**门禁装上去的第一天就会红**。这正是它该有的行为——现在红，说明它有效；如果它装上去是绿的，那才是门禁写错了。

`latest git tag = None` 是本地克隆未拉 tag 所致，CI 里 `fetch-depth: 0` 会取到。

---

## 5. 测试

| 组 | 用例 | 结果 |
|---|---|---|
| 一致 / 完全不一致 | V01, V02, V12 | PASS |
| SPEC_VERSION 落后 / 超前 / 无版本段 / 缺失 | V03, V04, V05, V06 | PASS |
| `__version__` / pyproject 缺失 | V07, V08 | PASS |
| git tag 不一致、PyPI 不一致 | V09, V10 | PASS |
| 边界：PyPI 不可达不误判、带 `-proposal` 后缀合法 | V11, V13 | PASS |
| **合计** | **13** | **13/13 PASS** |

命令：

```powershell
python tools\check_version_consistency.py --repo . --pypi 0.4.0
python tools\selftest_version_gate.py
```

`git apply --check` 对原仓 **exit 0**（三个文件均为新增，无冲突面）。

---

## 6. 剩余风险

| 风险 | 级别 | 说明 |
|---|---|---|
| 装上后 CI 立刻红 | P1（流程） | 必须先决定 `SPEC_VERSION` 怎么改，否则 main 分支会持续失败。建议顺序：先改标签 → 再合并门禁 |
| `SPEC_VERSION` 的语义我未定义 | P1 | 到底该不该跟包版本绑定、要不要引入独立 spec 版本序列，是协议决策 |
| CI 里 `actions/checkout@v4` 未固定 SHA | P2 | 已在 workflow 里留 TODO；任务书 P1-D 要求 SHA 固定 |
| 未联网验证 PyPI 拉取 | P2 | 本机网络对 pypi.org 可达性未测，脚本对不可达做了"不计为不一致"的降级 |

---

## 7. 批准点

- 是否**先改 `SPEC_VERSION`**（改成 `uibc-core/0.4.0-proposal` 或引入独立 spec 序列）——这是协议决定，需你定。
- 是否合并门禁 workflow（会立刻让 main 变红，需接受"红-修-绿"的过程）。
- 建分支、提交、推送均需单独批准。

---

## 8. 三个 P0 的累计状态

| P0 | 产物 | 用例 | 可应用 |
|---|---|---|---|
| MedXpert 时效统一 | `p26_medxpert_freshness/` | 12 + 7 | 是 |
| LGD-Eval 评测/授权分离 | `p27_eval_authz/` | 18 | 是 |
| UIBC 版本一致性门禁 | `p28_version_gate/` | 13 | 是 |

三个都是"补丁 + 用例 + 真实前后对照"，都未落地。
