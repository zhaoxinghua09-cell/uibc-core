# One-click run, for people who will not install anything

The three commands in the README assume a shell, a Python, and a willingness to
type. Some readers stop at the first of those. This page exists for them.

## Option A: click once on a machine neither side controls

Open **Actions → one-click outsider run → Run workflow**.

<https://github.com/zhaoxinghua09-cell/uibc-core/actions/workflows/one-click.yml>

The run page then shows the verdict line, the commit it ran on, the Python
version, and the sha256 of the result file. The result file is attached to the
run and kept for 90 days.

What this is: a public, timestamped run on GitHub's hosted runner.
What this is not: a third-party human node. Nobody's name is attached and no
person decided anything, so it does not move the count in
[`EXTERNAL-NODES.md`](EXTERNAL-NODES.md). Machine runs are logged as machine
runs; the register stays about people.

## Option B: open a browser session and read the line yourself

Open the repository in Codespaces (Code → Codespaces → Create codespace on
`main`). The container starts, the check runs on attach, and the verdict line
appears in the terminal. No account beyond the one you already have, nothing
installed locally.

## Option C: the command, for completeness

```
git clone --depth 1 https://github.com/zhaoxinghua09-cell/uibc-core.git
cd uibc-core
python3 tools/external_node_check.py --out external_node_result.json
```

Whatever route you take, the expected shape of the output is one line:

```
independent=PASS  reference=PASS(<ms>)  probes=3/3 rejected  -> CONSISTENT
```

If it says `DISCREPANCY`, that is the more useful result. Send the file back and
it gets recorded as a failed attempt, in your words or as an anonymous runner.
