# What the gate claims about the network, and what it does not

`tools/reproduce_gate.py` prints one line about the network. Until #301 that line
read `network reachable on this machine`, and before #300 it failed the run
outright when it was reachable. Both were wrong in the same direction: they
described the machine while the claim that needs defending is about the run.

This page states the claim, the two facts it is built from, the evidence on two
machines, and the boundary — the part a reader should not infer.

## The claim

> On this machine, during this run, the driver process made **zero** outbound
> connection attempts. Every published number was re-derived from bytes already
> on disk.

Note what the sentence is not. It is not "this machine has no network" and not
"the whole run was offline". A machine with internet is the normal case, and
almost every reader runs the gate on one.

## Two facts, deliberately separate

| fact | whose property | how it is obtained | can it fail the run |
|---|---|---|---|
| `network probe on this machine` | the machine | TCP connect to three targets, first that answers wins; if none answers, the observation is printed verbatim | **no** — information only |
| `outbound attempts by the driver` | the run | `NetGuard` wraps `socket.connect` / `socket.create_connection` for the duration and counts, separating loopback | **yes** — any attempt is copied into the failure list with its target |

Why the split matters: a firewall can allow one port and drop another. On the
Windows box where #301 was found, `git clone git@github.com:...` worked over
port 22 while the single probe target `1.1.1.1:443` timed out. The old wording
turned that into `blocked`, a statement about the network that the probe had
never tested. The probe now reports *which* target answered, and "no probe target
answered (last: …)" when none did.

Conversely, an attempt is not a success or a failure — it is a fact about the
run. The guard counts attempts, not established connections, and does so once:
`create_connection` calls `socket.connect` internally, which used to be counted
twice. A positive control (`--self-test`, control 1) pins that.

## Evidence, two machines, one commit

Both runs are of the public repository at `46ca378`, from a clone made by the
documented command, with a clean virtual environment. Both machines had working
internet at the time — that is the point.

| machine | OS / python | probe line | driver attempts | verdict | exit | receipt sha256 |
|---|---|---|---|---|---|---|
| home workstation | Windows 11 / 3.13.15 | `reachable (github.com:443 answered)` | 0 (loopback 0) | ALL COMPARISONS MATCH | 0 | `40eb8144…c7de7a` |
| cloud host | Linux 6.6.95 / 3.12.11 | `reachable (1.1.1.1:443 answered)` | 0 (loopback 0) | ALL COMPARISONS MATCH | 0 | `4b577f8c…9a528a1` |

`python tools/reproduce_gate.py --self-test` passes on both without a checkout
of the corpus, so the guard can be checked before the numbers are:

| control | what it proves |
|---|---|
| one outbound attempt counts as one | nested `create_connection` → `connect` is not double-counted; a blocked run is not silently zero |
| loopback is separated from network use | a run talking to `127.0.0.1` is not reported as reaching the network |
| socket layer restored after uninstall | the guard leaves the process as it found it; a tool that keeps patching after it exits will corrupt whatever runs next |

## Boundary — what a reader must not infer

1. **Child processes are not instrumented.** `uibc verify`, `pytest` and the
   corpus builder run as subprocesses. The receipt says "driver attempted N",
   never "the run attempted N". A subprocess could in principle fetch a
   fixture; this receipt would not see it. That gap is stated on the receipt itself.
2. **Reachability is never evidence of isolation.** A run on an air-gapped
   machine and a run on a networked machine that made no attempt produce the
   same zero. The count is about attempts, not about capability.
3. **This says nothing about the inspection–execution gap.** The gate recomputes
   numbers from artifacts on disk. Whether a package behaves the same way once
   installed and run is outside this tool — see the "not guaranteed" section of
   `assurance-ceiling.html`.
4. **The runner is still the holder.** Two machines, one operator. This is
   evidence that the command works for a stranger-shaped setup, not that a
   stranger ran it. Evidence level stays E2; the register is where an outside
   row would come from.

## Reproducing this page

```
git clone https://github.com/zhaoxinghua09-cell/uibc-core.git && cd uibc-core
python -m venv .venv && . .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e .
python tools/reproduce_gate.py --self-test
python tools/reproduce_gate.py --repo . --uibc "$(command -v uibc)" \
       --profile docs/assurance/far-profile.json --out receipts
```

Expect: self-test PASS; a probe line naming the target that answered; `0` attempts
unless something in your environment reaches out; exit 0 with `ALL COMPARISONS
MATCH`. If attempts are non-zero, the receipt names the target and exits 1 —
that is the tool working, not failing.

## 中文摘要

这道门禁关于网络只主张一件事：**本次运行中，驱动进程零次外联**，所有数字都是从磁盘上的字节重新算出来的。它不主张"这台机器没有网"，也不主张"整个过程离线"。

两个事实分开：**探针**是机器的属性（信息，永不判失败，且报告是哪个目标应答了——因为防火墙可以放通 22 端口却丢 443）；**外联尝试次数**是本次运行的属性（计入失败清单并报出目标地址）。#300 之前把"可达"当失败，任何人带网跑都会被判 REPRODUCTION FAILED；#301 之前探针只测一个目标，把"22 端口能用"的机器报成 blocked。两次都是同一个错误：标签说的比测量多。

边界照实写：子进程未插桩（回执写"driver attempted N"）；可达性不是隔离证据；不覆盖"装上后行为如何"的 inspection–execution gap；跑的仍是持有人本人，证据等级仍是 E2，E4 需要外部一行。
