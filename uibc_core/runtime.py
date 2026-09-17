"""uibc-core runtime hooks (PROPOSAL v0.1) - one-line wrappers so a running
program can record verifiable evidence without hand-writing CLI calls.

Design discipline (same as docs/api-scope.md): these helpers NEVER invent
facts. They only package what actually happened on disk (a file existed,
with this content, at this time). Zero dependencies.

Example:

    from uibc_core.runtime import record_action, seal
    record_action("demo.uibc", "report.txt", note="generated quarterly summary")
    seal("demo.uibc", "owner.key")   # re-seal so the Evidence Root stays valid
"""

import os

from . import cli as ucli


class _Args(object):
    """argparse-Namespace stand-in for direct CLI-function calls."""
    def __init__(self, **kw):
        self.__dict__.update(kw)


def record_action(package, file, action_type="ACTION", note="",
                  media_type=None):
    """Record one action as evidence in an existing package.

    Returns the recorded evidence relative path (from the CLI output).
    Raises the same errors the CLI would (missing package / file).
    """
    if not os.path.isdir(package):
        raise FileNotFoundError("package not found: %s" % package)
    if not os.path.isfile(file):
        raise FileNotFoundError("evidence file not found: %s" % file)
    if media_type is None:
        ext = os.path.splitext(file)[1].lstrip(".").lower()
        media_type = {"txt": "text/plain", "md": "text/markdown",
                      "json": "application/json", "csv": "text/csv",
                      "html": "text/html", "pdf": "application/pdf",
                      "png": "image/png", "jpg": "image/jpeg",
                      "jpeg": "image/jpeg"}.get(ext, "application/octet-stream")
    ucli.cmd_evidence(_Args(path=package, type=action_type, file=file,
                            media_type=media_type, note=note))


def seal(package, key_file=None):
    """Re-seal a package (recompute Evidence Root, write/refresh the HMAC
    seal). Call after every record_action batch so verifiers see a fresh
    root. key_file=None keeps the package unsigned (open-mode only)."""
    if not os.path.isdir(package):
        raise FileNotFoundError("package not found: %s" % package)
    ucli.cmd_submit(_Args(path=package, key=key_file))


def event(package, event_type, actor):
    """Append a lifecycle event (must be a known type: REGISTER/ACTIVATE/
    UPDATE/TRANSFER/DELEGATE/SUSPEND/RESUME/REVOKE/RETIRE)."""
    ucli.cmd_event(_Args(path=package, type=event_type, actor=actor))


def snapshot(package, facts, key_file=None):
    """Convenience: write a JSON facts file and record it as evidence in one
    call. `facts` must be a JSON-serializable dict of what actually happened.

    Anti-fabrication note: this helper timestamps and hashes `facts`, but it
    cannot make `facts` true. Garbage in, garbage notarized.
    """
    import json
    import time
    payload = dict(facts)
    payload.setdefault("recorded_at",
                       time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    path = package + ".snapshot.json" if os.path.isdir(package) \
        else os.path.join(os.path.dirname(package.rstrip("/\\")),
                          "snapshot.json")
    out = os.path.join(package, "snapshots") if os.path.isdir(package) else path
    os.makedirs(out, exist_ok=True)
    fp = os.path.join(out, "snapshot-%d.json" % int(time.time() * 1000))
    with open(fp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
    record_action(package, fp, action_type="ACTION",
                  note=str(payload.get("note", "")), media_type="application/json")
    if key_file:
        seal(package, key_file)
    return fp
