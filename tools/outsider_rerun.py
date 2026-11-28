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
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RECEIPT = os.path.join(HERE, "docs", "outsider-rerun-receipt.json")
PAGE = os.path.join(HERE, "docs", "OUTSIDER-RERUN.md")
MANIFEST = "docs/OUTSIDER-FILES.txt"
# All four are written by this tool, so all four stay out of the digests: each of
# them would otherwise hash a value that contains its own hash.
GENERATED = {"docs/outsider-rerun-receipt.json", "docs/OUTSIDER-RERUN.md",
             "docs/OUTSIDER-BOARD.html", MANIFEST,
             # The timestamp is taken *of* the receipt, so it cannot be part of it:
             # otherwise every new proof would invalidate the file it proves.
             "docs/outsider-rerun-receipt.json.ots"}
OTS = os.path.join(HERE, "docs", "outsider-rerun-receipt.json.ots")

IGNORE = (".git", "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
          "build", "*.egg-info",
          "node_modules", ".venv", "venv", "htmlcov", ".tox", ".nox",
          "*.pyc", "*.pyo", "*.egg-info")

STEPS = (
    ("gate", [sys.executable, "tools/mutation_gate.py"], "GATE OK"),
    ("parity", [sys.executable, "tools/competitor_gate_parity.py"], "PARITY OK"),
    ("demo", [sys.executable, "tools/demo_bid_binary.py"], "ALL OK"),
    ("tests", [sys.executable, "-m", "pytest", "tests/test_mutation_gate.py",
               "tests/test_competitor_parity.py", "tests/test_parity_board.py",
               "tests/test_refs_check.py", "tests/test_parity_sensitivity.py",
               "tests/test_parity_audit.py",
               "tests/test_parity_realrun.py", "-q"], "passed"),
)

# What each step must print, not merely exit zero on. A step whose command still
# returns 0 but no longer says "0 failed" is not evidence that nothing failed.
ASSERTS = {
    "gate": ("0 failed",),
    "parity": ("repositories pinned", "re-scored"),
    "demo": ("ALL OK",),
    "tests": ("passed",),
}

ENV_KEEP = ("PATH", "SYSTEMROOT", "SYSTEMDRIVE", "WINDIR", "TEMP", "TMP", "HOME",
            "USERPROFILE", "LANG", "LC_ALL", "PYTHONUTF8", "PYTHONIOENCODING")


INVENTORY = "docs/TRACKED-FILES.txt"

# Things a run of this project produces and a repository must never publish: a
# downloaded CI log bundle, a coverage file, a byte-code cache. This guard exists
# because one of them did get committed (a `logs*.zip` fetched while chasing a red
# job), the receipt was re-sealed afterwards so it did not answer for the file set
# the membership published, and every local check still said OK - the subset of
# checks that CI runs caught it instead. The membership check below is now part of
# `--check`, and this list makes the mistake name itself before it is committed.
ARTEFACT_PATTERNS = (
    r"(^|/)logs?\d*\.zip",
    r"(^|/)l\d+[a-z]?_?logs?\.zip",
    r"\.log$",
    r"(^|/)\.coverage",
    r"(^|/)htmlcov/",
    r"(^|/)\.pytest_cache/",
    r"(^|/)__pycache__/",
    r"\.py[co]$",
    r"(^|/)node_modules/",
    r"(^|/)\.venv/",
    r"(^|/)\.tox/",
    r"\.tmp$",
)
_ARTEFACT_RE = re.compile("|".join("(?:" + p + ")" for p in ARTEFACT_PATTERNS), re.I)


def artefact_paths(files):
    """Paths in `files` that look like a by-product rather than a source file."""
    return [p for p in files if _ARTEFACT_RE.search(p)]


def inventory_files(root):
    """The published membership: one path per line, exactly what a clone holds.

    A clone can ask git. An extracted tarball cannot, and it cannot tell a scratch
    directory a test run materialised (`benchmark/corpus/`, `tools/out/_mb/`) from
    a directory the repository commits but ignores (`dist/`, force-added on
    purpose). Guessing from `.gitignore` gets `dist/` wrong, so the membership is
    published instead: CI writes it with `git ls-files`, and the two channels then
    agree by construction rather than by coincidence.
    """
    path = os.path.join(root, INVENTORY)
    if not os.path.exists(path):
        return None
    rel = [l.strip().replace("\\", "/") for l in open(path, encoding="utf-8")
           if l.strip() and not l.startswith("#")]
    return rel


def write_inventory(root, from_archive=False):
    """Publish the membership.

    Three cases, no guessing:

    * a clone asks git (`git ls-files`) - authoritative, and CI does exactly this;
    * a fresh archive has nothing but committed files, so the walk is the answer -
      the caller must say so (`--from-archive`), because that is the one claim the
      tool cannot verify for itself;
    * anything else is refused. A tree that has run its tests carries scratch
      (`benchmark/corpus/`, `tools/out/_mb/`) that a clone would never hold, and
      writing it into the membership would make the receipt describe the author's
      disk instead of the repository. `.gitignore` cannot settle this either: it
      lists `dist/`, which this repository force-adds on purpose.
    """
    if os.path.isdir(os.path.join(root, ".git")):
        out = subprocess.run(["git", "ls-files", "-z"], cwd=root, capture_output=True,
                             text=True, encoding="utf-8", errors="replace")
        if out.returncode != 0 or not out.stdout:
            raise SystemExit("FAIL git could not list this tree; refusing to publish a membership")
        files = sorted(set(p for p in out.stdout.split("\0") if p) | {INVENTORY})
    elif from_archive:
        files = sorted(set(_walk(root)) | {INVENTORY})
    else:
        raise SystemExit("FAIL no .git here. Publish the membership from a fresh archive "
                         "(--inventory-write --from-archive) or from a clone.")
    os.makedirs(os.path.dirname(os.path.join(root, INVENTORY)), exist_ok=True)
    bad = artefact_paths(files)
    if bad:
        for p in bad[:10]:
            print("FAIL this is a by-product, not a member:", p)
        raise SystemExit(
            f"FAIL refusing to publish a membership that holds {len(bad)} by-product(s) "
            "(`logs*.zip`, coverage, caches). A clone would carry them, and a receipt "
            "that counts them describes your downloads rather than the repository. "
            "Remove them from the index (`git rm --cached <path>`), then rerun.")
    with open(os.path.join(root, INVENTORY), "w", encoding="utf-8", newline="\n") as f:
        f.write("\n".join(files) + "\n")
    return len(files)


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
    listed = inventory_files(root)
    if listed is not None:
        return [p for p in listed if p not in GENERATED]
    return _walk(root)


def _walk(root):
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in
                             {".git", "__pycache__", ".pytest_cache", ".mypy_cache", "build",
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

# Deliberately set, never inherited: these three decide the outcome as much as PATH does.
PINNED = {"PYTHONUTF8": "1", "PYTHONHASHSEED": "0", "PYTHONNOUSERSITE": "1", "PYTHONPATH": ""}


def clean_env():
    return {k: os.environ[k] for k in ENV_KEEP if k in os.environ} | dict(PINNED)


def installed_distributions(env):
    """What else was on this machine, in the author's own words: `name==version`, sorted.

    Sorted so that the digest of the list is a property of what is installed and not
    of the order pip happened to print it in.
    """
    try:
        out = subprocess.run([sys.executable, "-m", "pip", "freeze"], capture_output=True,
                             text=True, encoding="utf-8", errors="replace", env=env, timeout=120)
        lines = [l.strip() for l in (out.stdout or "").splitlines() if l.strip()]
        return sorted(l for l in lines if not l.startswith("-"))
    except Exception:                                                # noqa: BLE001
        return []


def distributions_digest(lines):
    """sha256 over the list exactly as the receipt prints it: one `name==version` per line."""
    return hashlib.sha256("\n".join(lines).encode("utf-8")).hexdigest()


def stable_stdout(text):
    """A step's output with the clock removed, so the digest can be compared elsewhere.

    `41 passed in 5.32s` becomes `41 passed`; nothing else is touched.  The point is
    that a stranger can run the same rule over his own output and compare digests —
    if the test logic were altered, the bytes would differ even with the same wording.
    """
    text = re.sub(r"\s+in\s+\d+(?:\.\d+)?\s*s(?:ec(?:onds)?)?\b", "", text)
    text = re.sub(r"\b\d+(?:\.\d+)?\s*s\b", "", text)
    lines = [ln.rstrip() for ln in text.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def copy_tree(dest):
    shutil.copytree(HERE, dest, ignore=shutil.ignore_patterns(*IGNORE))


def run(steps_only=None):
    name, (digest, cdigest, lfdigest, count) = all_digests(HERE)[0]
    blobs = commit_blobs(HERE) if name == "commit" else None
    files_manifest = manifest_from_blobs(blobs) if blobs is not None else file_manifest(HERE)
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
        must = ASSERTS.get(name, ())
        t0 = time.time()
        try:
            proc = subprocess.run(cmd, cwd=work, capture_output=True, text=True,
                                  encoding="utf-8", errors="replace", env=env, timeout=900)
            out, err, rc = proc.stdout or "", proc.stderr or "", proc.returncode
        except Exception as exc:                                     # noqa: BLE001
            out, err, rc = "", f"{type(exc).__name__}: {exc}", 124
        tail = (out.strip().splitlines() or [""])[-1][:160]
        missing = [m for m in must if m not in out]
        ok = rc == 0 and expect in out and not missing
        results.append({"step": name, "cmd": " ".join(cmd[1:]), "rc": rc,
                        "expect": expect, "asserts": list(must), "missing": missing,
                        "ok": ok, "seconds": round(time.time() - t0, 1),
                        "stdout_sha256": hashlib.sha256(
                            stable_stdout(out).encode("utf-8")).hexdigest(),
                        "tail": tail or err.strip().splitlines()[-1][:160]})
        print(f"{'PASS' if ok else 'FAIL'} {name:6s} rc={rc} {round(time.time() - t0, 1)}s :: {tail}"
              + (f" | missing: {missing}" if missing else ""))
    shutil.rmtree(tmp, ignore_errors=True)
    return {"digest": digest, "files": count, "content_digest": cdigest,
            "content_files": ccount, "content_lf_digest": lfdigest,
            "delivery": delivery, "distributions": installed_distributions(env),
            "files_manifest": files_manifest,
            "results": results}


def file_manifest(root, files=None):
    """Per-file sha256, so a mismatch can name the files that moved.

    The three digests answer "did anything move". This answers "which one",
    offline, with no reference to git: the receipt carries it, the checker
    recomputes it and prints the difference. It is also how the one file that a
    test run legitimately rewrites (`tools/out/mutation_benchmark.json`, whose
    `meta.generated_at_utc` is the clock) gets named instead of guessed.
    """
    out = {}
    for rel in sorted(files if files is not None else tracked_files(root)):
        if rel in GENERATED:
            continue
        p = os.path.join(root, rel.replace("/", os.sep))
        try:
            with open(p, "rb") as f:
                out[rel] = hashlib.sha256(f.read()).hexdigest()
        except OSError:
            out[rel] = "unreadable"
    return out


def manifest_from_blobs(blobs):
    """The manifest of a commit, not of a checkout.

    A checkout normalises line endings (`.gitattributes`: text=auto eol=lf), the
    blobs keep the stored bytes. The receipt names one of the two channels in
    `delivery`, so its per-file manifest must come from the same one - otherwise
    a correct receipt would report 83 files as drifted on every CI run.
    """
    return {p: hashlib.sha256(b).hexdigest() for p, b in blobs.items() if p not in GENERATED}


def serialise_manifest(manifest):
    """One line per file, `sha256  path`, sorted. A moved file is one changed line."""
    return "".join(f"{manifest[k]}  {k}\n" for k in sorted(manifest))


def write_manifest(manifest):
    """Write the manifest file and return the sha256 of its own bytes."""
    data = serialise_manifest(manifest)
    with open(os.path.join(HERE, MANIFEST.replace("/", os.sep)), "w",
              encoding="utf-8", newline="\n") as f:
        f.write(data)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def read_manifest(root):
    """(dict, sha256-of-the-file). A tampered manifest is caught by its own hash."""
    path = os.path.join(root, MANIFEST.replace("/", os.sep))
    if not os.path.exists(path):
        return None, None
    data = open(path, encoding="utf-8").read()
    entries = {}
    for line in data.splitlines():
        if not line.strip():
            continue
        sha, rel = line.split("  ", 1)
        entries[rel] = sha
    return entries, hashlib.sha256(data.encode("utf-8")).hexdigest()


def write_receipt(digest, files, results, content=None, content_files=None,
                  content_lf=None, delivery=None, files_manifest=None, distributions=None):
    receipt = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "tree_sha256": digest,
        "files_hashed": files,
        "content_sha256": content,
        "content_files": content_files,
        "content_lf_sha256": content_lf,
        "delivery": delivery,
        "files_manifest": {
            "path": MANIFEST,
            "sha256": write_manifest(files_manifest) if files_manifest else None,
            "entries": len(files_manifest or {}),
        },
        "digest_excludes": sorted(GENERATED),
        "runner": {"python": platform.python_version(), "machine": platform.machine(),
                   "system": platform.system()},
        "environment": {"variables_kept": list(ENV_KEEP),
                        "python_implementation": platform.python_implementation(),
                        "python_hash_seed": "0",
                        "user_site": "off",
                        "pythonpath": "",
                        "distributions": distributions or [],
                        "distributions_sha256": distributions_digest(distributions or []),
                        "note": "no tokens, no cloud credentials, nothing from the author's shell; "
                                "the hash seed and the user site directory are pinned so that "
                                "another machine's state cannot decide the outcome"},
        "steps": results,
        "ok": all(r["ok"] for r in results) and len(results) == len(STEPS),
    }
    open(RECEIPT, "w", encoding="utf-8", newline="\n").write(json.dumps(receipt, indent=1, ensure_ascii=False) + "\n")
    archive_rel = "conformance/uibc-conformance-0.7.0.zip"
    archive_path = os.path.join(HERE, archive_rel)
    if os.path.exists(archive_path):
        with open(archive_path, "rb") as fh:
            archive_sha, archive_bytes = hashlib.sha256(fh.read()).hexdigest(), os.path.getsize(archive_path)
    else:
        archive_sha, archive_bytes = None, None
    page = ["# 外人重跑：换一个目录、换一套环境，还成不成立", "",
            f"生成时间 {receipt['generated_at']}，运行环境 Python {receipt['runner']['python']} / "
            f"{receipt['runner']['system']}。", "",
            "做法：把仓库整棵拷到临时目录（不含 `.git`、不含任何缓存），用只保留白名单变量的干净环境，"
            "在该目录下跑四个公开入口；每一步记录退出码与输出末行；整棵树的 sha256 一并记下。", "",
            "| 步骤 | 命令 | 必须出现的字样 | 退出码 | 结果 | 耗时 |", "|---|---|---|---|---|---|"]
    for r in results:
        page.append("| {step} | `{cmd}` | {asserts} | {rc} | {ok} | {seconds}s |".format(
            step=r["step"], cmd=r["cmd"],
            asserts="；".join("`%s`" % m for m in r.get("asserts") or []) or "—",
            rc=r["rc"], ok="PASS" if r["ok"] else "FAIL", seconds=r["seconds"]))
    page += ["", "**为什么记的是字样而不只是退出码**：`rc=0` 只说明进程没崩。每一步还记下它必须印出的"
             "几处字样（例如 `0 failed`、`repositories pinned`、`passed`），重跑时任何一处没出现，这一步就"
             "判 FAIL——所以陌生人不必相信 \"PASS\" 这个词，他可以看这几处字样自己有没有看见。"]
    dists = receipt["environment"].get("distributions") or []
    page += ["", "**环境也记下来，不让你猜**：`Python {ver}` / {impl}，`PYTHONHASHSEED=0`（集合顺序不会自己变），"
             "`PYTHONNOUSERSITE=1`（谁自己 pip 装的包不能替你做决定），`PYTHONPATH` 清空。当时这台机器上的第三方包"
             "共 {n} 个，清单逐行 `name==version` 排好序后取 sha256（全 64 位，不截断）是"
             " `{h}`；全表在收据 `environment.distributions` 里，拿它重算一遍应当得到同一个值。".format(
                 ver=receipt["runner"]["python"],
                 impl=receipt["environment"].get("python_implementation") or "Python",
                 n=len(dists),
                 h=distributions_digest(dists) if dists else "—"),
             "换一台机器时，把 Python 版本对齐、让 pytest 在位即可；若上面那批字样不一致，差异在环境，不在收据。"]
    page += ["", "**每一步的输出也有指纹**（把 `in 5.32s` 这类秒数去掉后逐字节取 sha256）："]
    for r in results:
        page.append("- `{step}`：`{h}`".format(step=r["step"], h=r.get("stdout_sha256") or "—"))
    page += ["自己按同一规则（去掉秒数、行尾空格、末尾空行）处理后与上面对比：对不上就说明输出真的变了。"
             "这同时管住了「脚本只要印出字样就算过」这条路——字样是被测代码印的，"
             "而印出的整段字节记在收据里，改动测试逻辑就会改掉这段字节。"]
    page += ["", "**收据还带一枚时间戳**：`docs/outsider-rerun-receipt.json.ots`（OpenTimestamps，同一份字节同时提交给三个日历）。"
             "它证明的是「这些字节在提交那一刻就已经是这些字节」——不是我们事后补的。核验："
             "`python tools/anchor_ots.py --verify docs/outsider-rerun-receipt.json`。"
             "区块确认之前状态写 `pending_calendar`，确认后变成 `confirmed`；两者都说明提交已经发生，"
             "区别只是 Bitcoin 区块有没有把它记下来。"]
    page += ["", "**归档的来历也签了名**：`build-provenance` 作业在每次 main 推送时，用本仓库自己的 OIDC 身份，"
             "为 `dist` 下的 sdist、wheel 和你下载的那只归档各签一份构建来源证明（SLSA build provenance）。核验："
             "`gh attestation verify conformance/uibc-conformance-0.7.0.zip --repo zhaoxinghua09-cell/uibc-core`。"
             "它证明的是「这些字节在本仓库某次由本仓库签发的运行里出现过」；它**不**证明归档是隔离构建出来的——"
             "归档是仓库里的文件，不是当场构建的产物。这句区别写在这里，免得被当成比实际更强的东西。"]
    page += ["", "**环境也可以不由标签决定**：`docker/base-image.pin` 写的是基础镜像的 manifest 摘要，"
             "`docker/Dockerfile` 只许引用这一条（`tools/check_base_image_pin.py` 两边不一致就判红，"
             "并去注册表确认这个摘要还能拉到、顺带告诉你标签如今漂到哪儿去了）；容器里只装四个按 sha256 钉住的 "
             "wheel，然后跑同一条 `--check`。自己跑两条命令：",
             "`docker build -f docker/Dockerfile -t uibc-verify . && docker run --rm uibc-verify`。",
             "第二实现也要在这个环境里成立：`docker/node.pin` 用 tarball 的 sha256 钉住 Node（不是版本号），"
             "解包前重算摘要，解包只装 node/npm/npx 三个链接，不装 apt 包；于是容器里那条依赖 node 的测试不再"
             "被跳过，`python tools/tree_digest_second_impl.py --check` 也在同一个镜像里跑出 `VERDICT: TREE OK`。"
             "（第一版镜像没装 node，第四步报的是「40 passed, 1 skipped」——数字对，理由没说，现在理由没了。）",
             "它证明的是「这四步在一个由摘要决定、而不是由标签决定的解释器里同样成立」；它**不**证明容器文件系统"
             "逐字节可复现——层里的时间戳是构建那一刻的钟。这是钉住的环境，不是可复现的环境。"]
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
             ""]
    if archive_sha:
        page += [f"**先拿归档**：`{archive_rel}`，{archive_bytes} 字节，sha256 `{archive_sha}`。",
                 "这一份不需要我们的任何程序，也不需要信任本页的任何数字——下载后自己算 sha256，对上就说明"
                 "拿到的正是收据描述的那一份：",
                 f"- `https://raw.githubusercontent.com/zhaoxinghua09-cell/uibc-core/main/{archive_rel}`",
                 "- `https://codeload.github.com/zhaoxinghua09-cell/uibc-core/zip/refs/heads/main`（解开后在同一个路径下）",
                 "", "对不上就停下：说明有人换过字节，或者你的解包器动过它。"]
    page += ["", "复核：`python tools/outsider_rerun.py --check`（重算两根摘要＋逐步判定），或 `--run` 重新跑一遍。"]
    open(PAGE, "w", encoding="utf-8", newline="\n").write("\n".join(page) + "\n")
    print("OUTSIDER OK" if receipt["ok"] else "OUTSIDER FAIL",
          f"tree={digest[:12]} steps={len(results)}")
    return 0 if receipt["ok"] else 1


def check(verify_timestamp=True):
    if not os.path.exists(RECEIPT):
        print("FAIL no receipt; run --run first")
        return 1
    receipt = json.load(open(RECEIPT, encoding="utf-8"))
    missing = [k for k in ("tree_sha256", "content_sha256", "content_lf_sha256", "delivery")
               if k not in receipt]
    if missing:
        # A receipt written by an older release of this tool only carries the
        # strict digest. It cannot answer for line endings or for the channel it
        # came from, and comparing it would silently pass a tree it never saw.
        print("FAIL STALE RECEIPT: this file lacks " + ", ".join(missing))
        print("\nHOW TO FIX: tools/outsider_rerun.py --run regenerates all three axes and the")
        print("delivery tag on the tree in front of you; then tools/render_outsider_board.py --write")
        print(f"\nVERDICT: STALE RECEIPT ({len(missing)} field(s) missing)")
        return 1
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
        if not s.get("asserts"):
            fails.append(f"step {s.get('step')} records no asserted wording")
    if sorted(receipt.get("digest_excludes", [])) != sorted(GENERATED):
        fails.append("receipt excludes a different set of files than the checker")
    mf = receipt.get("files_manifest") or {}
    manifest, manifest_sha = read_manifest(HERE)
    drift = []
    if mf and manifest is None:
        fails.append(f"MANIFEST FILE: {MANIFEST} is missing; run --run")
    elif mf and manifest_sha != mf.get("sha256"):
        fails.append(f"MANIFEST FILE: {MANIFEST} was edited (sha {str(mf.get('sha256'))[:12]} "
                     f"in the receipt, {str(manifest_sha)[:12]} on disk)")
    elif mf and mf.get("entries") != len(manifest or {}):
        fails.append(f"MANIFEST FILE: {MANIFEST} holds {len(manifest or {})} entries, "
                     f"the receipt says {mf.get('entries')}")
    # Only when the strict answer is being judged: on a line-ending difference or
    # a mangled-name difference the digests already explain themselves, and listing
    # 83 "drifted" files there would be a true list answering the wrong question.
    if manifest and not (delivery_only or names_only):
        now = None
        if view_name == "commit":
            blobs = commit_blobs(HERE)
            if blobs is not None:
                now = manifest_from_blobs(blobs)
        now = now or file_manifest(HERE)
        for rel in sorted(set(manifest) | set(now)):
            if manifest.get(rel) != now.get(rel):
                drift.append(rel)
        for rel in drift[:8]:
            print(f"DRIFT {rel}: receipt {str(manifest.get(rel))[:12]} now "
                  f"{str(now.get(rel))[:12]}")
        if len(drift) > 8:
            print(f"DRIFT ... and {len(drift) - 8} more")
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
        print("\nHOW TO FIX: the files that moved are named above. If you only ran the test")
        print("suite, tools/out/mutation_benchmark.json is expected in that list: its")
        print("meta.generated_at_utc is the clock, so a suite run rewrites it. Restore it")
        print("from the commit, or reseal this tree with --run.")
        print(f"\nOUTSIDER FAIL ({len(fails)} problem(s))")
        return 1
    # Membership last, and as a verdict of its own: a receipt can be
    # self-consistent and still describe a file set the published inventory never
    # listed - that is how a committed `logs*.zip` passed every local check while
    # CI's inventory step said `FAIL git tracks and the inventory does not`.
    # Running it after the digest comparisons keeps the digest verdict readable
    # (NAMES-ONLY, DELIVERY, CONTENT) for the case that only concerns bytes.
    if check_inventory() != 0:
        print("\nHOW TO FIX: the published membership is docs/TRACKED-FILES.txt. Rewrite it on a")
        print("clone (`--inventory-write`) so it lists what git tracks, and re-seal with `--run`;")
        print("if the disagreement is a by-product that got committed, remove it from the index.")
        print("\nVERDICT: MEMBERSHIP DISAGREES (this tree is not the published membership)")
        return 1
    print()
    print(f"OUTSIDER OK: receipt matches this {view_name} ({count} files, {digest[:12]}, "
          f"content {cdigest[:12]}), {len(steps)} steps passed")
    if verify_timestamp and not check_timestamp():
        return 1
    for name, (d, c, l, n) in views:
        if name != view_name and d != digest:
            print(f"NOTE: the {name} view differs from the {view_name} one. The receipt answers "
                  f"for the {view_name}; uncommitted edits and files dropped by other steps live "
                  f"only in the {name} view and are not what this number describes.")
    return 0


def check_inventory():
    """Does the published membership still describe this tree?"""
    listed = inventory_files(HERE)
    if listed is None:
        print(f"FAIL {INVENTORY} is missing; run --inventory-write on a clone or a fresh archive")
        return 1
    bad = artefact_paths(listed)
    if bad:
        for p in bad[:10]:
            print("FAIL the published membership holds a by-product:", p)
        print(f"\nINVENTORY FAIL ({len(bad)} by-product(s) published as members)")
        return 1
    actual = _walk(HERE)
    git_view = None
    if os.path.isdir(os.path.join(HERE, ".git")):
        try:
            out = subprocess.run(["git", "ls-files", "-z"], cwd=HERE, capture_output=True,
                                 text=True, encoding="utf-8", errors="replace")
            if out.returncode == 0 and out.stdout:
                git_view = [p for p in out.stdout.split("\0") if p]
        except Exception:                                          # noqa: BLE001
            git_view = None
    if git_view is not None:
        drift = sorted(set(git_view) ^ set(listed))
        if drift:
            for p in drift[:10]:
                print("FAIL git tracks and the inventory does not:", p)
            print(f"\nINVENTORY FAIL ({len(drift)} path(s) differ from git ls-files); "
                  f"rerun --inventory-write")
            return 1
    missing = sorted(set(listed) - set(actual))
    extra = sorted(set(actual) - set(listed))
    for p in missing[:10]:
        print("FAIL listed but absent:", p)
    for p in extra[:10]:
        print("NOTE present but not published:", p)
    if missing:
        print(f"\nINVENTORY FAIL ({len(missing)} path(s) listed and gone)")
        return 1
    if extra:
        print(f"\nNOTE: {len(extra)} path(s) exist here and are not published "
              f"(scratch a clone would never hold); the receipt ignores them")
    print(f"INVENTORY OK ({len(listed)} paths, all present)")
    return 0


def stamp_receipt():
    """Submit the receipt to the calendars; the proof lands next to it as `.ots`.

    The tree is checked *without* the timestamp, because a receipt that has just
    been re-sealed is precisely the case where the old proof is stale - refusing
    here would make the stale proof impossible to replace.
    """
    if check(verify_timestamp=False) != 0:
        print("refusing to stamp: the receipt does not match this tree")
        return 1
    proc = subprocess.run([sys.executable, os.path.join(HERE, "tools", "anchor_ots.py"),
                           "--stamp", RECEIPT, "--json"], cwd=HERE, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")
    tail = (proc.stdout or proc.stderr or "").strip().splitlines()
    print("\n".join(tail[-6:]))
    if not os.path.exists(OTS):
        print(f"FAIL no proof was written to {OTS}")
        return 1
    print(f"stamped: {os.path.relpath(OTS, HERE)} ({os.path.getsize(OTS)} bytes)")
    return 0


def check_timestamp():
    """Is the published proof about *this* receipt? Pending is fine, mismatched is not.

    The binding is checked without the OpenTimestamps client: a proof carries the
    sha256 of the file it was taken of as 32 raw bytes inside it, so looking for
    those bytes answers "is this proof about this receipt" with no dependency at
    all. The client is only consulted afterwards, and only for the *status* - a
    checkout without it must not turn this into a failure, which is exactly the
    mistake this function made in its first version.
    """
    if not os.path.exists(OTS):
        print("FAIL no timestamp: docs/outsider-rerun-receipt.json.ots is missing; run --stamp")
        return False
    with open(RECEIPT, "rb") as f:
        digest = hashlib.sha256(f.read()).digest()
    with open(OTS, "rb") as f:
        raw = f.read()
    if digest not in raw:
        print("FAIL the timestamp proves a different file: stamp the receipt again")
        print(f"  receipt sha256 {digest.hex()[:16]} does not appear in the proof")
        return False
    try:
        import opentimestamps  # noqa: F401
    except Exception:                                              # noqa: BLE001
        print("timestamp: proof carries this receipt's digest (client not installed, "
              "block status not read)")
        return True
    proc = subprocess.run([sys.executable, os.path.join(HERE, "tools", "anchor_ots.py"),
                           "--verify", RECEIPT, "--proof", OTS, "--json"], cwd=HERE,
                          capture_output=True, text=True, encoding="utf-8", errors="replace")
    status = [ln for ln in ((proc.stdout or "") + (proc.stderr or "")).splitlines()
              if ln.startswith("status=")]
    print(f"timestamp: {status[-1][7:] if status else 'proof present'}")
    return True


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", action="store_true", help="copy the tree and rerun every entry point")
    ap.add_argument("--check", action="store_true", help="verify the receipt against this tree (default)")
    ap.add_argument("--inventory-write", action="store_true",
                    help="rewrite docs/TRACKED-FILES.txt from a clone (git ls-files)")
    ap.add_argument("--from-archive", action="store_true",
                    help="with --inventory-write on a tree with no .git: this is a fresh archive")
    ap.add_argument("--inventory-check", action="store_true",
                    help="verify docs/TRACKED-FILES.txt against the tree and against git ls-files")
    ap.add_argument("--stamp", action="store_true",
                    help="submit the receipt to the OpenTimestamps calendars (writes .ots)")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    if args.inventory_write:
        n = write_inventory(HERE, from_archive=args.from_archive)
        print(f"written: {INVENTORY} ({n} paths)")
        rc = 0
    elif args.inventory_check:
        rc = check_inventory()
    elif args.stamp:
        rc = stamp_receipt()
    elif args.run:
        out = run()
        rc = write_receipt(out["digest"], out["files"], out["results"],
                           content=out["content_digest"], content_files=out["content_files"],
                           content_lf=out["content_lf_digest"], delivery=out["delivery"],
                           distributions=out.get("distributions"),
                           files_manifest=out.get("files_manifest") or file_manifest(HERE))
    else:
        rc = check()
    if args.json:
        print(json.dumps({"ok": rc == 0, "exit": rc}, ensure_ascii=False))
    return rc


if __name__ == "__main__":
    sys.exit(main())
