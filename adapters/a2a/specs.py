"""Tool/model interface descriptor validation.

Clause anchor: T/ISC 0174-2026 section 7.1.1 b).

    7.1.1 b) 应支持通用模型接口定义规范的解析与校验。

"General model interface definition" in practice means the tool descriptor a model
platform hands to an agent: a name, a description the model reads to decide when to
call it, and a JSON Schema for its arguments. The gateway's job at 7.1.1 b) is to
*parse and validate* that descriptor before forwarding, because an unparseable or
under-specified descriptor produces a call the model cannot make correctly - and
the failure shows up as a wrong tool invocation, not as a schema error.

Scope, stated so it is not over-read: this validates MCP-style/function-calling
descriptors (name, description, inputSchema). It does not parse full OpenAPI
documents, and it does not judge whether the schema is *good*, only whether it is
well-formed and complete enough to be actionable.
"""

REQUIRED = ("name", "description", "inputSchema")


def validate_tool_descriptor(descriptor):
    """Return a list of {"code", "field", "message"}; empty list = valid."""
    problems = []

    def bad(code, field, message):
        problems.append({"code": code, "field": field, "message": message})

    if not isinstance(descriptor, dict):
        bad("D1", None, "tool descriptor must be a JSON object")
        return problems

    for field in REQUIRED:
        value = descriptor.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            bad("D1", field, "required field missing or empty: %s" % field)

    name = descriptor.get("name")
    if isinstance(name, str) and name.strip():
        if any(ch.isspace() for ch in name):
            bad("D2", "name", "tool name must not contain whitespace: %r" % name)
        if len(name) > 64:
            bad("D2", "name", "tool name longer than 64 characters")

    description = descriptor.get("description")
    if isinstance(description, str) and description.strip():
        if len(description.strip()) < 8:
            bad("D3", "description",
                "description too short to be actionable for a model (%d chars)"
                % len(description.strip()))

    schema = descriptor.get("inputSchema")
    if schema is not None:
        if not isinstance(schema, dict):
            bad("D4", "inputSchema", "inputSchema must be a JSON object")
        else:
            if schema.get("type") != "object":
                bad("D4", "inputSchema.type",
                    "inputSchema.type must be 'object', got %r" % (schema.get("type"),))
            properties = schema.get("properties")
            if properties is None:
                bad("D5", "inputSchema.properties",
                    "inputSchema has no properties; a model cannot know its arguments")
            elif not isinstance(properties, dict):
                bad("D5", "inputSchema.properties", "properties must be an object")
            required = schema.get("required")
            if required is not None:
                if not isinstance(required, list) or not all(
                        isinstance(item, str) for item in required):
                    bad("D6", "inputSchema.required", "required must be a list of strings")
                elif isinstance(properties, dict):
                    unknown = [item for item in required if item not in properties]
                    if unknown:
                        bad("D6", "inputSchema.required",
                            "required names not declared in properties: %s" % unknown)
            extra = schema.get("additionalProperties")
            if extra is not None and not isinstance(extra, (bool, dict)):
                bad("D7", "inputSchema.additionalProperties",
                    "additionalProperties must be boolean or a schema object")
    return problems


def validate_tool_descriptors(descriptors):
    """Validate a list; returns {"ok", "valid", "invalid": [{index, errors}]}."""
    if not isinstance(descriptors, list) or not descriptors:
        return {"ok": False, "valid": 0,
                "invalid": [{"index": None,
                             "errors": [{"code": "D0", "field": None,
                                         "message": "a non-empty list of tool descriptors is required"}]}]}
    invalid, seen = [], {}
    for index, descriptor in enumerate(descriptors):
        errors = validate_tool_descriptor(descriptor)
        if isinstance(descriptor, dict):
            name = descriptor.get("name")
            if name in seen:
                errors.append({"code": "D8", "field": "name",
                               "message": "duplicate tool name %r (also at index %d)"
                                          % (name, seen[name])})
            elif isinstance(name, str):
                seen[name] = index
        if errors:
            invalid.append({"index": index, "errors": errors})
    return {"ok": not invalid, "valid": len(descriptors) - len(invalid),
            "invalid": invalid}


MCP_EXAMPLE = {
    "name": "uibc_verify",
    "description": "校验一个 UIBC 证据包，返回 S1-S6 逐项结果与判定",
    "inputSchema": {
        "type": "object",
        "properties": {
            "package": {"type": "string", "description": "相对包路径"},
            "did": {"type": "string", "description": "可选：用 DID 代替裸公钥"},
        },
        "required": ["package"],
        "additionalProperties": False,
    },
}
