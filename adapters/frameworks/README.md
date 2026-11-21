# Framework hooks: 把框架里的工具调用记成可验证证据

零依赖，不 import 任何框架。

```
from adapters.frameworks.uibc_framework_hooks import CallRecorder

rec = CallRecorder("agent.uibc")
tool = rec.wrap_callable(search_web, name="search_web", description="Search")
tool.run("aer-1")        # 调用被记录，结果照常返回
rec.seal()               # 刷新 Evidence Root
```

## 三个形状

| 形状 | 入口 | 对应现实对象 |
|---|---|---|
| LangChain Tool | `wrap_callable(...)` → `name` / `description` / `run` / `invoke` / `func` | `langchain.tools.Tool` 的调用约定 |
| OpenAI function tool | `function_spec(...)` → `{"type":"function","function":{...},"invoke":callable}` | Chat Completions / Agents SDK 的描述符 |
| MCP `tools/call` | `mcp_tool_result(rec, name, args, payload, is_error)` | MCP 返回的 `{"content": [...], "isError": bool}` 信封 |

## 状态：诚实的三句话

1. **零依赖、可跑**：`tests/test_framework_adapters.py` 7 项，全量 `357 tests OK`。
2. **未在真实框架栈中运行过**：上面的形状是**约定兼容**，不是安装 LangChain / OpenAI Agents SDK 后实测。说有就有，没有就说没有。
3. **记录不等于证明**：recorder 只把"发生过什么"变成"以后可被引用"，它不能让主张为真。未签名包的验证结论是 `INCONCLUSIVE`（S6 无法判定），这是正确输出，不是缺陷。

## 为什么用 duck-typing 而不是 import

硬依赖会让这个文件在真正需要它的地方——CI、离线机器、评审者的笔记本——根本 import 不起来。这里需要的只有三样东西：名字、描述、一个可调用对象，全是约定。

## 一次记录长什么样

每条调用写成一份 JSON 证据：

```json
{
 "arguments": {"query": "aer-1"},
 "result": {"hits": 3, "query": "aer-1"},
 "status": "OK",
 "tool": "search_web"
}
```

失败调用记 `status: "ERROR"` 并附 `error`，默认仍然抛出（`on_error="swallow"` 可吞掉但照样记录）。
