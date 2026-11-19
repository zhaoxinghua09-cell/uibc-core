"""The published conformance archive must be the one the pin file names.

A hash published in prose drifts the moment someone rebuilds the archive and
forgets the number. This test makes the drift fail loudly: the archive in the
tree, the pin file and the case count all have to agree.

It also asserts the archive is *runnable* in the only way a test can cheaply
check: every file `run.py` needs at import time is inside it, and the manifest
it ships agrees with the case directories it ships.
"""
import hashlib
import json
import os
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARCHIVE = os.path.join(REPO, "conformance", "uibc-conformance-0.4.1.zip")
PIN = os.path.join(REPO, "anchors", "pins", "uibc-conformance-0.4.1.sha256")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_archive_exists():
    assert os.path.isfile(ARCHIVE), "the published conformance archive is missing"


def test_pin_names_the_same_bytes():
    with open(PIN, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    pinned = lines[0].split()[0]
    assert pinned == sha256(ARCHIVE), (
        "conformance archive does not match anchors/pins/uibc-conformance-0.4.1.sha256; "
        "either rebuild was published without updating the pin, or the pin is stale"
    )


def test_archive_is_self_contained():
    with zipfile.ZipFile(ARCHIVE) as z:
        names = set(z.namelist())
        for required in ("run.py", "manifest.json", "expected.json", "README.md"):
            assert required in names, "%s missing from the archive" % required
        # The archive stores files only, no directory entries: count the
        # distinct second path segment under cases/ instead.
        cases = sorted({n.split("/")[1] for n in names
                        if n.startswith("cases/") and n.count("/") >= 2})
        assert len(cases) == 36, "expected 36 case directories, found %d" % len(cases)

        manifest = json.loads(z.read("manifest.json"))
        assert len(manifest["cases"]) == 36
        # paths in the manifest are directories, relative to the archive root;
        # the archive has no directory entries, so check for files beneath them
        for case in manifest["cases"]:
            prefix = case["path"].rstrip("/") + "/"
            assert any(n.startswith(prefix) for n in names), (
                "%s points at a path with no files in the archive" % case["id"])

        expected = json.loads(z.read("expected.json"))
        assert len(expected["cases"]) == 36
        assert all("expect" in c for c in expected["cases"]), (
            "expected.json must normalise the expect/expectation split so a "
            "third-party runner does not have to discover it by KeyError"
        )
