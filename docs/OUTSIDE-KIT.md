# 外部复跑套件：从"你可以复现"到"拿去跑"

`docs/OUTSIDER-RUN.md` 请人克隆仓库。多数可能来核对的人是**不会**克隆的：clone、建 venv、安装、finding。差的就是那几步。

所以这里有一个压缩包：

```bash
python3 tools/build_outside_kit.py --out dist/
# dist/uibc-audit-kit-<version>.zip   43 files / ~118 KB
```

对方：解压 → `python3 tools/outsider_audit.py` → 读判定。不用 clone，不用装，不联网。

## 包里是什么

白名单，不是整个仓库：

| 内容 | 用途 |
|---|---|
| `tools/outsider_audit.py` | 审计器本体（基线、四段红队、互操作） |
| `uibc_core/` | 它用来判定的验证器 |
| `fixtures/clean.uibc/` | 被审的包 |
| `tests/fixtures/anchor/` | 真实 FreeTSA token，用于跑 S16 |
| `SHA256SUMS` + `kit-manifest.json` | 每个文件的 sha256，以及"套装"的整体摘要 |

**故意不放**：完整 `tests/`（审计器的各阶段自带正确性断言）、`docs/`（声明留在仓库里，不该混进你要跑的东西里）、任何联网代码。

## 收到包的人能自查两件事

1. **包有没有被动过**：`python3 tools/build_outside_kit.py --verify <zip>`（或直接 `sha256sum -c`）。
2. **判定是不是我们那份代码给的**：运行时它会打印 `verify.py` 的 sha256 与 `from this repo: True`。

一条测试把"改一个字节"变成"校验失败"：篡改 `uibc_core/verify.py` 后 `--verify` 退出码为 1 并指名文件。

## 它仍然不会告诉对方的事

- **有没有第三方见证过我们的包**：没有，数字是 0，工具打印 0。
- **互操作段跑没跑**：没给 `--kit` 就是 `SKIPPED`，跳过不算通过。

套件里也直接写了这两条（`kit-manifest.json` 的 `claims_this_does_not_support`），避免收到包的人以为它证明了更多。

## 为什么这件事值得单独做

前面十八轮证明的是"我们有能力被验"。这一轮做的是"有人能验"的前置条件——**把门槛降到一步**。门槛不降，第三方永远是 0，而且不是因为我们做得不够，是因为没人会为了核对一份声明去配环境。
