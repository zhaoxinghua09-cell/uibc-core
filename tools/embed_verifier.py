#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Put a dependency-free verifier INSIDE the package (the shape AIVS ships).

Why: `draft-stone-aivs-01` puts a self-check script directly in the archive, so a
recipient needs nothing but python3. Ours required cloning a repo. This closes
that shape gap without touching the evidence:

    python tools/embed_verifier.py <package_dir>
    python <package_dir>/verify/run.py

It writes three files under `<pkg>/verify/`: `iverify.py` (verbatim copy of the
independent implementation, stdlib only), `run.py`, `README.md`.

Two things this deliberately does NOT do:
  * it does not re-seal anything - the embedded script is UNSIGNED, and adding it
    must not change the verdict, the evidence root or the checkpoint head;
  * it does not make the package more trustworthy. A verifier inside the package
    is a convenience, exactly as in AIVS: if you do not trust the sender, you do
    not trust their script either. Use your own copy when it matters.
"""
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "independent_verifier", "iverify.py")

RUN_PY = '''#!/usr/bin/env python3
"""Verify the package that contains this directory. Standard library only."""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from iverify import independent_verify

pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
report = independent_verify(pkg)
print(json.dumps(report, ensure_ascii=False, indent=2))
sys.exit({"PASS": 0, "FAIL": 1}.get(report["result"], 2))
'''

README = """# verify/ - embedded self-check

Run it with nothing installed but python3:

    python verify/run.py

Exit code: 0 = PASS, 1 = FAIL, 2 = INCONCLUSIVE.

This script is **not covered by the package seal**. It is a copy of the
independent implementation (`independent_verifier/iverify.py`, same version) and
its presence does not change the verdict, the evidence root or the checkpoint
head. Treat it as convenience, not as provenance: a sender who wants to fool you
can ship a modified script. Compare its hash against the published repository
copy before relying on it.

Checks performed (parity with the reference implementation's S1-S9): V1 required
files, V2 identity, V3 lifecycle, V4 per-file hash, V5 evidence root, V6 seal,
V7 undeclared root files, V8 index metadata digest, V9 checkpoint head.
"""


def main(pkg_dir):
    if not os.path.isdir(pkg_dir):
        print("not a directory: %s" % pkg_dir)
        return 2
    dst = os.path.join(pkg_dir, "verify")
    os.makedirs(dst, exist_ok=True)
    shutil.copyfile(SRC, os.path.join(dst, "iverify.py"))
    with open(os.path.join(dst, "run.py"), "w", encoding="utf-8", newline="\n") as f:
        f.write(RUN_PY)
    with open(os.path.join(dst, "README.md"), "w", encoding="utf-8", newline="\n") as f:
        f.write(README)
    print("embedded verifier written to %s" % dst)
    print("run: python %s" % os.path.join(dst, "run.py"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "."))
