# SPDX-License-Identifier: Apache-2.0
"""atomic_write_json must survive a Windows read handle on its target.

Why this test exists: on 2026-11-21 the 200-writer concurrency test failed once
with

    PermissionError: [WinError 5] access denied:
    '...\\index.json.tmp-3752-...' -> '...\\index.json'

A reader had the index open for a few milliseconds. On Windows a replace fails
while any handle is open on the destination; on POSIX it succeeds. The one
portable fix is to retry the rename with a short backoff, because the rename is
still atomic and the window is bounded by the reader.

This test holds the target open deliberately for a bounded time, so it fails
without the retry instead of only failing when 200 threads happen to collide.

A note on the first draft of this test, kept because it was wrong in an
instructive way: it kept the file open until the write returned (reader waits
for the writer to finish, writer waits for the handle to close). That is a
deadlock, and no number of retries can win it. The retry is for a *bounded*
window, so the test must bound it too.
"""
import json
import os
import tempfile
import threading
import time
import unittest

from uibc_core.locking import atomic_write_json


class TestAtomicWriteSurvivesAnOpenReader(unittest.TestCase):
    def test_write_succeeds_while_the_target_is_open(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "index.json")
            atomic_write_json(path, {"version": 1})

            opened = threading.Event()

            def reader():
                with open(path, "rb") as fh:
                    opened.set()
                    time.sleep(0.12)      # bounded: the retry budget is ~1.5 s
                    fh.read()

            t = threading.Thread(target=reader)
            t.start()
            try:
                self.assertTrue(opened.wait(5), "reader never got the file open")
                atomic_write_json(path, {"version": 2})
            finally:
                t.join(5)

            with open(path, encoding="utf-8") as fh:
                self.assertEqual(json.load(fh), {"version": 2})
            # And no sibling temp file was left behind on the way out.
            self.assertEqual(sorted(os.listdir(d)), ["index.json"])


if __name__ == "__main__":
    unittest.main()
