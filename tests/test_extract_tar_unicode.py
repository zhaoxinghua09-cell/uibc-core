"""Tarball extraction must keep non-ASCII names byte-identical.

The failure this pins: Windows `bsdtar` decoded a UTF-8 header as GBK, so
`运行日志` became `杩愯鏃ュ織` and the conformance case `accept-unicode-names` failed
with a *hash mismatch* that pointed at the verifier instead of the extractor.
"""
import io
import os
import sys
import tarfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools import extract_tar  # noqa: E402

NAMES = ["运行日志/entry.json", "résumé/naïve.txt"]


def _make_archive(path):
    with tarfile.open(path, "w:gz", encoding="utf-8") as tf:
        for name in NAMES:
            data = ("body of " + name).encode("utf-8")
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tf.addfile(info, io.BytesIO(data))


def test_non_ascii_names_round_trip(tmp_path):
    archive = tmp_path / "a.tar.gz"
    _make_archive(str(archive))
    dest = tmp_path / "out"
    assert extract_tar.main([str(archive), "--dest", str(dest)]) == 0
    found = sorted(
        str(p.relative_to(dest)).replace(os.sep, "/")
        for p in dest.rglob("*") if p.is_file()
    )
    assert found == sorted(NAMES)


def test_missing_archive_is_an_error_not_a_traceback(tmp_path, capsys):
    rc = extract_tar.main([str(tmp_path / "nope.tar.gz"), "--dest", str(tmp_path / "o")])
    assert rc == 2
    err = capsys.readouterr().err
    assert "archive not found" in err and "Traceback" not in err
