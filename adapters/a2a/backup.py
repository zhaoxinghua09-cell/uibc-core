"""State backup, integrity check and fast restore.

Clause anchor: T/ISC 0174-2026 sections 6.3.1 and 6.3.2.

    6.3.1 a) 应支持智能体身份相关数据和操作数据的定时备份与主动备份能力；
    6.3.1 b) 应支持身份备份数据的加密存储，保障备份数据安全性与完整性；
    6.3.1 c) 应支持身份数据增量备份与全量备份结合；
    6.3.2 a) 应支持身份数据故障自动检测，核心数据异常时即时触发告警；
    6.3.2 b) 应支持备份身份数据的快速恢复，保障身份分发核心功能不中断。

What is honest here: a), c) and 6.3.2 a)/b) are implemented for the gateway's own
state files (registry, lifecycle, routes, journal) - full and incremental snapshots
with SHA-256 manifests, corruption detection, verified restore. b) encryption is
NOT implemented: adding a cipher to a zero-dependency stdlib project means either
pulling a crypto dependency or inventing one, and inventing one is the worse
choice. `encrypted` is therefore recorded as False in every manifest, so a reader
of the backup can see exactly what protection it has - rather than reading the
word "backup" and assuming more than exists.

Restore is two-phase on purpose: verify the manifest first, refuse on mismatch.
A backup that cannot prove its own integrity is not a backup, it is a rumour.
"""

import datetime as _dt
import hashlib
import json
import os
import shutil


def _sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _stamp(now=None):
    current = now or _dt.datetime.now(_dt.timezone.utc)
    return current.strftime("%Y%m%dT%H%M%SZ")


class BackupStore:
    def __init__(self, root, state_paths, now=None):
        self.root = os.path.abspath(root)
        self.state_paths = [os.path.abspath(p) for p in state_paths if p]
        self.clock = now or (lambda: _dt.datetime.now(_dt.timezone.utc))

    # -- snapshots ---------------------------------------------------------
    def backups(self):
        if not os.path.isdir(self.root):
            return []
        return sorted(name for name in os.listdir(self.root)
                      if os.path.isdir(os.path.join(self.root, name)))

    def latest(self):
        found = self.backups()
        return os.path.join(self.root, found[-1]) if found else None

    def create(self, incremental=False, label=None):
        if label is None:
            # Auto labels get a suffix instead of overwriting: two backups inside
            # the same second must both survive, because the second one may be the
            # only record of a state that broke.
            base = _stamp(self.clock())
            label = base
            suffix = 1
            while os.path.isdir(os.path.join(self.root, label)):
                suffix += 1
                label = "%s-%d" % (base, suffix)
        target = os.path.join(self.root, label)
        if os.path.isdir(target):
            raise ValueError("backup label already exists: %s" % label)
        # Resolve the base *before* creating the new directory, otherwise latest()
        # would return the empty directory we are about to fill.
        base = self.latest() if incremental else None
        os.makedirs(target, exist_ok=True)

        base_manifest = {}
        if base:
            with open(os.path.join(base, "manifest.json"), encoding="utf-8") as handle:
                base_manifest = {f["path"]: f for f in json.load(handle)["files"]}

        files, unchanged = [], 0
        for path in self.state_paths:
            if not os.path.exists(path):
                continue
            digest = _sha256(path)
            if incremental and path in base_manifest \
                    and base_manifest[path]["sha256"] == digest:
                unchanged += 1
                files.append(dict(base_manifest[path], carried_over=True))
                continue
            name = os.path.basename(path)
            copy_path = os.path.join(target, name)
            shutil.copy2(path, copy_path)
            files.append({"path": path, "copy": name, "sha256": digest,
                          "bytes": os.path.getsize(path), "carried_over": False})

        manifest = {
            "schema": "uibc-gateway-backup/1",
            "created_at": self.clock().isoformat(),
            "label": label,
            "incremental": bool(incremental),
            "base": os.path.basename(base) if base else None,
            "encrypted": False,
            "encryption_note": "6.3.1 b) 未实现：本项目零依赖，不自造密码学",
            "unchanged_carried_over": unchanged,
            "files": files,
        }
        with open(os.path.join(target, "manifest.json"), "w", encoding="utf-8") as handle:
            json.dump(manifest, handle, ensure_ascii=False, indent=2)
        return manifest

    # -- integrity ---------------------------------------------------------
    def verify(self, label=None):
        path = os.path.join(self.root, label) if label else self.latest()
        if not path or not os.path.isdir(path):
            return {"ok": False, "checked": 0, "mismatch": [{"reason": "no backup found"}]}
        with open(os.path.join(path, "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        mismatches, checked = [], 0
        for entry in manifest["files"]:
            copy_path = os.path.join(path, entry["copy"])
            if not os.path.exists(copy_path):
                mismatches.append({"path": entry["path"], "reason": "copy missing"})
                continue
            checked += 1
            if _sha256(copy_path) != entry["sha256"]:
                mismatches.append({"path": entry["path"], "reason": "sha256 mismatch"})
        return {"ok": not mismatches, "checked": checked,
                "files": len(manifest["files"]),
                "encrypted": manifest.get("encrypted", False),
                "mismatch": mismatches, "label": manifest.get("label")}

    def detect_corruption(self, label=None):
        """6.3.2 a) compare live state against the last good snapshot."""
        path = os.path.join(self.root, label) if label else self.latest()
        if not path or not os.path.isdir(path):
            return {"ok": True, "alert": False, "drift": [],
                    "reason": "no snapshot to compare against"}
        with open(os.path.join(path, "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        drift = []
        for entry in manifest["files"]:
            live = entry["path"]
            if not os.path.exists(live):
                drift.append({"path": live, "reason": "live file missing"})
                continue
            try:
                digest = _sha256(live)
            except OSError as exc:
                drift.append({"path": live, "reason": "unreadable: %s" % exc})
                continue
            if digest != entry["sha256"]:
                drift.append({"path": live, "reason": "changed since snapshot"})
            if live.endswith(".json"):
                try:
                    with open(live, encoding="utf-8") as handle:
                        json.load(handle)
                except ValueError:
                    drift.append({"path": live, "reason": "unparsable JSON"})
        changed = [d for d in drift if d["reason"] == "changed since snapshot"]
        broken = [d for d in drift if d["reason"] in ("unparsable JSON", "live file missing",
                                                      ) or d["reason"].startswith("unreadable")]
        return {"ok": not broken, "alert": bool(broken),
                "drift": drift, "changed": len(changed), "broken": len(broken)}

    def restore(self, label=None, target_dir=None):
        """6.3.2 b) verify first, then copy back. Refuses on any mismatch."""
        report = self.verify(label)
        if not report["ok"]:
            raise ValueError("refusing to restore from an unverified backup: %s"
                             % report["mismatch"])
        base = os.path.join(self.root, report["label"])
        with open(os.path.join(base, "manifest.json"), encoding="utf-8") as handle:
            manifest = json.load(handle)
        restored = []
        for entry in manifest["files"]:
            destination = entry["path"]
            if target_dir:
                destination = os.path.join(os.path.abspath(target_dir),
                                           os.path.basename(entry["path"]))
            parent = os.path.dirname(destination)
            if parent and not os.path.isdir(parent):
                os.makedirs(parent, exist_ok=True)
            shutil.copy2(os.path.join(base, entry["copy"]), destination)
            restored.append(destination)
        return {"ok": True, "restored": restored, "label": report["label"],
                "verified_files": report["checked"]}
