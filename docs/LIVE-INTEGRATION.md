# 真实框架栈内实测（LangChain）

`2026-11-18`｜`langchain-core 1.8.2`｜`Python 3.12`／Linux

---

## 之前写的是"形状兼容"，这次是"被框架调用"

`uibc_framework_hooks.py` 的三形状钩子是**鸭子类型**：它接受长得像 Tool 的对象，从没在真实框架里跑过。矩阵里一直标着"部分对齐（未在真实框架栈内实测）"。

新增 `adapters/frameworks/langchain_callback.py`：`UibcCallbackHandler` 是**真正的 `BaseCallbackHandler` 子类**。我们不包任何东西、不拦截任何东西——LangChain 每调一次工具，就主动推给我们一次 `on_tool_start` / `on_tool_end` / `on_tool_error`。

这就是"形状兼容"与"栈内实测"的全部区别，也是这个仓库不愿意含糊的那一格。

## 实测结果

| 环境 | 结果 |
|---|---|
| 装了 `langchain-core 1.8.2` | **6 tests，5 通过，1 skip** |
| 裸 Python（无 LC） | 6 skip，`import` 不失败；构造 handler 抛 `RuntimeError` 并给出安装命令 |

那 1 个 skip 是**反向测试**（"无 LC 时构造必须报错"），装了 LC 时它本就该跳。

跑法：

```bash
python -m venv /tmp/lc && /tmp/lc/bin/pip install langchain-core
/tmp/lc/bin/python -m unittest tests.test_langchain_live -v
```

## 为什么必须让它跑真东西

四条测试都不靠"我们以为 LC 会怎样"：

1. 真 `@tool` 装饰的函数，`invoke(..., config={"callbacks": [h]})` → 索引里多出一条，`arguments == {"a":2,"b":3}`、`result == 5`、`tool == "add_two"`；
2. 两次调用 → 两条条目、两个不同 `content_hash`；
3. **抛异常的工具仍然留下证据**（`status: "ERROR"`，含原始报文）——失败调用不得变成"没有发生"；
4. 框架写出来的包，我们的 `verify()` 照样能验。

## 一个被自己的测试抓到的坑：记录之后必须 seal

第一次跑第 4 条，**S5（evidence root）FAIL**。

原因不是 bug，是设计：`record()` 每写一条就改变 evidence root，而 `manifest.evidence_root` 还停在上一版；`seal()` 才是把新根发布出去的动作。

这跟"锚定证明不能写回包内"是同一族错误——**改了内容却不更新承诺**。所以我们没有去改测试绕过它，而是把它拆成两条：

- `test_recorder_stays_verifiable_after_framework_traffic`——seal 之后 S4/S5 PASS，S6 仍为 INCONCLUSIVE（未签名不得报 PASS）；
- `test_forgetting_to_seal_is_caught_by_S5`——不 seal 直接验，**S5 必须 FAIL，总判定必须 FAIL**。

一个会让"忘了封签"通过的验证器只是装饰品。

## 每调用延迟：把"口径不同"这一格量出来

之前的 23 ms 是**每包**（含完整校验），CCS 说的亚毫秒是**每调用**。拿包的数去比调用的数，是让对照表失真的典型手法，所以补测了热路径：

| 指标 | 值 |
|---|---|
| 单位 | 一次 `record()`（**含 index 重写 + evidence 文件写盘**） |
| n | 300（另 20 次预热） |
| median | **1.225 ms**（复跑 1.222 ms） |
| mean | 1.235 ms |
| p95 | 1.929 ms |
| p99 | 2.156 ms |

**结论：同量级，不领先。** 1.2 ms 对"亚毫秒"是一个数量级内的差距，而我们的数字包含写盘与索引重写——对方的亚毫秒大概率不含。既不宣称优势，也不掩饰差距。

工具：`tools/latency_per_call.py`（`--n` / `--json`，可复跑）。

## 边界（这次没测的）

- **只跑了单次 tool invoke**，没有跑 ReAct / 多步 agent 循环，也没有跑并发。
- **未测 OpenAI Agents SDK**、CrewAI、AutoGen；LC 之外仍是形状兼容。
- **未测 IDE 侧**（Claude Code / Cursor / Goose），矩阵第 15 项仍是"对齐但 IDE 插件缺"。
- LC 的 `on_tool_end` 输出若是富对象，会被 `_json_safe` 压成 `content`/`text`/`model_dump`/`repr` 之一；这是记录层的取舍，不是完整保真。

## 全量

`379 + 6 = 385` 项，裸环境 `OK (skipped=8+6)`；装 LC 环境 `6/6`（1 个反向 skip）。
