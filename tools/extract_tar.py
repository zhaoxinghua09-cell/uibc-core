"""Extract a GitHub tarball without mangling non-ASCII member names.

Why: on Windows, `bsdtar` (the `tar` that ships with the OS) decodes member
names in the archive's header encoding and can turn `运行日志` into
`杩愯鏃ュ織` and `résumé` into `r茅sum茅`. The bytes are fine; the names are not.
A verifier then reports a case like `accept-unicode-names` as FAIL with a
*hash mismatch*, which looks like a verifier defect and is not one.

`git clone` does not have this problem (it takes its file names from tree
objects, not from a header string). If a reader only has the tarball, this
script reads each header name with the encoding the GitHub writer used (UTF-8)
and refuses to write anything when a name would not survive as valid UTF-8.

Usage:
  python tools/extract_tar.py uibc-core-<ref>.tar.gz --dest DIR

Exit: 0 extracted; 2 archive cannot be read or would produce mangled names.
"""

import argparse
import os
import sys
import tarfile


def _safe_members(tf, dest):
    for m in tf.getmembers():
        target = os.path.realpath(os.path.join(dest, m.name))
        if not target.startswith(os.path.realpath(dest) + os.sep):
            raise ValueError("member escapes the destination: " + m.name)
        try:
            m.name.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError(
                "member name is not valid UTF-8: %r - the archive was re-encoded "
                "somewhere; use git clone instead" % m.name
            )
        yield m


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("archive")
    p.add_argument("--dest", required=True)
    a = p.parse_args(argv)

    if not os.path.isfile(a.archive):
        print("archive not found: " + a.archive, file=sys.stderr)
        return 2
    os.makedirs(a.dest, exist_ok=True)
    try:
        with tarfile.open(a.archive, "r:gz", encoding="utf-8") as tf:
            tf.extractall(a.dest, members=_safe_members(tf, a.dest), filter="data")
    except (tarfile.TarError, ValueError, OSError) as exc:
        print("cannot extract: %s" % exc, file=sys.stderr)
        return 2

    roots = [d for d in os.listdir(a.dest) if os.path.isdir(os.path.join(a.dest, d))]
    print("extracted %d member(s); top-level directories: %s"
          % (sum(1 for _ in tarfile.open(a.archive, "r:gz")), ", ".join(roots)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
