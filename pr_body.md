The rerun used to say "PASS" without saying on what. A stranger on another machine
could not tell whether the four steps passed because the tree was sound or because
this machine happened to have the right things installed. That is a request to
trust the host, not the receipt, and the external reviewer said so.

This branch records the host instead of assuming it:

- `PYTHONHASHSEED=0` — Python is told in advance that the hash seed is fixed, so
  set iteration order cannot shift the output between runs or between machines.
- `PYTHONNOUSERSITE=1` — the per-user `site-packages` directory is off, so a package
  someone pip-installed for themselves cannot quietly decide the outcome.
- `PYTHONPATH` emptied — nothing from the author's shell leaks into the run.
- The interpreter is named in the receipt: implementation and version.
- `environment.distributions` lists, as `name==version`, every third-party package
  that was installed at the time of the run, and the page prints the count plus a
  sha256 of that list, so the exact set can be compared without reading 246 lines.

The page now says plainly that a different machine only needs the same Python
version with pytest present, and that if the asserted strings differ the difference
is in the environment and not in the receipt.

Everything is re-sealed in the fixed order — manifest, evidence index, inventory,
receipt, board — and the receipt describes this commit: 2552 files,
`015da7e90b10`, content `71795231fde3`, 4 steps, all passing.

What a stranger does:

```
git clone https://github.com/zhaoxinghua09-cell/uibc-core && cd uibc-core
python tools/outsider_rerun.py --run
```

They should see four `PASS` lines, the asserted strings listed on the page, and a
receipt whose `tree_sha256` equals `015da7e90b10…` when read from the commit.
