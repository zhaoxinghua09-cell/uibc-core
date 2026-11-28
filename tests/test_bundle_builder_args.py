"""The builder must not accept anything as a version, or overwrite a pinned archive.

Measured 2026-11-20: `tools/build_conformance_bundle.py --help` was read as a version and
wrote `conformance/uibc-conformance---help.zip` (229,084 bytes, 294 files) into the
repository, because the version was `sys.argv[1]` with no check. The same run also showed
that rebuilding 0.4.1 from today's tree yields different bytes than the pin, which the
builder must refuse rather than perform.
"""
import importlib.util
import os

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILDER = os.path.join(REPO, "tools", "build_conformance_bundle.py")


def load_builder():
    spec = importlib.util.spec_from_file_location("build_conformance_bundle", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def builder():
    return load_builder()


def test_importing_the_builder_does_not_choose_a_version():
    """The old module took sys.argv at import time, so `--help` became a version."""
    source = open(BUILDER, encoding="utf-8").read()
    assert 'VERSION = sys.argv[1]' not in source


def test_help_returns_usage_and_builds_nothing(builder):
    version, replace = builder.parse_args(["--help"])
    assert version is None and replace is False


def test_a_short_version_is_refused(builder):
    with pytest.raises(SystemExit):
        builder.parse_args(["0.4"])


def test_a_flag_as_a_version_is_refused(builder):
    with pytest.raises(SystemExit):
        builder.parse_args(["--fast"])


def test_the_default_is_the_current_version(builder):
    version, replace = builder.parse_args([])
    assert version == "0.4.1" and replace is False


def test_replace_is_the_only_flag(builder):
    version, replace = builder.parse_args(["0.4.2", "--replace"])
    assert version == "0.4.2" and replace is True


def test_the_refusal_is_documented_with_both_hashes():
    pin = open(os.path.join(REPO, "anchors", "pins", "uibc-conformance-0.4.1.sha256"),
               encoding="utf-8").read()
    audit = open(os.path.join(REPO, "docs", "AUDIT-KIT.md"), encoding="utf-8").read()
    readme = open(os.path.join(REPO, "README.md"), encoding="utf-8").read()
    for text in (pin, audit, readme):
        assert "083c0dbc" in text
    assert "refuses to overwrite" in audit
    assert "refuses to overwrite" in readme


def test_the_builder_refuses_a_pinned_archive_with_different_bytes(builder):
    source = open(BUILDER, encoding="utf-8").read()
    assert "is pinned and this build has different bytes" in source
    assert "return 3" in source
