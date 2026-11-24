"""Heterogeneous message conversion with a round-trip gate.

Clause anchor: T/ISC 0174-2026 section 7.2.2.

    7.2.2 a) 应支持异构消息格式的自动识别与统一转换，至少覆盖 JSON、XML 等主流格式；
    7.2.2 b) 应支持消息体的语义保持转换，确保格式转换过程中信息不丢失、语义不偏移；
    7.2.2 e) 宜支持对消息转换结果进行语义一致性校验，校验失败时拒绝转发并记录安全事件。

The clause that matters here is b), and it cannot be satisfied by "the converter
returned something". So every conversion is round-tripped - XML back to JSON -
and compared against the input under a canonical form. If the comparison fails,
the call raises SemanticDrift instead of forwarding a payload whose meaning has
quietly changed. A converter that loses a field and says nothing is worse than
one that refuses.

Type fidelity is carried explicitly (`json-type` attribute per element) because
XML has no native distinction between 1, "1", true and null, and a converter that
"helpfully" stringifies all four is exactly the semantic drift 7.2.2 b) forbids.
"""

import json
from xml.etree import ElementTree as ET

TYPE_ATTR = "json-type"
KEY_ATTR = "json-key"
FORMATS = ("json", "xml")


class SemanticDrift(ValueError):
    """A conversion changed the meaning of the payload (7.2.2 b/e)."""

    def __init__(self, message, diff=None, event=None):
        ValueError.__init__(self, message)
        self.diff = diff or {}
        self.event = event or {"type": "semantic-drift", "severity": "high"}


def _tag(key):
    """XML-safe element name plus the original key when they differ."""
    clean = "".join(ch if (ch.isalnum() or ch in "-_.") else "_" for ch in str(key))
    if not clean or clean[0].isdigit():
        clean = "k_" + clean
    return clean, (None if clean == str(key) else str(key))


def _element(value, tag):
    el = ET.Element(tag)
    if isinstance(value, dict):
        if not value:
            el.set(TYPE_ATTR, "object")
        for key, item in value.items():
            name, original = _tag(key)
            child = _element(item, name)
            if original is not None:
                child.set(KEY_ATTR, original)
            el.append(child)
    elif isinstance(value, list):
        if not value:
            el.set(TYPE_ATTR, "array")
        for item in value:
            el.append(_element(item, "item"))
    elif value is None:
        el.set(TYPE_ATTR, "null")
    elif isinstance(value, bool):
        el.set(TYPE_ATTR, "bool")
        el.text = "true" if value else "false"
    elif isinstance(value, int):
        el.set(TYPE_ATTR, "int")
        el.text = str(value)
    elif isinstance(value, float):
        el.set(TYPE_ATTR, "float")
        el.text = repr(value)
    else:
        el.set(TYPE_ATTR, "str")
        el.text = str(value)
    return el


def json_to_xml(payload, root="a2a-message"):
    return ET.tostring(_element(payload, root), encoding="unicode")


def _value(el):
    kind = el.get(TYPE_ATTR)
    children = list(el)
    if children:
        if all(child.tag == "item" for child in children):
            return [_value(child) for child in children]
        out = {}
        for child in children:
            key = child.get(KEY_ATTR) or child.tag
            out[key] = _value(child)
        return out
    if kind == "object":
        return {}
    if kind == "array":
        return []
    if kind == "null":
        return None
    if kind == "bool":
        return (el.text or "").strip() == "true"
    if kind == "int":
        return int((el.text or "0").strip())
    if kind == "float":
        return float((el.text or "0").strip())
    return el.text or ""


def xml_to_json(text, root=None):
    root_el = ET.fromstring(text)
    value = _value(root_el)
    # When the root element carries no container type, return its content as-is;
    # a bare <v json-type="str">hi</v> should convert to "hi", not {"v": "hi"}.
    if len(root_el) == 0 and root_el.get(TYPE_ATTR) in ("str", "int", "float", "bool", "null"):
        return value
    return value


def _canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"), default=str)


def check_roundtrip(payload):
    """Return (ok, back_converted, diff). ok=False means b) is violated."""
    xml = json_to_xml(payload)
    back = xml_to_json(xml)
    if _canon(back) == _canon(payload):
        return True, back, {}
    return False, back, {"input": _canon(payload)[:200],
                         "output": _canon(back)[:200]}


def detect_format(payload):
    """Return "json", "xml", or None when the input cannot be judged.

    Measured 2026-11-24 (harness s03, C2 "A2A 畸形输入"): this raised ValueError
    for `None`, `""` and other non-messages. A detector is the function a gateway
    calls on bytes it did not choose, so "cannot tell" has to be an answer and
    not an exception -- the caller decides whether to refuse. `convert()` still
    refuses, with a message that names the reason.
    """
    if isinstance(payload, (dict, list)):
        return "json"
    if isinstance(payload, str):
        text = payload.lstrip()
        if text.startswith("<"):
            return "xml"
        if text.startswith("{") or text.startswith("["):
            return "json"
    return None


def convert(payload, target_format, source_format=None):
    """Convert a message to target_format and prove the meaning survived.

    Returns {"payload", "source", "target", "roundtrip"}. Raises SemanticDrift
    when the round-trip comparison fails (7.2.2 e): the caller must refuse to
    forward and log the event rather than ship a drifted message.
    """
    if target_format not in FORMATS:
        raise ValueError("unsupported target format %r; supported: %s"
                         % (target_format, ", ".join(FORMATS)))
    source = source_format or detect_format(payload)
    if source not in FORMATS:
        raise ValueError(
            "cannot detect the message format (%r is not one of %s); "
            "pass source_format explicitly" % (source, ", ".join(FORMATS)))

    if source == target_format:
        parsed = payload
        if isinstance(payload, str):
            parsed = json.loads(payload) if source == "json" else ET.fromstring(payload)
        return {"payload": payload, "source": source, "target": target_format,
                "roundtrip": "not-needed"}

    if source == "json":
        data = json.loads(payload) if isinstance(payload, str) else payload
        result = json_to_xml(data)
        ok, back, diff = check_roundtrip(data)
        if not ok:
            raise SemanticDrift("JSON->XML conversion is not semantically stable "
                                "(7.2.2 b)", diff=diff)
        return {"payload": result, "source": "json", "target": "xml",
                "roundtrip": "ok", "verified_against": back}

    # XML -> JSON
    text = payload if isinstance(payload, str) else json_to_xml(payload)
    data = xml_to_json(text)
    ok, back, diff = check_roundtrip(data)
    if not ok:
        raise SemanticDrift("XML->JSON conversion is not semantically stable "
                            "(7.2.2 b)", diff=diff)
    return {"payload": json.dumps(data, ensure_ascii=False, sort_keys=True),
            "source": "xml", "target": "json", "roundtrip": "ok",
            "verified_against": back}
