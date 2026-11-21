"""Make the verifier a single file a stranger can run without installing anything.

Every "outsider" run in this repository so far still needed the repository: clone
it, then `python tools/...` imports `uibc_core` from the checkout. That is a
small dependency for us and a real obstacle for someone who was handed a package
and a URL.

A zipapp removes it. The result is one file:

    python3 uibc.pyz verify  package/          exit 0 = PASS
    python3 uibc.pyz explain package/          one line per check
    python3 uibc.pyz anchor  bundle/           ANCHORED, from an anchor outside

`anchor` is `tools/anchor_check.py`, so the two commands a reader needs - "is the
package consistent" and "is this the package the publisher signed" - live in the
same artifact. No pip, no network, no checkout.

Usage:  python3 tools/build_zipapp.py [--out dist/uibc.pyz]
"""
from __future__ import annotations

import os
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)

MAIN = '''import sys

if len(sys.argv) > 1 and sys.argv[1] == "anchor":
    sys.argv.pop(1)
    import anchor_check
    sys.exit(anchor_check.main())

from uibc_core.cli import main
main()
'''


def build(out_path):
    pkg_dir = os.path.join(REPO, "uibc_core")
    anchor = os.path.join(HERE, "anchor_check.py")
    entries = []
    for root, dirs, files in os.walk(pkg_dir):
        dirs[:] = [d for d in dirs if d != "__pycache__"]
        for f in files:
            if f.endswith(".pyc"):
                continue
            full = os.path.join(root, f)
            arc = os.path.relpath(full, REPO)
            entries.append((full, arc.replace(os.sep, "/")))

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    with zipfile.ZipFile(out_path, "w", zipfile.ZIP_DEFLATED) as z:
        # __main__ first: a zipapp runs the module named __main__
        z.writestr("__main__.py", MAIN)
        z.write(anchor, "anchor_check.py")
        for full, arc in entries:
            z.write(full, arc)
    return out_path


def main():
    out = os.path.join(REPO, "dist", "uibc.pyz")
    if "--out" in sys.argv:
        out = sys.argv[sys.argv.index("--out") + 1]
    path = build(out)
    print("built %s (%d bytes)" % (path, os.path.getsize(path)))
    print("")
    print("  python3 %s verify  <package>" % os.path.basename(path))
    print("  python3 %s anchor  <bundle>" % os.path.basename(path))
    print("")
    print("No uibc_core install, no network, no checkout required.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
