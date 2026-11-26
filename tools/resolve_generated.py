#!/usr/bin/env python3
"""Resolve a rebase conflict in the *generated* documents, by regenerating them.

Why this exists: `docs/EVIDENCE-INDEX.md` and `docs/EVIDENCE-DASHBOARD.svg` are
outputs of scripts. Every parallel branch regenerates them, so every merge
conflicts on them - and resolving by hand means retyping what a script would
have printed. Rounds have spent five rebases on this in one day.

What it does, during a conflicted rebase:

  1. read the conflicted paths from git
  2. for each path that a generator owns, re-run the generator and stage the
     result (the generator is the authority, not either side of the conflict)
  3. if any conflicted path is NOT a generator output, print it and exit 1 -
     a human has to decide, and this tool must not pretend otherwise

    python3 tools/resolve_generated.py            # act
    python3 tools/resolve_generated.py --dry-run  # list what it would do

Exit 0 only when every conflicted path was regenerated and staged.
"""
from __future__ import annotations

import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gitbin  # noqa: E402  (git may be a .cmd shim on Windows)

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# path -> command whose stdout (or file output) is that path's content.
# Anything not listed here is a human decision; the tool refuses to guess.
GENERATORS = {
    "docs/EVIDENCE-INDEX.md": ["tools/build_evidence_index.py"],
    "docs/EVIDENCE-DASHBOARD.svg": ["tools/run_all_evidence.py", "--online",
                                    "--svg", "docs/EVIDENCE-DASHBOARD.svg"],
}


def conflicted_paths():
    r = gitbin.run(["diff", "--name-only", "--diff-filter=U"],
                   cwd=REPO, capture_output=True, text=True)
    return [p.strip() for p in r.stdout.splitlines() if p.strip()]


def in_rebase():
    gitdir = gitbin.run(["rev-parse", "--git-dir"], cwd=REPO,
                        capture_output=True, text=True).stdout.strip()
    return any(os.path.isdir(os.path.join(REPO, gitdir, d))
               for d in ("rebase-merge", "rebase-apply"))


def regenerate(path):
    cmd = GENERATORS[path]
    r = subprocess.run([sys.executable] + cmd, cwd=REPO, capture_output=True, text=True,
                       timeout=900)
    return r.returncode, (r.stdout or "")[-2000:]


def main():
    dry = "--dry-run" in sys.argv
    if not in_rebase():
        print("NOT IN A REBASE - nothing to resolve. This tool only runs mid-rebase.")
        return 2
    paths = conflicted_paths()
    if not paths:
        print("NO CONFLICTS - commit or continue the rebase yourself.")
        return 2
    print("conflicted: %s" % ", ".join(paths))
    leftover = [p for p in paths if p not in GENERATORS]
    for p in paths:
        if p not in GENERATORS:
            print("  human decision needed: %s" % p)
            continue
        print("  regenerating: %s <- %s" % (p, " ".join(GENERATORS[p])))
        if dry:
            continue
        rc, out = regenerate(p)
        if rc != 0:
            print("  GENERATOR FAILED (rc=%d) for %s\n%s" % (rc, p, out))
            leftover.append(p)
            continue
        gitbin.run(["add", "--", p], cwd=REPO, check=False)
    if leftover:
        print("")
        print("VERDICT: INCOMPLETE - %d path(s) still need you: %s"
              % (len(leftover), ", ".join(leftover)))
        return 1
    print("")
    print("VERDICT: ALL CONFLICTS WERE GENERATED - staged. Next: git rebase --continue")
    print("(If the rebase then complains about unstaged changes under conformance/, "
          "those are test by-products: git checkout -- conformance/ && git clean -fd conformance/cases)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
