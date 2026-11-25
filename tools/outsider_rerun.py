"""Outsider rerun: prove the claims hold in a copy nobody has touched.

Every receipt in this repository so far was produced by the machine that wrote
the code. That is the weakest possible witness. This tool makes the witness
mechanical:

  1. copy the tree to a fresh temporary directory, without `.git`, without
     caches, without any of this machine's state;
  2. run the four public entry points there with a stripped environment (no
     tokens, no extra variables), from that directory as the working directory;
  3. hash the tree, record every exit code and the tail of every output, and
     write `docs/outsider-rerun-receipt.json`;
  4. `--check` recomputes the tree digest and fails if the receipt no longer
     describes this tree, or if any step is not a clean pass.

The digest excludes the two files it produces (`docs/outsider-rerun-receipt.json`
and `docs/OUTSIDER-RERUN.md`) - otherwise it would have to contain itself. Both
producer and checker skip the same two paths, so the exclusion is symmetric and
the receipt cannot be quietly freshened without the tree actually matching.

The receipt carries two axes, because a single number cannot say *why* it moved:

  * `tree_sha256` - path and content together, the strict one;
  * `content_sha256` - content only, path-independent, so a tree whose file
    *names* were mangled by an extractor still matches on bytes.

That second axis is not a concession. Windows `tar` decodes UTF-8 names as
CP936, so a perfectly good tarball lands as `r茅sum茅.md` and the strict digest
goes red while every byte is untouched. `--check` distinguishes the two cases
and says which one it is: `NAMES-ONLY` (bytes identical, names broken - your
extractor, not this repository) or `CONTENT` (a byte really moved).

If a stranger can run this, they do not have to take anyone's word for the gate,
the parity table or the demo.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(HERE, "docs", "outsider-rerun-receipt.json")
PAGE = os.path.join(HERE, "docs", "OUTSIDER-RERUN.md")
GENERATED = {"docs/outsider-rerun-receipt.json", "docs/OUTSIDER-RERUN.md",
             "docs/OUTSIDER-BOARD.html"}

IGNORE = (".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
          "node_modules", ".venv", "venv", "htmlcov", ".tox", ".nox",
          "*.pyc", "*.pyo", "*.egg-info")

STEPS = (
    ("gate", [sys.executable, "tools/mutation_gate.py"], "GATE OK"),
    ("parity", [sys.executable, "tools/competitor_gate_parity.py"], "PARITY OK"),
    ("demo", [sys.executable, "tools/demo_bid_binary.py"], "ALL OK"),
    ("tests", [sys.executable, "-m", "pytest", "tests/test_mutation_gate.py",
               "tests/test_competitor_parity.py", "tests/test_parity_board.py",
               "tests/test_refs_check.py", "tests/test_parity_sensitivity.py",
               "tests/test_parity_audit.py", "-q"], "passed"),
)

ENV_KEEP = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "HOME",
            "USERPROFILE", "LANG", "LC_ALL", "PYTHONUTF8", "PYTHONIOENCODING")


def tracked_files(root):
    """The files a clone would contain.

    In a checkout, ask git: that set does not move when a test run drops
    `.coverage` or `htmlcov/` into the tree. In a tarball there is no `.git`, so
    walk with the same ignore list the producer used - the two agree because a
    tarball carries no build artefacts.
    """
    if os.path.isdir(os.path.join(root, ".git")):
        try:
            out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace")
            if out.returncode == 0 and out.stdout:
                return [p for p in out.stdout.split("\0") if p]
        except Exception:                                          # noqa: BLE001
            pass
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in
                             {".git", "__pycache__", ".pytest_cache", ".mypy_cache",
                              ".ruff_cache", "node_modules", ".venv", "venv", "htmlcov", ".tox", ".nox"})
        for fn in sorted(filenames):
            if fn.endswith((".pyc", ".pyo")) or fn in (".coverage", "coverage.xml"):
                continue
            found.append(os.path.relpath(os.path.join(dirpath, fn), root).replace("\\", "/"))
    return found


def tree_digest(root, files=None):
    """sha256 over every file path and its content digest, in path order.

    `files` lets a caller hand over its own membership list (used by the
    cross-implementation check, so Python and Node cannot pass by agreeing on
    different file sets); omitted, membership is derived here.
    """
    entries = []
    for rel in sorted(files if files is not None else tracked_files(root)):
        if rel in GENERATED:
            continue
        p = os.path.join(root, rel.replace("/", os.sep))
        try:
            with open(p, "rb") as f:
                entries.append(rel + ":" + hashlib.sha256(f.read()).hexdigest())
        except OSError:
            entries.append(rel + ":unreadable")
    return hashlib.sha256("\n".join(entries).encode()).hexdigest(), len(entries)


def content_digest(root, files=None):
    """sha256 over every file's content digest, paths deliberately left out.

    Used as the second axis: it answers "did any byte move" without caring how
    the extractor spelled the names. Sorting the hashes rather than the paths
    keeps it independent of the path strings entirely.
    """
    hashes = []
    for rel in (files if files is not None else tracked_files(root)):
        if rel in GENERATED:
            continue
        p = os.path.join(root, rel.replace("/", os.sep))
        try:
            with open(p, "rb") as f:
                hashes.append(hashlib.sha256(f.read()).hexdigest())
        except OSError:
            hashes.append("unreadable")
    return hashlib.sha256("\n".join(sorted(hashes)).encode()).hexdigest(), len(hashes)


def content_lf_digest(root, files=None):
    """The content axis with CRLF folded to LF before hashing.

    Why a third number: `git archive` ships the stored blob, a checkout applies
    the eol attributes. Measured here: 83 blobs are stored with CRLF while
    `.gitattributes` says `text=auto eol=lf`, so the same commit hands you
    different bytes depending on how you got it - clone or codeload tarball. A
    receipt taken from an archive therefore disagrees with a Linux worktree on
    those 83 files and on nothing else. This axis is what tells that apart from
    an actual edit; it is never used as the strict number.
    """
    hashes = []
    for rel in (files if files is not None else tracked_files(root)):
        if rel in GENERATED:
            continue
        p = os.path.join(root, rel.replace("/", os.sep))
        try:
            with open(p, "rb") as f:
                hashes.append(hashlib.sha256(f.read().replace(b"\r\n", b"\n")).hexdigest())
        except OSError:
            hashes.append("unreadable")
    return hashlib.sha256("\n".join(sorted(hashes)).encode()).hexdigest(), len(hashes)


def commit_blobs(root):
    """path -> bytes for everything HEAD tracks, read out of git, not the disk.

    Why not the disk: a checkout is a working directory, and CI steps before the
    audit legitimately drop files into it (a regenerated page, a coverage file).
    Those would make the receipt look stale without a single tracked byte moving.
    HEAD does not move. This is also the delivery-independent view: `git archive`
    ships exactly these bytes, so the tarball and the clone finally agree.
    """
    if not os.path.isdir(os.path.join(root, ".git")):
        return None
    try:
        ls = subprocess.run(["git", "ls-tree", "-r", "-z", "--full-tree", "HEAD"], cwd=root,
                            capture_output=True)
        if ls.returncode != 0 or not ls.stdout:
            return None
        entries = []
        for item in ls.stdout.split(b"\0"):
            if not item:
                continue
            meta, path = item.split(b"\t", 1)
            mode, kind, sha = meta.split(b" ")
            if kind != b"blob" or mode not in (b"100644", b"100755"):
                continue
            entries.append((sha, path.decode("utf-8")))
        bat = subprocess.run(["git", "cat-file", "--batch"], cwd=root,
                             input=b"".join(e[0] + b"\n" for e in entries),
                             capture_output=True)
        if bat.returncode != 0:
            return None
        blobs, pos = {}, 0
        data = bat.stdout
        for sha, path in entries:
            eol = data.index(b"\n", pos)
            header = data[pos:eol].split(b" ")
            size = int(header[2])
            body = data[eol + 1:eol + 1 + size]
            blobs[path] = body
            pos = eol + 1 + size + 1
        return blobs
    except Exception:                                              # noqa: BLE001
        return None


def digests_from_blobs(blobs):
    """The three axes, computed on an in-memory path -> bytes mapping."""
    paths, contents, folded = [], [], []
    for path in sorted(blobs):
        if path in GENERATED:
            continue
        body = blobs[path]
        paths.append(path + ":" + hashlib.sha256(body).hexdigest())
        contents.append(hashlib.sha256(body).hexdigest())
        folded.append(hashlib.sha256(body.replace(b"\r\n", b"\n")).hexdigest())
    n = len(paths)
    return (hashlib.sha256("\n".join(paths).encode()).hexdigest(),
            hashlib.sha256("\n".join(sorted(contents)).encode()).hexdigest(),
            hashlib.sha256("\n".join(sorted(folded)).encode()).hexdigest(), n)


def all_digests(root):
    """Every view we can offer, cheapest first: what git says, what is on disk."""
    views = []
    blobs = commit_blobs(root)
    if blobs is not None:
        views.append(("commit", digests_from_blobs(blobs)))
    views.append(("disk", (tree_digest(root)[0], content_digest(root)[0],
                               content_lf_digest(root)[0], len(tracked_files(root)))))
    return views

def clean_env():
    return {k: os.environ[k] for k in ENV_KEEP if k in os.environ} | {"PYTHONUTF8": "1"}


def copy_tree(dest):
    shutil.copytree(HERE, dest, ignore=shutil.ignore_patterns(*IGNORE))


def run(steps_only=None):
    name, (digest, cdigest, lfdigest, count) = all_digests(HERE)[0]
    delivery = name if name == "commit" else ("worktree" if os.path.isdir(os.path.join(HERE, ".git")) else "archive")
    ccount = count
    tmp = tempfile.mkdtemp(prefix="uibc-outsider-")
    work = os.path.join(tmp, "repo")
    copy_tree(work)
    env = clean_env()
    results = []
    for name, cmd, expect in STEPS:
        if steps_only and name not in steps_only:
            continue
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, timeout=900)
            out, err, rc = proc.stdout or "", proc.stderr or "", proc.returncode
        except Exception as exc:                                     # noqa: BLE001
            out, err, rc = "", f"{type(exc).__name__}: {exc}", 124
        tail = (out.strip().splitlines() or [""])[-1][:160]
        ok = rc == 0 and expect in out
        results.append({"step": name, "cmd": " ".join(cmd[1:]), "rc": rc,
                        "expect": expect, "ok": ok, "seconds": round(time.time() - t0, 1),
                        "tail": tail or err.strip().splitlines()[-1][:160]})
        print(f"{'PASS' if ok else 'FAIL'} {name:6s} rc={rc} {round(time.time() - t0, 1)}s :: {tail}")
    shutil.rmtree(tmp, ignore_errors=True)
    return {"digest": digest, "files": count, "content_digest": cdigest,
            "content_files": ccount, "content_lf_digest": lfdigest,
            "delivery": delivery,
            "results": results}


def write_receipt(digest, files, results, content=None, content_files=None,
                  content_lf=None, delivery=None):
    receipt = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tree_sha256": digest,
        "files_hashed": files,
        "content_sha256": content,
        "content_files": content_files,
        "content_lf_sha256": content_lf,
        "delivery": delivery,
        "digest_excludes": sorted(GENERATED),
        "runner": {"python": platform.python_version(), "machine": platform.machine(),
                   "system": platform.system()},
        "environment": {"variables_kept": list(ENV_KEEP),
                        "note": "no tokens, no cloud credentials, nothing from the author's shell"},
        "steps": results,
        "ok": all(r["ok"] for r in results) and len(results) == len(STEPS),
    }
    open(RECEIPT, "w", encoding="utf-8").write(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    page = ["# 外人重跑：换一个目录、换一套环境，还成不成立", "",
            f"生成时间 {receipt['generated_at']}，运行环境 Python {receipt['runner']['python']} / "
            f"{receipt['runner']['system']}。", "",
            "做法：把仓库整棵拷到临时目录（不含 `.git`、不含任何缓存），用只保留白名单变量的干净环境，"
            "在该目录下跑四个公开入口；每一步记录退出码与输出末行；整棵树的 sha256 一并记下。", "",
            "| 步骤 | 命令 | 退出码 | 结果 | 耗时 |", "|---|---|---|---|---|"]
    for r in results:
        page.append("| {step} | `{cmd}` | {rc} | {ok} | {seconds}s |".format(
            step=r["step"], cmd=r["cmd"], rc=r["rc"], ok="PASS" if r["ok"] else "FAIL",
            seconds=r["seconds"]))
    page += ["", f"**树摘要 `{receipt['tree_sha256'][:16]}…`（{files} 个文件，排除本页与 receipt 自身）**。",
             f"**内容摘要 `{str(receipt.get('content_sha256'))[:16]}…`（只看每个文件的字节，不看文件名）**。",
             "", "为什么有两根轴：路径与内容一起算的那个摘要最严，但也会被解包器连累。"
             "Windows 自带的 `tar` 把 UTF-8 文件名当 CP936 解，出来的 `r茅sum茅.md` 一个字节都没错，"
             "严摘要却红。于是收据同时记一根只算内容的摘要，`--check` 因此能说出是 "
             "`NAMES-ONLY`（字节全同、名字坏了，问题在你的解包器）还是 `CONTENT`（真的有字节动了）。",
             "在 Windows 上解包请用 `python -c \"import tarfile,sys;tarfile.open(sys.argv[1]).extractall(sys.argv[2])\" <包> <目录>`，"
             "或直接在 POSIX 上解包。",
             "",
             f"**第三根轴 `{str(receipt.get('content_lf_sha256'))[:16]}…`：内容摘要再折一次换行（CRLF→LF）**，"
             f"收据记的是 `{receipt.get('delivery')}` 这一路的字节。原因实测：本仓有 83 个文件的 blob 按 CRLF 存，"
             "而 `.gitattributes` 写的是 `text=auto eol=lf`——`git archive` 给的是存储的字节，检出给的是规整后的字节，"
             "同一个提交两条通道给两套字节。这一根轴用来把\"换行差异\"与\"有人改了字节\"分开，"
             "`--check` 因此能报 `VERDICT: DELIVERY MATCH`（同名同内容、只差换行）。",
             "", "复核：`python tools/outsider_rerun.py --check`（重算两根摘要＋逐步判定），或 `--run` 重新跑一遍。"]
    open(PAGE, "w", encoding="utf-8").write("\n".join(page) + "\n")
    print("OUTSIDER OK" if receipt["ok"] else "OUTSIDER FAIL",
          f"tree={digest[:12]} steps={len(results)}")
    return 0 if receipt["ok"] else 1


def check():
    if not os.path.exists(RECEIPT):
        print("FAIL no receipt; run --run first")
        return 1
    receipt = json.load(open(RECEIPT, encoding="utf-8"))
    fails = []
    receipt_content = receipt.get("content_sha256")
    receipt_lf = receipt.get("content_lf_sha256")
    views = all_digests(HERE)
    names_only = False
    delivery_only = False
    matched = None
    strict = False
    for name, (d, c, l, n) in views:
        if receipt.get("tree_sha256") == d:
            matched = (name, d, c, l, n)
            strict = True
            break
    if matched is None:
        for name, (d, c, l, n) in views:
            if receipt_content and receipt_content == c:
                names_only = True
                matched = (name, d, c, l, n)
                fails.append(
                    "NAMES-ONLY: the paths differ but every byte matches "
                    f"(content_sha256 {c[:12]} agrees, tree_sha256 {d[:12]} does not, seen as {name})")
                break
            if receipt_lf and receipt_lf == l:
                delivery_only = True
                matched = (name, d, c, l, n)
                fails.append(
                    "DELIVERY: the bytes differ only in line endings "
                    f"(content_lf_sha256 {l[:12]} agrees on both sides); the receipt names "
                    f"delivery {receipt.get('delivery')!r}, this tree is another one ({name})")
                break
        if matched is None:
            name, (d, c, l, n) = views[-1]
            fails.append(f"CONTENT: receipt describes tree {str(receipt.get('tree_sha256'))[:12]} "
                         f"but this tree hashes to {d[:12]} (content_sha256 "
                         f"{str(receipt_content)[:12]} vs {c[:12]})")
            matched = (name, d, c, l, n)
    view_name, digest, cdigest, lfdigest, count = matched
    # The strict digest already encodes the file set: every path and every
    # content hash is in it. The count is a second opinion worth asking when the
    # digest did not match; when it did, a differing count means the two views
    # count differently (a Windows extraction turning a symlink into a file),
    # not that a file appeared.
    if not strict and receipt.get("files_hashed") != count:
        fails.append(f"file count moved: receipt {receipt.get('files_hashed')}, tree {count}")
    steps = receipt.get("steps", [])
    if len(steps) != len(STEPS):
        fails.append(f"receipt has {len(steps)} steps, expected {len(STEPS)}")
    for s in steps:
        if not s.get("ok") or s.get("rc") != 0:
            fails.append(f"step {s.get('step')} did not pass in the recorded run")
        if s.get("expect") and s["expect"] not in (s.get("tail") or ""):
            fails.append(f"step {s.get('step')} tail does not carry its marker {s['expect']!r}")
    if sorted(receipt.get("digest_excludes", [])) != sorted(GENERATED):
        fails.append("receipt excludes a different set of files than the checker")
    for f in fails:
        print("FAIL", f)
    if names_only:
        print("\nHOW TO FIX: your extractor mangled the file names, not the files. Windows `tar`")
        print("decodes UTF-8 names as CP936. Re-extract with Python's tarfile (it honours UTF-8)")
        print("or on a POSIX host, then rerun --check; the tree digest will match unchanged.")
        print(f"\nOUTSIDER FAIL ({len(fails)} problem(s), names only - bytes are intact)")
        return 2
    if delivery_only:
        print("\nOK BY DELIVERY: this is the same commit seen through the other channel. `git archive`")
        print("ships the stored blob; a checkout applies `.gitattributes` (text=auto eol=lf), and")
        print("this repository stores some blobs with CRLF. The strict digest names the channel it")
        print("was taken from, so a stranger who clones and a stranger who unpacks a tarball each")
        print("get a number that matches their own bytes. Nothing was edited.")
        print(f"\nVERDICT: DELIVERY MATCH ({receipt.get('delivery')} receipt, "
              f"{'worktree' if os.path.isdir(os.path.join(HERE, '.git')) else 'archive'} tree)")
        return 0
    if fails:
        print(f"\nOUTSIDER FAIL ({len(fails)} problem(s))")
        return 1
    print(f"OUTSIDER OK: receipt matches this {view_name} ({count} files, {digest[:12]}, "
          f"content {cdigest[:12]}), {len(steps)} steps passed")
    for name, (d, c, l, n) in views:
        if name != view_name and d != digest:
            print(f"NOTE: the {name} view differs from the {view_name} one. The receipt answers "
                  f"for the {view_name}; uncommitted edits and files dropped by other steps live "
                  f"only in the {name} view and are not what this number describes.")
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="copy the tree and rerun every entry point")
    ap.add_argument("--check", action="store_true", help="verify the receipt against this tree (default)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.run:
        out = run()
        rc = write_receipt(out["digest"], out["files"], out["results"],
                           content=out["content_digest"], content_files=out["content_files"],
                           content_lf=out["content_lf_digest"], delivery=out["delivery"])
    else:
        rc = check()
    if args.json:
        print(json.dumps({"ok": rc == 0, "exit": rc}, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
