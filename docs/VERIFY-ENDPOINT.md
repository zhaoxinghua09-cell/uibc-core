# 在线验证入口：把包传到 URL，拿回判定

对手有一个能直接打开的验证页面（`verify.actionstate.ai`），我们没有。这一轮补的不是页面，是页面背后那个东西：一个零依赖、只依赖标准库的验证端点。

```bash
python3 tools/serve_verify.py --port 8770
curl -X POST --data-binary @pkg.zip http://127.0.0.1:8770/verify
```

实测（本地，2026-11-18）：

```
$ curl -sS -X POST --data-binary @clean.zip http://127.0.0.1:8770/verify
result: INCONCLUSIVE
counts: {'PASS': 7, 'INCONCLUSIVE': 1}
failed: []
inconclusive: ['S6']
checks: 8
```

`INCONCLUSIVE` + `failed: []` 是对的：出厂包没签名，S6（封签）如实报不可判定，后续检查不越过它。一个返回 `PASS` 的端点会是在替包撒谎。

## 三条设计约束，按最容易做错的顺序

**1. 它只见过滤后的字节。** 没有"验一下你机器上这个目录"这类参数，请求体就是包。整类"调用方让服务器去读它本不该读的东西"的漏洞因此不存在。

**2. 压缩包是敌意输入。** zip 的成员名可以是 `../../etc/passwd`，可以有上万个条目，也可以是解压炸弹。所以：**名字在解压之前检查**，成员数与解压后总字节都有上限，任何一项不过就 400 拒绝，而不是解压一半。

**3. 判定不是承诺。** 响应说每条检查看到了什么、哪些不可判定，从不说"这个包是有效的"；也不签任何东西。

## 测试覆盖的八件事

| 用例 | 断言 |
|---|---|
| `/health` | 返回能力与限额 |
| 真包 | `INCONCLUSIVE`，含 S1/S4/S5/S6，S6 在不可判定里 |
| 平铺与嵌套一层 | 结果一致（两种打包习惯都认） |
| 改 `evidence_root` | `FAIL`，`S5` 出现在 `failed` |
| `../../escape.txt` 成员 | 400，`parent traversal` |
| `/etc/passwd` 绝对成员 | 400 |
| 超过 8 MB 输入 | `Rejected` |
| 不是 zip | 400，`not a zip` |

## 还没有做的事（说清楚）

- **没有部署到公网。** 默认只绑 `127.0.0.1`。真挂上去是**对外动作**，要你决定：放哪（Cloudflare Worker / 一台 VPS / 内网），以及挂上去之后它代表谁。
- **没有并发压力测试。** `ThreadingHTTPServer` 够用但不是生产级；真开放前要加请求队列上限与超时。
- **没有速率限制。** 公网端点必须有，否则一次解压炸弹刷满 CPU 就能让别人替我们"证明"这个服务不可用。
