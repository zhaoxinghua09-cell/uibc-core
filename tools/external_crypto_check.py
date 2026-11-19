#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""用第三方密码库独立复算本项目的 Ed25519 封签。

动机（为什么需要这个脚本）
--------------------------
`uibc_core/ed25519.py` 是纯 Python 自实现（零第三方依赖，这是本项目的取舍）。
我们的 verifier 用它去验我们自己产出的签——**即使这个实现写错了，验也是自洽地通过**。
这类"自验自证"是任何单实现项目最深的坑，而且它不会以失败的形式暴露出来。

本脚本把这一层换成可被第三方反驳的检验：

- 用 `cryptography`（第三方库，OpenSSL 后端）对同一个事实做验签；
- 与我们的 `ed_seal_verify` 逐包比对，输出 agree/disagree；
- 再跑一个**负样本探针**：把 payload 改一个字节后，第三方库必须拒签，
  否则说明验签只是在空转；

本脚本明确不做的事（不藏起来）
------------------------------
1. canonical 序列化仍用本仓库的 JCS 实现（本机没有第三方 JCS 库），
   因此 **RFC 8785 合规性没有被本脚本检验**——第三方只验"签名原语"这一层。
2. HMAC 封签是对称的，没有密钥就无法第三方复算；这些包被计为 SKIPPED
   并给出理由，不计入 agree/disagree。
3. 第三方库能验通过，只说明"签名原语与 RFC 8032 一致"，不说明包里内容为真。

用法
----
    python tools/external_crypto_check.py                 # 从 conformance 归档取包
    python tools/external_crypto_check.py --json          # 机器可读
    python tools/external_crypto_check.py --dir <dir>     # 指定已解压的 cases 目录

退出码：0 = CONSISTENT；1 = DISCREPANCY 或探针未被拒（此时不许对外声称已交叉验证）。
"""

import argparse
import base64
import glob
import json
import os
import sys
import tempfile
import zipfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO not in sys.path:
    sys.path.insert(0, REPO)

from uibc_core import signing  # noqa: E402

_ZIP = os.path.join(REPO, "conformance", "uibc-conformance-0.4.0.zip")

try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    HAVE_CRYPTOGRAPHY = True
except Exception:  # pragma: no cover - 由调用方处理
    HAVE_CRYPTOGRAPHY = False


def _read_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _package_payload(pkg):
    """Recompute the sealed payload exactly as the package records it."""
    identity = _read_json(os.path.join(pkg, "identity.json"))
    manifest = _read_json(os.path.join(pkg, "manifest.json"))
    lifecycle_path = os.path.join(pkg, "lifecycle.json")
    lifecycle = _read_json(lifecycle_path) if os.path.exists(lifecycle_path) else None
    return signing.seal_payload(identity, manifest, lifecycle)


def _third_party_verifies(pub_b64, sig_b64, payload):
    """Verify with cryptography, not with our own implementation."""
    pub = base64.b64decode(pub_b64, validate=True)
    sig = base64.b64decode(sig_b64, validate=True)
    key = Ed25519PublicKey.from_public_bytes(pub)
    try:
        key.verify(sig, payload)
        return True
    except Exception:
        return False


def _case_dirs(root):
    return [d for d in sorted(glob.glob(os.path.join(root, "*"))) if os.path.isdir(d)]


def run(cases_root):
    rows = []
    skipped_hmac = 0
    for pkg in _case_dirs(cases_root):
        seal_path = os.path.join(pkg, "signatures", "seal.json")
        if not os.path.exists(seal_path):
            continue
        try:
            seal = _read_json(seal_path)
        except Exception:
            # 损坏的封签是负样本的一部分，交给 verifier 判，不在本脚本里判
            continue
        if seal.get("algorithm") != signing.ALGORITHM_ED25519:
            skipped_hmac += 1
            continue
        payload = _package_payload(pkg)
        identity = _read_json(os.path.join(pkg, "identity.json"))
        manifest = _read_json(os.path.join(pkg, "manifest.json"))
        lifecycle_path = os.path.join(pkg, "lifecycle.json")
        lifecycle = _read_json(lifecycle_path) if os.path.exists(lifecycle_path) else None
        # signature order is (public_key, identity, manifest, lifecycle, sig)
        scope = signing.ed_seal_verify_scoped(
            base64.b64decode(seal["public_key"], validate=True),
            identity,
            manifest,
            lifecycle,
            seal.get("signature", ""),
        )
        ours = scope is not None
        theirs = _third_party_verifies(seal.get("public_key", ""), seal.get("signature", ""), payload)
        rows.append({
            "case": os.path.basename(pkg),
            "scope": scope,
            "third_party": "ok" if theirs else "fail",
            "ours": "ok" if ours else "fail",
            "agree": ours == theirs,
        })
    return rows, skipped_hmac


def probe(root):
    """A one-byte edit to the payload must be refused by the third party."""
    for pkg in _case_dirs(root):
        seal_path = os.path.join(pkg, "signatures", "seal.json")
        if not os.path.exists(seal_path):
            continue
        try:
            seal = _read_json(seal_path)
        except Exception:
            continue
        if seal.get("algorithm") != signing.ALGORITHM_ED25519:
            continue
        payload = _package_payload(pkg)
        tampered = payload[:-1] + bytes([payload[-1] ^ 0x01])
        refused = not _third_party_verifies(seal["public_key"], seal["signature"], tampered)
        return {"case": os.path.basename(pkg), "tampered_refused": refused}
    return None


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--dir")
    args = ap.parse_args(argv)

    if not HAVE_CRYPTOGRAPHY:
        print("SKIPPED: cryptography is not installed; this check needs a third-party library.")
        return 2

    tmp = None
    if args.dir:
        root = args.dir
    else:
        tmp = tempfile.mkdtemp(prefix="uibc-extcrypto-")
        with zipfile.ZipFile(_ZIP) as z:
            z.extractall(tmp)
        root = os.path.join(tmp, "cases")

    rows, skipped_hmac = run(root)
    pr = probe(root)

    disagree = [r for r in rows if not r["agree"]]
    verdict = "CONSISTENT"
    if disagree or (pr and not pr["tampered_refused"]):
        verdict = "DISCREPANCY"

    if args.json:
        print(json.dumps({
            "ed25519_packages": len(rows),
            "agree": len(rows) - len(disagree),
            "disagree": disagree,
            "skipped_hmac": skipped_hmac,
            "probe": pr,
            "verdict": verdict,
        }, indent=2, ensure_ascii=False))
    else:
        print("%-46s %-12s %-8s %s" % ("case", "third-party", "ours", "agree"))
        for r in rows:
            print("%-46s %-12s %-8s %s" % (r["case"][:46], r["third_party"], r["ours"], r["agree"]))
        print("")
        print("HMAC packages skipped (no key to recompute with): %d" % skipped_hmac)
        if pr:
            print("probe: one byte changed in %s -> third party refused: %s"
                  % (pr["case"], pr["tampered_refused"]))
        print("NOT CHECKED HERE: RFC 8785 canonical serialisation still uses this repo's JCS")
        print("implementation; no third-party JCS library is installed on this machine.")
        print("")
        print("VERDICT: %s" % verdict)

    if tmp:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)
    return 0 if verdict == "CONSISTENT" else 1


if __name__ == "__main__":
    raise SystemExit(main())
