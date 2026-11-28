"""The silent set is frozen. A new field that nothing notices fails the build.

F-007 and F-008 were both fields the package writes and no check reads. Watching
for the next one by hand does not scale, so this test fixes the current list and
fails if it grows. Every entry below has a reason; a field added to the schema
without a reason is exactly the defect this guards against.
"""
import json
import os
import shutil
import sys
import tempfile
import unittest

_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, _REPO)
sys.path.insert(0, os.path.join(_REPO, "tools"))

from uibc_core.verify import verify  # noqa: E402

BASE = os.path.join(_REPO, "fixtures", "clean.uibc")

# Descriptive: changing it changes no verdict, and should not.
# `evidence/index.json/entries[n]/media_type` moved OUT of this list on 2026-11-28:
# S20 now refuses a declared media type outside the accepted vocabulary, so the
# field is no longer silent. (It stays out of the S7 digest on purpose - S20
# binds the label, not the bytes, which S4 already covers.)
DESCRIPTIVE = {
    "manifest.json/schema", "manifest.json/agent_version",
    "identity.json/schema", "identity.json/version", "identity.json/agent_type",
    "lifecycle.json/schema",
    "evidence/index.json/entries[0]/note",
    "evidence/index.json/entries[1]/note",
    "signatures/seal.json/schema", "signatures/seal.json/created_at",
}

# Unreferenced: a value nothing else points at, so altering it contradicts nothing.
# IDs are not checked for uniqueness either - stated here rather than implied.
UNREFERENCED = {
    "lifecycle.json/events[2]/event_id",
    "evidence/index.json/entries[0]/evidence_id",
    "evidence/index.json/entries[1]/evidence_id",
}

# Undecidable without material the package does not carry: an HMAC seal with a
# secret we do not hold, or per-event signatures the format does not define.
UNDECIDABLE = {
    "lifecycle.json/events[0]/signature",
    "lifecycle.json/events[1]/signature",
    "lifecycle.json/events[2]/signature",
    "signatures/seal.json/key_id",
    "signatures/seal.json/signature",
    "signatures/seal.json/signed",
}

# Known gaps: enums nothing validates yet. Listed so they are not forgotten,
# not so they are excused.
KNOWN_GAPS = {
    "manifest.json/status",
    "identity.json/status",
}

SILENT_ALLOWED = DESCRIPTIVE | UNREFERENCED | UNDECIDABLE | KNOWN_GAPS


class TestFieldCoverage(unittest.TestCase):
    def test_the_silent_set_has_not_grown(self):
        from check_field_coverage import probe

        (_, _base), results = probe()
        silent = {r["field"] for r in results if not r["moved"]}
        grew = silent - SILENT_ALLOWED
        self.assertEqual(
            sorted(grew), [], "fields no check notices, and no reason on record: "
            + ", ".join(sorted(grew)))
        stale = SILENT_ALLOWED - silent
        self.assertEqual(sorted(stale), [],
                         "listed as silent but a check now notices: "
                         + ", ".join(sorted(stale)))

    def _with_index_edit(self, fn):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        path = os.path.join(pkg, "evidence/index.json")
        doc = json.load(open(path, encoding="utf-8"))
        fn(doc)
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        return {c["id"]: c for c in verify(pkg)["checks"]}

    def test_a_repeated_evidence_id_fails_semantics(self):
        """Structural (S4) or semantic (S12)?

        2026-11-19 decision: semantic. A repeated entry still names a readable
        file whose hash matches, so the evidence root can be computed and the
        duplicate is caught by the root itself (S5) - which is what
        benchmarks.md promises for fixture duplicated.uibc. Filing it under S4
        made the reference answer INCONCLUSIVE there while the independent
        implementation answered FAIL, i.e. two answers to one spec.
        """
        checks = self._with_index_edit(
            lambda d: d["entries"][1].__setitem__("evidence_id",
                                                  d["entries"][0]["evidence_id"]))
        self.assertEqual(checks["S12"]["result"], "FAIL", checks["S12"]["detail"])
        self.assertIn("duplicate evidence_id", checks["S12"]["detail"])

    def test_an_empty_evidence_id_fails_semantics(self):
        checks = self._with_index_edit(
            lambda d: d["entries"][0].__setitem__("evidence_id", ""))
        self.assertEqual(checks["S12"]["result"], "FAIL", checks["S12"]["detail"])
        self.assertIn("evidence_id", checks["S12"]["detail"])

    def test_a_declared_payload_hash_has_a_shape(self):
        tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, tmp, True)
        pkg = os.path.join(tmp, "pkg")
        shutil.copytree(BASE, pkg)
        path = os.path.join(pkg, "lifecycle.json")
        doc = json.load(open(path, encoding="utf-8"))
        doc["events"][0]["payload_hash"] = "not-a-hash"
        json.dump(doc, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        checks = {c["id"]: c for c in verify(pkg)["checks"]}
        self.assertEqual(checks["S12"]["result"], "FAIL", checks["S12"]["detail"])
        self.assertIn("payload_hash", checks["S12"]["detail"])


if __name__ == "__main__":
    unittest.main()
