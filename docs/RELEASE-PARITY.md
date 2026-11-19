# 三种获取方式，三个不同的验证器

**实测 2026-11-18。复算：`python3 tools/check_release_parity.py`**

## 一张表

| 获取方式 | 版本 | 检查项 | 项数 |
|---|---|---|---|
| 归档（DOI） | `0.2.1` | S1–S6 | 6 |
| **`pip install uibc-core`** | **`0.3.3`（最新）** | **S1–S6** | **6** |
| 仓库 `main` | 未发布 | S0–S18 | 19 |

## 怎么测的（因为"项数"最容易测错）

第一版比较是错的：我数 `verify.py` 的行数、数 `record("S…")` 的字符串，得出"PyPI 版 8 项"。**这个数字不对**——不同包会触发不同检查，数源码什么也证明不了。

正确的测法是**拿同一个包喂给两个版本**：

```
用 tools/outsider_audit.py 的 build_v11 + build_ext + build_s16 + build_ckpt
造一个"全特性包"（v1.1 生命周期 + merkle + 锚 + RFC3161 + 收据链 + 策略）
       ↓
仓库版 verify  → INCONCLUSIVE，17 项（S1–S18 除 S9，未给 pin）
PyPI 0.3.3    → INCONCLUSIVE，6 项（S1–S6）
```

**结论不是"它少跑了几项"，是"它不认识 S7–S18 中的任何一项存在"。** 那些字段它不看。

顺带确认了两件好事：出厂包和 `examples/link1` 的三个示例，在 0.3.3 上跑出的判定与 README 完全一致（PASS / FAIL 点名 S4 / INCONCLUSIVE）。**示例没有夸大。**

## 这意味着什么

`pip install uibc-core` 是最常见的获取方式。任何人这样装完，再读到"十八项检查"，看到的都是一个只有六项的验证器。

这不只是"版本旧"：**最新发布版就是六项**。三个渠道里，有两个（DOI 和 pip）都停在六项。

## 现在能不能发布？可以

```
python3 tools/preflight_release.py
```

它把一个"只有包目录"的导入路径当作安装后的环境，喂全特性包，数它报了什么：

```
仓库声明 19 项；安装后会报出 17 项（判定 INCONCLUSIVE）。
会报：S1..S8, S10..S18
给一个外部 pin 后再报：S9
包与仓库一致，可以发布。
```

**也就是说代码是自足的**——不依赖仓库里的额外文件。缺的不是能力，是**一次发布**。

## 发布清单（需要你做的只有两步）

| 步骤 | 谁做 | 说明 |
|---|---|---|
| 1. 定版本号 | 我 | 建议 `0.4.0`：按本项目自定的 semver 规则，**改变判定结果就是 breaking**，多 12 项检查必然改变判定 |
| 2. 改 `pyproject.toml` 的 version | 我 | 一条改动 |
| 3. `git tag v0.4.0 && git push --tags` | **你或授权我** | 对外可见，需明确点头 |
| 4. `python -m build` + `twine upload` | **你**（PyPI 令牌在你手里） | 让 `pip install` 拿到 18 项 |
| 5. GitHub Release → Zenodo 自动归档 → 新 DOI | **你**（Zenodo 与 GitHub 的联动在你账号上） | 让 DOI 能背书 18 项 |
| 6. 更新 `CITATION.cff` 的 version/DOI | 我 | 新 DOI 出来后一条改动 |

第 3–5 步我不会替你点：打 tag 与上传是不可撤回的对外动作，账号也在你手里。

## 没做

- **没改版本号**。改了而不发布，只会多一个"说有新版本、却装不到"的坑。
- **没给 `0.3.3` 打补丁**。历史版本不该被润色成它没有的样子。

---

## English

Three ways to obtain this project; three verifiers. The archive (DOI, `0.2.1`) reports six checks. The **latest published package** (`pip install uibc-core`, `0.3.3`) reports six. The repository reports nineteen (S1–S19; S19 needs an external freshness state file to trigger).

The first attempt at this comparison counted lines and string literals and concluded "eight" for the package. That number was wrong, because which checks run depends on the package fed in, not on what the source mentions. Feeding **one** full-feature package to both verifiers gives the real answer: the published one does not merely run fewer checks -- it does not know S7-S18 exist.

The reassuring half: `tools/preflight_release.py` shows the repository's package directory is self-sufficient, so what is missing is a **release**, not a capability. The release needs a version, a tag and an upload -- the last two are outbound and belong to the account holder.
