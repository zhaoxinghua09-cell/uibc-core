# 树摘要的第二个实现：同一个数字，两套语言算出来

`tools/outsider_rerun.py` 产出两个数，收据压在这两个数上：

- `tree_sha256` —— 把每个文件写成 `<路径>:<该文件字节的 sha256>` 一行，按路径排序，再对整串取 sha256（排除它自己写的两页）；
- `content_sha256` —— 只把每个文件的内容摘要排序后取 sha256，路径完全不参与。

一个只有一种程序能算出来的数，是那个程序的意见，不是证据。所以 `tools/verify-js/tree-digest.mjs` 用 Node 标准库把这两个数重算一遍：不 import `uibc_core`，不跑 Python，不装 npm 包，也不读它的实现对家。

## 怎么跑

```bash
python tools/tree_digest_second_impl.py            # 长表
python tools/tree_digest_second_impl.py --json     # 机器可读
python tools/tree_digest_second_impl.py --check    # 不一致就 exit 1
node tools/verify-js/tree-digest.mjs --root . --files-from <NUL 分隔清单>
```

## 为什么"成员名单"是递过去的，不是各自再走一遍

两条实现如果各自遍历目录，它们可以靠**"对同一批别的文件得出同一个数"**而通过——这种一致什么也没证明。所以 Python 侧把自己的文件清单（NUL 分隔）交给 Node，两边算的必须是同一批文件。名单本身是否完整，由收据与 `--check` 负责；这里只证明**公式不是某一个程序的私人口径**。

## 三个可能被怀疑的口径，各自的答案

| 怀疑 | 答案 | 谁把它钉住 |
|---|---|---|
| "排序是按 Python 的字符串比较吧" | Node 用 UTF-8 字节序比较（`Buffer.compare`），而不是 JS 默认的 UTF-16 码元序——后者会把星形字符排错位置 | `tree-digest.mjs` 的 `byBytes`，与测试里的改名/翻字节对照 |
| "换行和分隔符是 Python 的习惯吧" | 两边都用 `\n` 连接、都取 UTF-8 字节，Node 侧一眼可读 | 同一个函数体内的两行 join |
| "两个轴在第二实现里还是同一个意思吧" | 改名：严摘要动、内容摘要不动；翻一个字节：两个都动 | `tests/test_tree_digest_second_impl.py` 的 rename 与 flip 两条 |

## 强制，而不是声明

CI 的 `second-implementation` job 里多了一步 `python tools/tree_digest_second_impl.py --check`。它红的方式只有一种：两个实现不再一致。也就是说，以后谁改了 `tree_digest()` 的排序、拼接或排除规则而没有同步改 Node 侧，构建会红——"第二个实现"从一句介绍变成一个会失败的检查，这与仓里既有那条 `assert_second_impl.py`（JS 验证器与 Python 验证器同集）是同一个做法。

**边界**：第二个实现只证明算式和序列化可被另一套工具链复现。它不证明这批字节是上游原本的字节（那由 vendored corpus 那道门负责），也不证明这批字节里的算术是对的（那由语料复算与第二实现折法负责）。三个问题分开，是因为它们可以被分开检查；混成一句"我们有两个实现所以可信"，就又不成立了。
