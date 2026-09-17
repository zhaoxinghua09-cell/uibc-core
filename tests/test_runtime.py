"""Runtime hook tests (task G23). One-line wrappers over the CLI functions."""

import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import cli as ucli
from uibc_core.runtime import event, record_action, seal, snapshot  # noqa: E402
from uibc_core.signing import generate_key  # noqa: E402
from uibc_core.verify import verify  # noqa: E402


def _ready_pkg(tmp, name="r.uibc"):
    pkg = os.path.join(tmp, name)
    ucli.cmd_init(type("A", (), {"path": pkg})())
    ucli.cmd_register(type("A", (), {
        "path": pkg, "agent_id": "rt-agent", "owner": "rt-owner",
        "agent_type": "software-agent", "version": "1"})())
    return pkg


class RuntimeHookTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="rt-")
        self.pkg = _ready_pkg(self.tmp)
        self.key = generate_key()
        self.kf = os.path.join(self.tmp, "owner.key")
        with open(self.kf, "w", encoding="ascii") as f:
            f.write(self.key.hex())

    # 1. record_action records a real file and verify stays PASS
    def test_01_record_action_then_verify(self):
        src = os.path.join(self.tmp, "log.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("agent did the thing\n")
        seal(self.pkg, None)
        record_action(self.pkg, src, note="did the thing")
        seal(self.pkg, self.kf)
        r = verify(self.pkg, key=self.key)
        self.assertEqual(r["result"], "PASS")

    # 2. media_type inference: txt -> text/plain
    def test_02_media_type_inference(self):
        src = os.path.join(self.tmp, "data.csv")
        with open(src, "w", encoding="utf-8") as f:
            f.write("a,b\n1,2\n")
        idx_path = os.path.join(self.pkg, "evidence", "index.json")
        with open(idx_path, "r", encoding="utf-8") as f:
            before = len(json.load(f)["entries"])
        record_action(self.pkg, src)
        with open(idx_path, "r", encoding="utf-8") as f:
            entries = json.load(f)["entries"]
        self.assertEqual(len(entries), before + 1)
        self.assertEqual(entries[-1].get("media_type"), "text/csv")

    # 3. missing package -> honest FileNotFoundError
    def test_03_missing_package(self):
        with self.assertRaises(FileNotFoundError):
            record_action(os.path.join(self.tmp, "ghost.uibc"), self.kf)

    # 4. missing evidence file -> honest FileNotFoundError
    def test_04_missing_evidence_file(self):
        with self.assertRaises(FileNotFoundError):
            record_action(self.pkg, os.path.join(self.tmp, "nope.txt"))

    # 5. event() appends a valid lifecycle event (S3 stays green)
    def test_05_event_valid_type(self):
        from uibc_core.runtime import record_action
        src = os.path.join(self.tmp, "log.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("pre-event evidence\n")
        record_action(self.pkg, src)
        seal(self.pkg, self.kf)
        event(self.pkg, "ACTIVATE", "rt-agent")
        seal(self.pkg, self.kf)
        r = verify(self.pkg, key=self.key)
        self.assertEqual(r["result"], "PASS")

    # 6. event() rejects nothing at wrapper level, but S3 catches junk later
    def test_06_event_junk_type_caught_by_s3(self):
        event(self.pkg, "NOT_A_REAL_EVENT", "rt-agent")
        seal(self.pkg, self.kf)
        r = verify(self.pkg, key=self.key)
        self.assertEqual(r["result"], "FAIL")

    # 7. snapshot writes a timestamped JSON and it passes verification
    def test_07_snapshot_roundtrip(self):
        seal(self.pkg, None)
        fp = snapshot(self.pkg, {"action": "answer_user",
                                 "question": "meaning of life",
                                 "answer": "42"}, key_file=self.kf)
        self.assertTrue(os.path.isfile(fp))
        r = verify(self.pkg, key=self.key)
        self.assertEqual(r["result"], "PASS")

    # 8. snapshot honors recorded_at override (deterministic evidence)
    def test_08_snapshot_recorded_at_respected(self):
        fp = snapshot(self.pkg, {"action": "x", "recorded_at": "2000-01-01T00:00:00Z"})
        with open(fp, "r", encoding="utf-8") as f:
            self.assertEqual(json.load(f)["recorded_at"], "2000-01-01T00:00:00Z")

    # 9. tampering after record_action is caught (the whole point)
    def test_09_tamper_after_record_caught(self):
        src = os.path.join(self.tmp, "log.txt")
        with open(src, "w", encoding="utf-8") as f:
            f.write("honest\n")
        record_action(self.pkg, src)
        seal(self.pkg, self.kf)
        # tamper with the copy INSIDE the package (the source is a duplicate)
        files = os.path.join(self.pkg, "evidence", "files")
        victim = sorted(os.listdir(files))[0]
        with open(os.path.join(files, victim), "a", encoding="utf-8") as f:
            f.write("forged\n")
        r = verify(self.pkg, key=self.key)
        self.assertEqual(r["result"], "FAIL")


if __name__ == "__main__":
    unittest.main()
