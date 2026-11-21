# Verify it yourself — no AI knowledge needed
# 你自己就能验——不需要懂 AI

This pack is fictional data with real cryptography. You do not need to
understand seals, keys or AI to check it. You only need to copy one line,
press Enter, and read one word.

本演示包是虚构数据、真封签。你不需要懂封签、密钥或者 AI。你只需要
复制一行字、按回车、看一个词。

---

## EN — five steps

**Step 1 — Open a terminal.**
Windows: press the Windows key, type `powershell`, press Enter.
Mac: press Command+Space, type `terminal`, press Enter.
A plain window opens where you can type lines. That is all a terminal is.

**Step 2 — Get the tool (once).**
Copy this line into the window, press Enter:

```
pip install uibc-core
```

(You also need this demo folder: clone
https://github.com/zhaoxinghua09-cell/uibc-core.git and use
`examples/link3-handover-evidence/`, or take the folder you were given.)

**Step 3 — Go to the demo pack.**
Copy this line, press Enter:

```
cd uibc-core/examples/link3-handover-evidence/packages
```

(For this practice pack, use the folder you were given instead.)

**Step 4 — Run the check.**
Copy this line, press Enter:

```
uibc verify approved
```

**Step 5 — Read one word.**
The last lines tell you the verdict. Only three words are possible:

- **PASS** — Nobody changed anything in this folder since it was sealed.
  What you are holding is exactly what the sender sealed.
- **FAIL** — Something was changed, swapped or removed after sealing.
  The check names the exact file. Do not file it, do not use it — send
  it back and ask why.
- **INCONCLUSIVE** — The check could not be completed (for example a
  file or the key is missing). This is *not* a pass. Treat it as
  "unknown — ask before you rely on it".

**One extra habit — pin the key.**
A seal alone proves nothing was *changed*; it does not prove *who*
sealed it. When the sender gives you their public key (a short text
file), add it to the line:

```
uibc verify received-resealed --pubkey ../meridian-owner.pub
```

Now a pack re-sealed by somebody else fails too. Think of it as
checking the signature against the specimen signature you already hold.

---

## 中文——五步

**第一步：打开终端。**
Windows：按 Windows 键，输入 `powershell`，回车。
Mac：按 Command＋空格，输入 `terminal`，回车。
会弹出一个能打字的窗口。这就是终端，没别的。

**第二步：把工具拿下来（只做一次）。**
把这一行复制进窗口，回车：

```
pip install uibc-core
```

(You also need this demo folder: clone
https://github.com/zhaoxinghua09-cell/uibc-core.git and use
`examples/link3-handover-evidence/`, or take the folder you were given.)

**第三步：进到工具目录。**
复制这一行，回车：

```
cd uibc-core/examples/link3-handover-evidence/packages
```

（练手包就用你拿到的那个文件夹。）

**第四步：运行检查。**
复制这一行，回车：

```
uibc verify approved
```

**第五步：只看一个词。**
最后几行就是裁决。只有三种可能：

- **PASS（通过）**——这个文件夹自封存之后，没人动过任何东西。
  你手里的，就是对方封存的那一份。
- **FAIL（不通过）**——封存之后，有文件被改了、换了或删了。
  检查会把出问题的文件名直接写出来。别归档、别使用——退回去问。
- **INCONCLUSIVE（无法判定）**——检查没做完（比如缺文件或缺钥）。
  这**不是**通过。它的意思是「不知道——问清楚之前别依赖它」。

**多一个习惯——钉住公钥。**
封签只能证明「没被改过」，证不了「是谁封的」。对方把公钥
（一个很短的文本文件）给你时，把它加进命令：

```
uibc verify received-resealed --pubkey ../meridian-owner.pub
```

这样，别人换把钥匙重封的包也会 FAIL。就像拿签名去比对你手里
留存的签名样本。

---

*Practice first on this pack: run the check on `packages/approved`
(expect PASS), then on `packages/received-swapped` (expect FAIL naming
the report file).先拿这个包练手：验 `packages/approved`（应为
PASS），再验 `packages/received-swapped`（应为 FAIL 并指名报告
文件）。*
