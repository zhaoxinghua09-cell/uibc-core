"""The vendored documents are the evidence, so they are held like evidence.

Three things are asserted: every file on disk is described in the manifest, every
recorded hash still matches the bytes, and every quoted clause points at a document the
manifest covers. Without the first one a new file could sit unexamined; without the third
a quote could cite a document that was never vendored at all.
"""
import hashlib
import io
import json
import os
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
SRC = os.path.join(REPO, "docs", "spec-sources")
MANIFEST = os.path.join(SRC, "MANIFEST.json")


def sha(path):
    return hashlib.sha256(io.open(path, "rb").read()).hexdigest()


class TestVendoredSources(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docs = json.load(io.open(MANIFEST, encoding="utf-8"))["documents"]
        cls.grounds = json.load(io.open(
            os.path.join(REPO, "conformance", "oracle", "grounds.json"), encoding="utf-8"))["cases"]

    def test_every_file_on_disk_is_described(self):
        on_disk = {n for n in os.listdir(SRC)
                   if n.endswith(".txt")}
        described = {d["file"] for d in self.docs}
        self.assertEqual(sorted(on_disk), sorted(described),
                         "an unexamined document is worse than no document")

    def test_every_recorded_hash_matches_the_bytes(self):
        for doc in self.docs:
            path = os.path.join(SRC, doc["file"])
            self.assertEqual(sha(path), doc["sha256"], doc["file"])
            self.assertEqual(os.path.getsize(path), doc["bytes"], doc["file"])

    def test_every_document_names_where_it_came_from(self):
        for doc in self.docs:
            self.assertRegex(doc["url"], r"^https://", doc["file"])

    def test_every_quoted_clause_points_at_a_vendored_document(self):
        listed = {"docs/spec-sources/" + d["file"] for d in self.docs}
        for row in self.grounds:
            if row.get("clause_source"):
                self.assertIn(row["clause_source"], listed, row["check"])

    def test_the_manifest_records_what_upstream_served(self):
        """Local hashes alone cannot show the file was not edited here."""
        for doc in self.docs:
            self.assertIn("upstream_sha256", doc, doc["file"])
            self.assertTrue(doc.get("upstream_stable"), doc["file"])
            self.assertTrue(doc.get("local_equals_upstream"),
                            "%s: vendored copy differs from what the publisher served"
                            % doc["file"])


if __name__ == "__main__":
    unittest.main()
