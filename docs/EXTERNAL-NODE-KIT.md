# 外部验证节点接入包（30 分钟，一条命令）

> 目的：让**不是我们的人**在自己的机器上得出与我们相同的结论，并把这一个结果文件发回来。这件事比再加十个功能重要——它是"可复算"从主张变成事实的唯一方式。
>
> 当前状态：**外部节点 = 0**。你跑一次并回传 `external_node_result.json`，这个数就变成 1。

## 1. 你需要什么

- Python 3.9+（不需要 pip，不需要装任何依赖：验证器与第二实现都只用标准库）
- 一个 shell（Windows PowerShell / macOS / Linux 均可）
- 不需要 Git 账号，不需要申请权限（公开仓匿名可读）

## 2. 三条命令（约 3 分钟，不含下载）

```bash
git clone --depth 1 --branch release/v1.1-precheck https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
python benchmark/corpus.py                 # 首次会自建语料，约 10 秒
python tools/external_node_check.py --out external_node_result.json
```

最后一条会打印类似：

```
independent=PASS  reference=PASS(19ms)  probes=3/3 rejected  -> CONSISTENT
RESULT_JSON=.../external_node_result.json
```

## 3. 这个脚本到底做了什么（四件事，都可被你自己复核）

1. **独立验证**：用 `independent_verifier/iverify.py`（纯标准库，独立于主验证器编写）验证包；
2. **参考验证**：用 `uibc_core/verify.py` 验证同一个包，并比较两边结论是否一致；
3. **三个必须被拒绝的探针**：
   - 时间戳缺时区（`2026-11-17T05:59:59`）
   - 不存在的日历日（`1900-02-29`）
   - 大写 UUID
   
   这三条如果**有一条没被拒绝**，脚本会输出 `DISCREPANCY` —— 也就是说，它跑出 `CONSISTENT` 才证明"这套检查不是在无脑放行"。
4. **落一个 JSON**：含平台、Python 版本、命令、耗时、每项结果，可直接贴进你的工单或邮件。

## 4. 你不需要相信我们什么

- 你不需要相信我们的服务器（没有服务器参与）
- 你不需要相信我们的代码是唯一的实现（第二实现独立存在，且两边结论必须一致）
- 你不需要相信"结论对"（我们的结论只有一句：**在观察到的证据边界内，没有检出违规**；它不断言 agent 正确、安全、明智，也不断言证据为真）

## 5. 回传什么（这一步把它变成"节点"）

把 `external_node_result.json` 发回给联系人（或贴进 issue）。里面**不含任何个人信息**——只有平台字符串、Python 版本、耗时与判定结果。

我们会登记：平台 / 时间 / 结果。**如果你的结果与我们的不一致，那才是最有价值的报告**，我们会优先处理。

## 6. 可选的深一步（约 25 分钟）

```bash
python -m unittest discover -s tests -p "test_*.py"    # 全量 208 项
python tools/compose_demo.py                            # K1-K8 七个组合场景
python tools/pccp_case.py --prev benchmark/corpus/base --curr tools/out/_mb/m_M17
```

`pccp_case.py` 会输出一份《版本历史报告》，是我们给器械客户看的那个东西的最小版本。

## 7. 我们已知的边界（写在这里，省得你替我们发现）

- 整包回滚：仅靠包内信息无法发现，需包外记录的 head（S9）；
- 若证据不是我们自己采集，"证据为真"永远不会被这份报告证明；
- AER-1 语料的 base64 严格性与 Merkle 包含证明，我们目前**没有对等实现**（见 `docs/AER1-CROSSWALK-RESULT.md`）。
