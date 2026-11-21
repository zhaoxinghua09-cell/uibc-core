"""Sign the published digest list offline, with the release key, without touching the page.

v0.4.1 is frozen and carries UNSIGNED.txt. Re-signing it would rewrite the page and
invalidate the pin, the receipt and the invitation letters that quote its digest. But
"nothing identifies the publisher" is not an acceptable resting place either.

So: the page stays as it is, and the publisher signs the digest it froze -- here, in
the repository, where the page cannot rewrite the record.
"""
import ctypes
import ctypes.wintypes as wt
import io
import json
import os
import shutil
import subprocess
import sys

REPO = "zhaoxinghua09-cell/uibc-core"
SEED_DPAPI = r"D:\Workbuddy\05-工具\vault\uibc_release_seed.dpapi"
TAG = "v0.4.1"
NAME = "CORPUS-DIGESTS.txt"
WORK = os.path.join(os.environ["TEMP"], "attest_" + TAG.replace("/", "_"))


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", ctypes.c_ulong), ("pbData", ctypes.POINTER(ctypes.c_char))]


def unprotect(path):
    raw = open(path, "rb").read()
    blob_in = DATA_BLOB(len(raw), ctypes.cast(
        ctypes.create_string_buffer(raw, len(raw)), ctypes.POINTER(ctypes.c_char)))
    blob_out = DATA_BLOB()
    if not ctypes.windll.crypt32.CryptUnprotectData(
            ctypes.byref(blob_in), None, None, None, None, 0, ctypes.byref(blob_out)):
        raise RuntimeError("CryptUnprotectData failed on %s" % path)
    size = blob_out.cbData
    data = ctypes.string_at(blob_out.pbData, size)
    ctypes.windll.kernel32.LocalFree(blob_out.pbData)
    return data


def fetch(tag, name, dest):
    os.makedirs(dest, exist_ok=True)
    proc = subprocess.run(["gh", "release", "download", tag, "-R", REPO, "-p", name,
                           "-D", dest, "--clobber"], capture_output=True, text=True,
                          timeout=300)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip()[:300])
    return os.path.join(dest, name)


def main():
    if os.path.isdir(WORK):
        shutil.rmtree(WORK)
    path = fetch(TAG, NAME, WORK)
    message = open(path, "rb").read()
    print("served %s: %d bytes" % (NAME, len(message)))
    digest = __import__("hashlib").sha256(message).hexdigest()
    print("served sha256: %s" % digest)

    seed = unprotect(SEED_DPAPI)
    if isinstance(seed, str):
        seed = seed.encode()
    if len(seed) == 64:
        # The vault stores it as 64 hex characters, not raw bytes.
        seed = bytes.fromhex(seed.decode("ascii"))
    if len(seed) != 32:
        raise SystemExit("unexpected seed length %d" % len(seed))
    print("seed decrypted in memory, 32 bytes, not printed")

    sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "tools"))
    import anchor_release_digests as ard
    pub = ard.__dict__["ed25519"].publickey(seed)
    key_id = ard._key_id(pub)

    out_dir = os.path.join("anchors", "attestations", TAG)
    os.makedirs(out_dir, exist_ok=True)
    out = os.path.join(out_dir, NAME + ".sig")
    ard.sign_file(path, seed, out=out,
                  note="the release page is frozen and carries UNSIGNED.txt; this attests "
                       "the digest it served when it was frozen, signed after the fact")
    print("signature written to %s" % out)

    reasons = ard.verify_file(out, path)
    print("verify_file reasons:", reasons if reasons else "none")
    sidecar = json.load(io.open(out, encoding="utf-8"))
    print("key_id %s / file_sha256 %s" % (sidecar["key_id"], sidecar["file_sha256"]))
    print("key_id matches the recorded release key:",
          sidecar["key_id"] == key_id)

    att = {
        "kind": "uibc-publisher-attestation-v0",
        "tag": TAG,
        "attests": {"file": NAME, "bytes": len(message), "sha256": digest},
        "signature": NAME + ".sig",
        "key_id": key_id,
        "why_not_on_the_page": "the page was frozen on 2026-11-20T04:24:44Z and carries "
                               "UNSIGNED.txt; adding a signature would rewrite the bytes "
                               "the pin, the receipt and two invitations already quote",
        "statement": "The Ed25519 key identified here signed this digest list. It identifies "
                     "the publisher; it does not claim the release workflow was honest, and "
                     "it was produced after publication rather than during it.",
    }
    io.open(os.path.join(out_dir, "ATTESTATION.json"), "w", encoding="utf-8",
            newline="\n").write(json.dumps(att, indent=2, sort_keys=True) + "\n")
    print("attestation written")


if __name__ == "__main__":
    main()
