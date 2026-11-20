"""The signing chain must be wired, not merely described.

On 2026-11-20 a PR merged the anchoring tool and its tests while its workflow edit and
two document edits were silently reverted during a conflict resolution. The PR
description said the release workflow signs and attaches `.sig` / `.tsr` / `UNSIGNED.txt`;
the tree said otherwise, and nothing failed. That is the defect these tests exist for:
a claim in a description has to be a fact in the tree.
"""

import os
import re

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(REPO, ".github", "workflows", "release-lab-bundle.yml")

# The sdist ships the package and its docs, not `.github`. A suite run from an unpacked
# archive has no workflow to read, and a FileNotFoundError here would report "the chain
# is broken" when the only fact is that this tree never had the workflow. Measured in CI
# on 2026-11-20: five of these failed with FileNotFoundError inside the sdist job.
pytestmark = pytest.mark.skipif(
    not all(os.path.isfile(p) for p in (
        WORKFLOW,
        os.path.join(REPO, "docs", "LAB-PROTOCOL.md"),
        os.path.join(REPO, "docs", "COMPETITIVE-STATE.md"),
        os.path.join(REPO, "tools", "anchor_release_digests.py"))),
    reason=".github/workflows is not shipped in the sdist; this guard runs in a checkout")


def workflow():
    with open(WORKFLOW, encoding="utf-8") as fh:
        return fh.read()


def test_the_workflow_calls_the_signing_tool():
    text = workflow()
    assert "tools/anchor_release_digests.py sign" in text
    assert "tools/anchor_release_digests.py verify" in text


def test_the_workflow_reads_the_seed_from_a_secret_and_never_echoes_it():
    text = workflow()
    assert "${{ secrets.UIBC_RELEASE_SEED_HEX }}" in text
    # No `echo $SEED` and no line that prints the variable into the log.
    assert not re.search(r"echo\s+\"\$?SEED\"", text)
    assert "set -x" not in text


def test_a_release_without_a_seed_ships_an_unsigned_marker():
    text = workflow()
    assert "release/UNSIGNED.txt" in text
    assert "NOT signed" in text


def test_both_anchors_are_attempted_and_their_state_is_shown():
    text = workflow()
    assert "tools/anchor_release_digests.py anchor" in text
    assert "release/ANCHORS.json" in text


def test_every_optional_artifact_is_attached_only_when_it_exists():
    text = workflow()
    for artifact in ("CORPUS-DIGESTS.txt.sig", "anchor_freetsa.tsr", "anchor_freetsa_ca.pem",
                     "CORPUS-DIGESTS.txt.ots", "ANCHORS.json", "UNSIGNED.txt"):
        assert artifact in text, artifact
    assert "not attached (absent)" in text


def test_the_documents_do_not_claim_the_chain_has_run_on_a_release():
    protocol = open(os.path.join(REPO, "docs", "LAB-PROTOCOL.md"), encoding="utf-8").read()
    state = open(os.path.join(REPO, "docs", "COMPETITIVE-STATE.md"), encoding="utf-8").read()
    assert "has not run on a published release yet" in protocol
    assert "发布侧未验证" in state or "not yet exercised" in state.lower()
    # The stale sentence this fixed: a page saying we ship no signature at all while a
    # tool that signs sits in the tree.
    assert "没有签名、没有 OTS、没有 RFC 3161" not in state


def test_the_demo_seed_is_still_refused_by_the_tool():
    code = open(os.path.join(REPO, "tools", "anchor_release_digests.py"), encoding="utf-8").read()
    assert "PUBLIC_SEEDS" in code
    assert "refusing to sign with the public demo seed" in code
