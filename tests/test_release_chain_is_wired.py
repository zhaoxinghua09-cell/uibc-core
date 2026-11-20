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


def test_the_workflow_opens_a_release_when_the_tag_has_none():
    """A tag push does not create a release, and `gh release upload` fails without one.

    Measured 2026-11-20: the repository carried a v0.4.1 tag and no v0.4.1 release, which
    is why the newest release asset for this corpus was 0.4.0 — the workflow had nowhere
    to attach. The step must check first and create only when the check fails.
    """
    text = workflow()
    assert "gh release view" in text
    assert "gh release create" in text
    assert "--generate-notes" in text
    view_at = text.index("gh release view")
    create_at = text.index("gh release create")
    assert view_at < create_at, "the view check must come before the create"
    # `if gh release view ...` on one line, then the create inside the else branch.
    assert re.search(r"if\s+gh release view", text), "the view must be the condition itself"
    assert "else" in text[view_at:create_at], "the create must sit in the else branch"


def test_the_attach_step_uses_the_same_tag_the_check_used():
    text = workflow()
    assert text.count("${{ steps.v.outputs.tag }}") >= 3


def test_the_archive_itself_is_attached():
    """Measured 2026-11-20: the first real run uploaded five files and no archive, so a
    reader on the release page still could not download the corpus."""
    text = workflow()
    assert "release/uibc-conformance-${{ steps.v.outputs.version }}.zip" in text


def test_the_anchors_have_their_dependency_installed():
    """Without asn1crypto the TSA request cannot be built at all: measured 2026-11-20,
    the published ANCHORS.json said `NameError: name 'tsp' is not defined`."""
    text = workflow()
    assert "pip install" in text
    assert "asn1crypto" in text


def test_an_unstartable_verifier_is_not_a_tsa_refusal():
    tool = open(os.path.join(REPO, "tools", "anchor_release_digests.py"), encoding="utf-8").read()
    assert 'elif code == 3' in tool
    assert '"state": "unavailable"' in tool


def test_every_optional_artifact_is_attached_only_when_it_exists():
    text = workflow()
    for artifact in ("CORPUS-DIGESTS.txt.sig", "anchor_freetsa.tsr", "anchor_freetsa_ca.pem",
                     "CORPUS-DIGESTS.txt.ots", "ANCHORS.json", "UNSIGNED.txt"):
        assert artifact in text, artifact
    assert "not attached (absent)" in text


def test_the_documents_say_the_chain_ran_once_and_do_not_claim_more_than_that():
    """The premise flipped on 2026-11-20 when the chain actually ran.

    Before that, this test asserted the documents said it had *not* run — that was
    the honest state then. Workflow run 44671945364 attached a FreeTSA token to
    v0.4.1, so the sentence became false. The test now holds the new claim to the
    same standard: the documents must say it ran once, must name the run, and must
    not claim a signature the release does not carry.
    """
    protocol = open(os.path.join(REPO, "docs", "LAB-PROTOCOL.md"), encoding="utf-8").read()
    state = open(os.path.join(REPO, "docs", "COMPETITIVE-STATE.md"), encoding="utf-8").read()
    assert "has not run on a published release yet" not in protocol
    assert "44671945364" in protocol
    assert "anchored" in protocol
    # No signature is on the release, so no document may say one is.
    assert "UIBC_RELEASE_SEED_HEX" in protocol
    assert "已实现、本地实测通过、发布侧未验证" not in state
    assert "三件缺一" in state
    # The stale sentence this fixed: a page saying we ship no signature at all while a
    # tool that signs sits in the tree.
    assert "没有签名、没有 OTS、没有 RFC 3161" not in state


def test_the_demo_seed_is_still_refused_by_the_tool():
    code = open(os.path.join(REPO, "tools", "anchor_release_digests.py"), encoding="utf-8").read()
    assert "PUBLIC_SEEDS" in code
    assert "refusing to sign with the public demo seed" in code
