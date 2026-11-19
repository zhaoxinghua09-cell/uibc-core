"""A pin must be resolvable by someone who has only the pin.

Three things can go wrong with a pinned hash, and only the first is usually tested:

1. the hash does not match the bytes we hold            (self-consistency)
2. the bytes were never published                       (nothing to hash)
3. the pin names a file, but not where that file lives  (hash unresolvable)

Case 3 is the one that bit a competitor's pin on 2026-11-20: their bundle and tree
hashes resolved, their manifest hash did not, and no reader could tell whether the
file had moved, been regenerated, or never existed. Our own conformance pin named
a basename only, which is the same failure in a milder form: correct hash, no
path.

So: every entry in anchors/pins/*.sha256 must either
  (a) name a repository-relative path that exists here and hashes to the pin, or
  (b) have a source URL in the same file whose basename matches the entry, so the
    bytes can be fetched and hashed elsewhere.

Basename-only entries fail, because a reader cannot resolve them.
"""
import hashlib
import os
import re
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PINS = os.path.join(_REPO, "anchors", "pins")
ENTRY = re.compile(r"^([0-9a-f]{64})\s+(\S+)\s*$")


def _entries(text):
    out = []
    for line in text.splitlines():
        m = ENTRY.match(line.strip())
        if m:
            out.append((m.group(1), m.group(2)))
    return out


def _sha256(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def _urls(text):
    return [w for w in re.findall(r"https?://\S+", text)]


class TestPinsAreResolvable(unittest.TestCase):
    def test_every_pin_resolves_to_bytes_someone_else_can_hash(self):
        names = sorted(n for n in os.listdir(PINS) if n.endswith(".sha256"))
        self.assertTrue(names, "no pin files found")
        for name in names:
            with open(os.path.join(PINS, name), encoding="utf-8") as f:
                text = f.read()
            entries = _entries(text)
            self.assertTrue(entries, "%s carries no hash entries" % name)
            urls = _urls(text)
            for digest, target in entries:
                repo_path = os.path.join(_REPO, target)
                if os.path.isfile(repo_path):
                    self.assertEqual(
                        _sha256(repo_path), digest,
                        "%s: %s does not hash to the pinned value" % (name, target))
                    continue
                # not in the repo: it must be pinnable to a published URL
                matching = [u for u in urls if u.rstrip("/").endswith(target)]
                if matching:
                    continue
                self.assertNotEqual(
                    target, os.path.basename(target),
                    "%s: entry %r is not in this repository and no source URL in "
                    "this file ends with it - the hash cannot be resolved by a "
                    "reader who has only this file" % (name, target))
                self.fail("%s: entry %r has a path but the file is missing"
                          % (name, target))

    def test_the_audit_kit_names_the_same_path_the_pin_names(self):
        """A reader starts at AUDIT-KIT; the pin it points to must use the path
        AUDIT-KIT shows, or the two documents disagree about where the bytes are."""
        with open(os.path.join(_REPO, "docs", "AUDIT-KIT.md"), encoding="utf-8") as f:
            audit = f.read()
        with open(os.path.join(PINS, "uibc-conformance-0.4.1.sha256"),
                  encoding="utf-8") as f:
            pin = f.read()
        entries = _entries(pin)
        self.assertEqual(len(entries), 1, "expected one archive entry")
        _, target = entries[0]
        self.assertIn(target, audit,
                      "AUDIT-KIT does not name %r, so a reader following the pin "
                      "cannot find the file" % target)


if __name__ == "__main__":
    unittest.main()
