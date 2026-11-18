"""One package, one writer at a time.

Why this exists: 200 concurrent records into one package used to leave 28
index entries and 129 stray files behind, with 69 JSON decode errors and a
package that no longer verified. The read-modify-write in `cmd_evidence`
was unguarded and not atomic, so two threads could both read the index,
both append, and the later write silently discarded the earlier one.

Two primitives, both standard library:

  - an exclusive lock file in the package (`evidence/.lock`), using
    `fcntl.flock` on POSIX and `msvcrt.locking` on Windows;
  - atomic replacement of the index (`write tmp` then `os.replace`), so a
    reader never observes a half-written file.

What this does not solve: two *processes* on a filesystem that does not
honour advisory locks (some network mounts). The lock is advisory; it stops
cooperating writers, not a filesystem. `docs/CONCURRENCY.md` says so.
"""

import contextlib
import os
import time

try:  # POSIX
    import fcntl as _fcntl
    _HAVE_FCNTL = True
except Exception:  # pragma: no cover - Windows
    _fcntl = None
    _HAVE_FCNTL = False

try:  # Windows
    import msvcrt as _msvcrt
    _HAVE_MSVCRT = True
except Exception:  # pragma: no cover - POSIX
    _msvcrt = None
    _HAVE_MSVCRT = False

_POLL = 0.004


class LockTimeout(RuntimeError):
    pass


def _acquire(fd, timeout):
    deadline = time.monotonic() + timeout
    while True:
        try:
            if _HAVE_FCNTL:
                _fcntl.flock(fd, _fcntl.LOCK_EX | _fcntl.LOCK_NB)
                return
            if _HAVE_MSVCRT:
                os.lseek(fd, 0, os.SEEK_SET)
                _msvcrt.locking(fd, _msvcrt.LK_NBLCK, 1)
                return
            # No locking primitive: refuse to pretend. A caller that believes
            # it holds a lock it does not hold is worse than a caller that
            # knows it is unprotected.
            raise LockTimeout("no file locking primitive on this platform")
        except (BlockingIOError, OSError) as exc:
            if isinstance(exc, LockTimeout):
                raise
            if time.monotonic() >= deadline:
                raise LockTimeout("could not acquire %s within %.1fs" % (fd, timeout))
            time.sleep(_POLL)


def _release(fd):
    try:
        if _HAVE_FCNTL:
            _fcntl.flock(fd, _fcntl.LOCK_UN)
        elif _HAVE_MSVCRT:
            os.lseek(fd, 0, os.SEEK_SET)
            _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)
    finally:
        pass


@contextlib.contextmanager
def package_lock(package, timeout=30.0):
    """Hold an exclusive advisory lock on one package.

    The lock file lives inside the package (evidence/.lock). It is not
    evidence: S1 permits dotfiles next to the index, and this file is
    documented rather than hidden.
    """
    path = os.path.join(package, "evidence", ".lock")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        if _HAVE_MSVCRT and os.path.getsize(path) == 0:
            # msvcrt locks a byte range; give it a byte to stand on.
            os.write(fd, b"\0")
        _acquire(fd, timeout)
        try:
            yield
        finally:
            _release(fd)
    finally:
        os.close(fd)


def atomic_write_json(path, obj, indent=2):
    """Write JSON via a sibling temp file and os.replace.

    A reader either sees the old file or the new one, never a partial write.
    """
    import json
    tmp = "%s.tmp-%d-%d" % (path, os.getpid(), id(obj))
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, indent=indent, sort_keys=False)
        f.write("\n")
    os.replace(tmp, path)
