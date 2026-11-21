#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Push through the account gate. The only sanctioned way to push this repo.

Git hooks depend on a file bit that Windows does not really have, and a safety
check that silently does not run is worse than none: on 2026-11-17 the pre-push
hook was installed, the push went out, and no gate line ever appeared. So the
gate is also a wrapper - `python tools/push_safe.py [...]` runs the check first
and only then invokes `git push`.

    python tools/push_safe.py                      # push the current branch
    python tools/push_safe.py origin other-branch  # same arguments as git push
"""
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)


def main(argv=None):
    argv = list(argv if argv is not None else sys.argv[1:])
    gate = subprocess.run([sys.executable, os.path.join(HERE, "pre_push_gate.py")],
                          cwd=ROOT, text=True, capture_output=True)
    out = (gate.stdout or "") + (gate.stderr or "")
    print(out.strip())
    if gate.returncode != 0:
        print("PUSH ABORTED: account gate failed. Nothing was sent.")
        return gate.returncode

    cmd = ["git", "push"] + (argv if argv else ["origin", "HEAD"])
    print("gate passed -> %s" % " ".join(cmd))
    rc = subprocess.call(cmd, cwd=ROOT)
    if rc != 0:
        print("push failed rc=%d (gate already passed; this is the network/remote, "
              "not the account)" % rc)
    return rc


if __name__ == "__main__":
    sys.exit(main())
