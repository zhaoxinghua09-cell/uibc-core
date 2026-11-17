# 账号门禁（pre-push）：先核对账号，再推送

## 为什么会有这个东西

2026-11-17 有一次推送，是**先推、后核对**：当时只确认了"远端指向正确的仓库"和"认证成功"，就认定账号没错。这两件事同时成立，**并不能**推出"凭证属于该仓库的所有者"——它完全可能是一个有写权限的协作者或组织成员的 token，甚至是一把共享 key。账号一旦串，外部看到的是作者身份错误，而自己在本地完全看不出来。

现在改为**推送前核对**，核对不通过就不推。

## 它查什么

1. 从 `origin` 解析 GitHub owner（`github.com[:/]<owner>/...`）；
2. 用 `git credential fill` 取出当前存储凭证（**不打印、不落盘**）；
3. 调 `GET https://api.github.com/user`，只取 `login`；
4. 比对 `login` 与 owner；不一致 → **exit 1，阻断推送**。

实测（本轮）：

```
正例  remote_owner=zhaoxinghua09-cell  credential_login=zhaoxinghua09-cell  -> OK (exit 0)
反例  remote_owner=stevenzhao07        credential_login=zhaoxinghua09-cell  -> MISMATCH (exit 1)
```

## 怎么用

```bash
# 单次手动核对
python tools/pre_push_gate.py

# 已安装为钩子，每次 push 自动执行
.git/hooks/pre-push
```

**允许例外，但必须显式**：仓库确实属于组织或其他账号时，设 `GIT_ALLOWED_OWNERS=owner1,owner2`。不提供静默跳过——绕过只能用 `--no-verify`，那是自觉动作，不是意外。

## 边界（写清楚，免得被当成万能）

- 只对 **GitHub + HTTPS 凭证**有效；SSH key 走的是另一条链路（当前本机没有 SSH key）；
- 依赖网络：API 不可达时**按失败处理**（fail-closed），不会"查不到就放行"；
- 它不判断权限是否足够，只判断"是不是同一个号"。
