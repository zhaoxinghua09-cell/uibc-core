"""The profile's steps, as tests rather than prose.

Each case is a way the check can go wrong and the code it must produce. The point
is that "different tree" and "different bytes" stay different codes: a verifier that
merges them produces a report nobody downstream can act on.
"""
import json
import os
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from uibc_core import profile  # noqa: E402

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEMO = os.path.join(REPO, "examples", "demo.uibc")
SEED = b"\x07" * 32


def value_of(pkg=DEMO):
    root, count, agent, problems = profile.package_facts(pkg)
    assert not problems, problems
    return profile.registered_value(root, count, agent), root, count, agent


def test_good_receipt_is_partial_never_ok():
    v, *_ = value_of()
    res = profile.verify(DEMO, profile.make_receipt(v, SEED))
    assert res["verdict"] == profile.PARTIAL_INCLUSION_UNCHECKED, res
    assert "inclusion proof not evaluated" in json.dumps(res["steps"])
    assert res["verdict"] != profile.OK


def test_receipt_for_other_bytes_is_a_value_mismatch_not_a_signature_error():
    res = profile.verify(DEMO, profile.make_receipt(b"not this value" + b"x" * 100, SEED))
    assert res["verdict"] == profile.FAIL_VALUE_MISMATCH, res
    assert "different bytes, or signed by a key not held here" in json.dumps(res["steps"])


def test_unknown_tree_is_unsupported_not_false():
    v, *_ = value_of()
    res = profile.verify(DEMO, profile.make_receipt(v, SEED, vds=9999))
    assert res["verdict"] == profile.UNSUPPORTED_SCHEME, res
    assert any("not evidence that the package is false" in n for n in res["notes"])


def test_receipt_without_proof_is_malformed():
    v, *_ = value_of()
    res = profile.verify(DEMO, profile.make_receipt(v, SEED, vdp=None))
    assert res["verdict"] == profile.FAIL_MALFORMED, res


def test_changed_byte_in_package_breaks_the_root(tmp_path):
    d = tmp_path / "pkg"
    shutil.copytree(DEMO, d)
    f = d / "evidence" / "files" / "action-log.txt"
    f.write_bytes(f.read_bytes() + b"x")
    v, *_ = value_of()
    res = profile.verify(str(d), profile.make_receipt(v, SEED))
    assert res["verdict"] == profile.FAIL_PACKAGE, res
    assert "content changed" in json.dumps(res["steps"], ensure_ascii=False)


def test_undeclared_file_is_a_package_problem(tmp_path):
    d = tmp_path / "pkg"
    shutil.copytree(DEMO, d)
    (d / "evidence" / "files" / "extra.txt").write_bytes(b"smuggled")
    v, *_ = value_of()
    res = profile.verify(str(d), profile.make_receipt(v, SEED))
    assert res["verdict"] == profile.FAIL_PACKAGE, res
    assert "undeclared" in json.dumps(res["steps"], ensure_ascii=False)


def test_count_is_inside_the_value():
    v1, root, count, agent = value_of()
    v2 = profile.registered_value(root, count + 1, agent)
    assert v1 != v2
    assert b'"count":' in v1


def test_root_and_agent_are_both_bound():
    v1, root, count, agent = value_of()
    assert v1 != profile.registered_value("0" * 64, count, agent)
    assert v1 != profile.registered_value(root, count, agent + "-other")
