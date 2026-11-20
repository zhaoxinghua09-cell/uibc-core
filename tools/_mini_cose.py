#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""零依赖的最小 CBOR + COSE_Sign1(EdDSA) 实现。

为什么存在：`tools/cose_sign1_interop.py` 原来硬依赖 `cbor2` + `pycose`，
外人拿到仓库直接跑会 ModuleNotFoundError 卡住（2026-11-20 外人实跑 rc=1 的真因）。
本模块只覆盖互验脚本用到的那一小块 CBOR（int / bstr / tstr / array / map / tag 18 /
true / false / null），签名与验签走 `uibc_core.ed25519`（纯标准库实现）。

对外接口刻意做成 cbor2 / pycose 的同名子集，便于互验脚本在有库/无库两种环境下
共用一套判定逻辑，而不是两套结论。
"""
import sys

from uibc_core import ed25519 as _ed


# --------------------------------------------------------------------------- #
# CBOR 编解码（子集）
# --------------------------------------------------------------------------- #
class Tag(object):
    """对应 cbor2.CBORTag：带 .tag 与 .value。"""

    __slots__ = ("tag", "value")

    def __init__(self, tag, value):
        self.tag = int(tag)
        self.value = value

    def __repr__(self):
        return "Tag(%d, %r)" % (self.tag, self.value)

    def __eq__(self, other):
        return isinstance(other, Tag) and self.tag == other.tag and self.value == other.value


def _head(major, n):
    if n < 24:
        return bytes([(major << 5) | n])
    if n < 0x100:
        return bytes([(major << 5) | 24, n])
    if n < 0x10000:
        return bytes([(major << 5) | 25]) + n.to_bytes(2, "big")
    if n < 0x100000000:
        return bytes([(major << 5) | 26]) + n.to_bytes(4, "big")
    return bytes([(major << 5) | 27]) + n.to_bytes(8, "big")


def dumps(obj):
    """确定性编码：map 按 key 排序，保证同一对象两次编码字节一致。"""
    if obj is True:
        return b"\xf5"
    if obj is False:
        return b"\xf4"
    if obj is None:
        return b"\xf6"
    if isinstance(obj, Tag):
        return _head(6, obj.tag) + dumps(obj.value)
    if isinstance(obj, int):
        return _head(0, obj) if obj >= 0 else _head(1, -1 - obj)
    if isinstance(obj, (bytes, bytearray)):
        raw = bytes(obj)
        return _head(2, len(raw)) + raw
    if isinstance(obj, str):
        raw = obj.encode("utf-8")
        return _head(3, len(raw)) + raw
    if isinstance(obj, (list, tuple)):
        return _head(4, len(obj)) + b"".join(dumps(x) for x in obj)
    if isinstance(obj, dict):
        items = sorted(obj.items(), key=lambda kv: (str(type(kv[0])), kv[0]))
        return _head(5, len(items)) + b"".join(dumps(k) + dumps(v) for k, v in items)
    raise TypeError("mini-cbor 不支持的类型: %r" % (type(obj),))


def _read(data, pos):
    ib = data[pos]
    major, add = ib >> 5, ib & 0x1F
    pos += 1
    if add < 24:
        n = add
    elif add == 24:
        n = data[pos]
        pos += 1
    elif add == 25:
        n = int.from_bytes(data[pos:pos + 2], "big")
        pos += 2
    elif add == 26:
        n = int.from_bytes(data[pos:pos + 4], "big")
        pos += 4
    elif add == 27:
        n = int.from_bytes(data[pos:pos + 8], "big")
        pos += 8
    else:
        raise ValueError("mini-cbor 不支持不定长/保留附加信息 add=%d" % add)

    if major == 0:
        return n, pos
    if major == 1:
        return -1 - n, pos
    if major == 2:
        return data[pos:pos + n], pos + n
    if major == 3:
        return data[pos:pos + n].decode("utf-8"), pos + n
    if major == 4:
        out = []
        for _ in range(n):
            v, pos = _read(data, pos)
            out.append(v)
        return out, pos
    if major == 5:
        out = {}
        for _ in range(n):
            k, pos = _read(data, pos)
            v, pos = _read(data, pos)
            out[k] = v
        return out, pos
    if major == 6:
        v, pos = _read(data, pos)
        return Tag(n, v), pos
    if major == 7:
        if add == 20:
            return False, pos
        if add == 21:
            return True, pos
        if add == 22:
            return None, pos
        raise ValueError("mini-cbor 不支持 major 7 简单值 add=%d" % add)
    raise ValueError("mini-cbor 非法 major=%d" % major)


def loads(data):
    v, pos = _read(bytes(data), 0)
    if pos != len(data):
        raise ValueError("mini-cbor 尾部有多余字节（%d/%d 已消费）" % (pos, len(data)))
    return v


def CBORTag(tag, value):  # 与 cbor2.CBORTag 同名
    return Tag(tag, value)


# --------------------------------------------------------------------------- #
# COSE_Sign1 / OKPKey 垫片（同名子集）
# --------------------------------------------------------------------------- #
class _Curve(object):
    name = "Ed25519"


Ed25519 = _Curve()


class OKPKey(object):
    def __init__(self, crv=Ed25519, x=None, d=None):
        self.x = bytes(x) if x is not None else None
        self.d = bytes(d) if d is not None else None


class Sign1Message(object):
    """只实现互验脚本用到的两条路径：sign+encode、from_cose_obj+verify_signature。"""

    def __init__(self, phdr=None, payload=None, key=None):
        self.phdr = dict(phdr or {})
        self.payload = payload
        self.key = key
        self.protected_bytes = None
        self.unprotected = None
        self.signature = None

    # ---------------- 签 ----------------
    def _sig_structure(self, protected_bytes, payload):
        return dumps(["Signature1", protected_bytes, b"", payload])

    def encode(self):
        if self.key is None or self.key.d is None:
            raise ValueError("mini-cose: 签封需要私钥(k=OKPKey(..., d=seed))")
        self.protected_bytes = dumps(self.phdr)
        sig = _ed.sign(self.key.d, self._sig_structure(self.protected_bytes, self.payload))
        self.signature = sig
        self.unprotected = {4: self.key.x}
        return dumps(Tag(18, [self.protected_bytes, self.unprotected, self.payload, sig]))

    # ---------------- 验 ----------------
    @classmethod
    def from_cose_obj(cls, arr, _dont_verify=True):
        if not isinstance(arr, (list, tuple)) or len(arr) != 4:
            raise ValueError("COSE_Sign1 必须是 4 元数组")
        protected_bytes, unprotected, payload, sig = arr
        msg = cls(payload=payload)
        msg.protected_bytes = bytes(protected_bytes)
        msg.phdr = loads(protected_bytes)
        msg.unprotected = unprotected
        msg.signature = bytes(sig)
        if msg.phdr.get(1) not in (-8, -19):
            raise ValueError("mini-cose 只支持 alg=-8/-19，收到 %r" % (msg.phdr.get(1),))
        return msg

    def verify_signature(self):
        """返回 True / False（与 pycose 1.1.0 的语义一致：bool，不抛异常）。"""
        if self.key is None or self.key.x is None:
            raise ValueError("验签需要公钥")
        if self.signature is None:
            raise ValueError("信封里没有签名")
        return bool(_ed.verify(self.key.x, self._sig_structure(self.protected_bytes, self.payload),
                               self.signature))


IS_ZERO_DEP_BACKEND = True


def describe():
    return {"impl": "tools/_mini_cose.py", "cbor": "mini", "cose": "mini", "python": sys.version.split()[0]}
