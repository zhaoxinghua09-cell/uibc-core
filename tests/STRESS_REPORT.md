# uibc-core 压力测试报告

- 执行时间：2026-09-17 14:11 (UTC+8)，总运行 35.5s；**2026-09-17 晚间复跑并新增场景 g（v0.2 签名路径压测），7/7 通过（43.0s）**
- Python：3.13.12（C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe）
- 环境：Windows 11 Pro / Intel i5-13400 / 32GB RAM
- 运行方式：项目根目录 `python -m unittest tests.stress_test -v`，7/7 通过（v0.2 起含场景 g）
- 测试文件：`tests/stress_test.py`（未修改 uibc_core 源码与现有单元测试）
- 临时大文件（10MB/50MB）测毕即删，无残留

## 实测结果

| 场景 | 规模 | 耗时 | 吞吐/速率 | 结论 |
|---|---|---|---|---|
| a) hash_file 大文件哈希 | 10 MB | 0.0076s | 1309.5 MB/s | 可支撑生产负载 |
| a) hash_file 大文件哈希 | 50 MB | 0.0359s | 1393.1 MB/s | 可支撑生产负载 |
| b) evidence_root | 1,000 哈希 | 0.0003s | ~310 万 hashes/s | 可支撑生产负载 |
| b) evidence_root | 10,000 哈希 | 0.0034s | ~290 万 hashes/s | 可支撑生产负载 |
| b) evidence_root | 100,000 哈希 | 0.0393s | ~254 万 hashes/s | 可支撑生产负载 |
| c) validate_lifecycle 长链 | 10,000 事件 | 0.0024s | ~0.002s/万事件（411 万 events/s） | 可支撑生产负载 |
| c) validate_lifecycle 长链 | 100,000 事件 | 0.0298s | ~0.003s/万事件（336 万 events/s） | 可支撑生产负载 |
| d) verify() 500 证据条目 PASS | 500 entries | 0.4298s | 包构建（init→register→500×evidence→submit）另计 3.42s | 可支撑生产负载 |
| d) verify() 500 证据条目 FAIL（篡改 1 个文件） | 500 entries | 0.4165s | FAIL 路径与 PASS 同量级，无异常放大 | 可支撑生产负载 |
| e) CLI 全链路（subprocess） | init→register→50×evidence→submit→verify | 29.3376s | 单次进程启动约 0.55s（54 次调用），主要是 Python 解释器冷启动开销 | 存在隐患需优化（进程模型，非算法） |
| f) tracemalloc 内存 | 100,000 事件链验证 | 0.1130s | 峰值增量 6.3 MB，净增量 ≈0 MB，O(1) 附加内存 | 可支撑生产负载 |
| g) seal_sign（v0.2 签名） | 10,000 ops | 0.0804s | ~124,400 ops/s | 可支撑生产负载 |
| g) seal_verify（v0.2 验签） | 10,000 ops | 0.0754s | ~132,600 ops/s | 可支撑生产负载 |
| g) verify 严格模式（S6）500 条目 PASS | 500 evidence | 0.4056s | 与开放模式 verify（0.43s）同量级，签名核验无额外放大 | 可支撑生产负载 |

## 分析

1. **哈希与证据根（a/b）**：hash_file 64KB 分块读取，吞吐 1.3 GB/s 接近 SHA-256 硬件加速上限；evidence_root 随规模线性且速率稳定在 250 万+/s，10 万证据根计算 <50ms。
2. **生命周期状态机（c/f）**：单遍线性扫描，10 万事件 30ms、内存峰值仅 6.3MB（主要来自 seen_ids 集合），线性扩展无退化。
3. **verify() 大包（d）**：500 条目完整校验 0.43s，其中主要是逐文件 I/O+哈希；篡改后 FAIL 路径耗时与 PASS 相当（仍需全量哈希重算），无病态行为。
4. **CLI 全链路（e）**：54 个子进程串行共 29.3s，平均每个进程 ~0.54s——瓶颈是每次调用重新启动 Python 解释器，而非 core 算法。**建议**：批量场景提供单进程 API（如 `--batch` 或库调用 `cli` 函数），或让 cmd_evidence 接受多文件。
5. **无算法层面的性能隐患**；唯一「存在隐患需优化」项是 CLI 进程模型（场景 e），属架构改进项，不阻塞生产。

## 复现

```
cd d:/Workbuddy/2026-09-17-20-24-56/uibc-core
C:/Users/Administrator/.workbuddy/binaries/python/versions/3.13.12/python.exe -m unittest tests.stress_test -v
```
