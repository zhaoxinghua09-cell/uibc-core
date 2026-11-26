"""The suite must hand back the tree it was given.

`tools/out/mutation_benchmark.json` is tracked and carries `meta.generated_at_utc`,
the clock. Anything that exercises the benchmark rewrites it, and the outsider
receipt speaks for the repository rather than for this disk - so "run the tests,
then check the receipt" used to be a sequence that failed for us and for a
stranger alike, with a `CONTENT` mismatch nobody could place. Restoring it at
session end keeps that sequence working without weakening the check: the receipt
still has to match every byte.
"""

import os

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WATCHED = ("tools/out/mutation_benchmark.json",)


@pytest.fixture(scope="session", autouse=True)
def _hand_back_tracked_artifacts():
    saved = {}
    for rel in WATCHED:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if os.path.exists(path):
            with open(path, "rb") as f:
                saved[rel] = f.read()
    yield
    for rel, data in saved.items():
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(path) or open(path, "rb").read() != data:
            with open(path, "wb") as f:
                f.write(data)
