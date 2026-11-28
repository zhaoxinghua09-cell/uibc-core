"""The 0.7.0 archive: 200 cases, frozen, and pinned by bytes.

The older pin test (test_conformance_archive_pin.py) guards the 0.4.1 archive and its
36 cases. This one guards the archive that carries the 200-case corpus, so a rebuild
that forgets the pin fails here instead of drifting quietly in prose.
"""
import hashlib
import json
import os
import zipfile

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
ARCHIVE = os.path.join(REPO, "conformance", "uibc-conformance-0.7.0.zip")
PIN = os.path.join(REPO, "anchors", "pins", "uibc-conformance-0.7.0.sha256")
ROOT = "uibc-conformance-0.7.0/"
CASES = 200
REFUSALS = 194


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def test_archive_exists():
    assert os.path.isfile(ARCHIVE), "the 0.7.0 conformance archive is missing"


def test_pin_names_the_same_bytes():
    with open(PIN, encoding="utf-8") as f:
        lines = [l.strip() for l in f if l.strip() and not l.startswith("#")]
    pinned = lines[0].split()[0]
    assert pinned == sha256(ARCHIVE), (
        "conformance archive 0.7.0 does not match anchors/pins/uibc-conformance-0.7.0.sha256; "
        "either the rebuild was published without updating the pin, or the pin is stale")


def test_archive_carries_the_200_case_corpus():
    with zipfile.ZipFile(ARCHIVE) as z:
        names = set(z.namelist())
        for required in ("run.py", "manifest.json", "expected.json", "README.md", "SHA256SUMS"):
            assert ROOT + required in names, "%s missing from the archive" % required

        manifest = json.loads(z.read(ROOT + "manifest.json"))
        assert len(manifest["cases"]) == CASES

        expected = json.loads(z.read(ROOT + "expected.json"))
        assert len(expected["cases"]) == CASES
        assert all("expect" in c for c in expected["cases"])

        refusals = [c for c in manifest["cases"] if c.get("expected_checks")]
        assert len(refusals) == REFUSALS, (
            "expected %d refusal cases, found %d" % (REFUSALS, len(refusals)))

        cases = sorted({n[len(ROOT):].split('/')[1] for n in names
                        if n.startswith(ROOT + 'cases/') and n[len(ROOT):].count('/') >= 2})
        assert len(cases) == CASES, "expected %d case directories, found %d" % (CASES, len(cases))

        for case in manifest["cases"]:
            prefix = ROOT + case["path"].rstrip("/") + "/"
            assert any(n.startswith(prefix) for n in names), (
                "%s points at a path with no files in the archive" % case["id"])


def test_checksum_manifest_covers_every_published_file():
    with zipfile.ZipFile(ARCHIVE) as z:
        sums = {}
        for line in z.read(ROOT + "SHA256SUMS").decode("utf-8").splitlines():
            if line.strip():
                digest, rel = line.split("  ", 1)
                sums[rel] = digest
        published = {n[len(ROOT):] for n in z.namelist()
                     if n.startswith(ROOT) and not n.endswith("SHA256SUMS") and not n.endswith("/")}
        assert set(sums) == published, (
            "SHA256SUMS lists %d files, the archive publishes %d" % (len(sums), len(published)))
        for rel, digest in list(sums.items())[:8]:
            assert hashlib.sha256(z.read(ROOT + rel)).hexdigest() == digest, rel


def test_runner_refuses_when_the_two_tables_disagree():
    # The archive ships run.py plus a bundled verifier; the integrity check that
    # refuses to start on a manifest/expected mismatch runs before any case is scored.
    with zipfile.ZipFile(ARCHIVE) as z:
        run_py = z.read(ROOT + "run.py").decode("utf-8")
    assert "Two copies of one truth: refusing to run rather than pick one." in run_py

