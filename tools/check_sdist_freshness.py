#!/usr/bin/env python3
"""check_sdist_freshness -- refuse an sdist that still carries the previous version's corpus.

Why this exists: 0.5.4 shipped with exactly this defect. Its sdist still had the
oracle corpus saying 0.5.3, so sdist-self-check stayed red on main (#460). The
release gate compared the archive against the tree but never asked whether the
sdist's corpus belonged to this version at all.

    python tools/check_sdist_freshness.py --sdist uibc_core-0.5.5.tar.gz --version 0.5.5

Exit codes: 0 PASS / 2 FAIL (stale strings found) / 3 INCONCLUSIVE (unreadable file)
"""
import argparse, re, sys, tarfile

SCOPE = ("conformance/", "uibc_core/")     # the content area that changes with the version
EXEMPT = ("CHANGELOG", "docs/COMPETITORS", "tests/test_release_readiness", "tools/check_release_readiness")  # legitimately mention old versions


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sdist", required=True)
    ap.add_argument("--version", required=True)
    ap.add_argument("--check-versions", default=None,
                    help="要查的旧版本串，逗号分隔；默认按 --version 推前一位（1.2.3 → 1.2.2）")
    a = ap.parse_args()

    old = a.check_versions
    if not old:
        parts = a.version.split(".")
        prev = "%s.%d" % (".".join(parts[:-1]), max(int(parts[-1]) - 1, 0))
        old = prev
    olds = [x.strip() for x in old.split(",") if x.strip()]

    try:
        tf = tarfile.open(a.sdist)
    except Exception as e:
        print("INCONCLUSIVE  cannot open the sdist: %s" % e)
        return 3

    hits = []
    for m in tf.getmembers():
        if not m.isfile() or not m.name.endswith((".json", ".py", ".toml", ".md", ".txt")):
            continue
        name = m.name.split("/", 1)[-1]
        if not name.startswith(SCOPE) or any(e in name for e in EXEMPT):
            continue
        try:
            data = tf.extractfile(m).read().decode("utf-8", "ignore")
        except Exception:
            continue
        for v in olds:
            if re.search(r"(?<![0-9.])%s(?![0-9])" % re.escape(v), data):
                hits.append((name, v))

    print("sdist %s | version %s | looking for %s | %d hit(s)"
          % (a.sdist.split("/")[-1], a.version, ",".join(olds), len(hits)))
    for n, v in hits[:8]:
        print("   %s carries %s" % (n, v))
    if hits:
        print("FAIL  the sdist carries strings from the previous version "
              "(published, this is what made 0.5.4 red)")
        return 2
    print("PASS  no stale version strings in the content area")
    return 0


if __name__ == "__main__":
    sys.exit(main())
