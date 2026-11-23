"""Export a readable, credential-free API reference from FastAPI OpenAPI."""

from __future__ import annotations

import json
import os
import sys
from urllib.request import urlopen
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OPENAPI_URL = os.getenv("OPENAPI_URL", "http://127.0.0.1:9000/openapi.json")


def resolve(schema: dict[str, Any], document: dict[str, Any]) -> dict[str, Any]:
    ref = schema.get("$ref")
    if not ref:
        return schema
    node: Any = document
    for part in ref.removeprefix("#/ ").replace("#/", "").split("/"):
        node = node[part]
    return node


def type_name(schema: dict[str, Any], document: dict[str, Any]) -> str:
    schema = resolve(schema, document)
    if "anyOf" in schema:
        return " | ".join(type_name(item, document) for item in schema["anyOf"])
    if "oneOf" in schema:
        return " | ".join(type_name(item, document) for item in schema["oneOf"])
    kind = schema.get("type") or schema.get("title") or "object"
    if kind == "array":
        return f"array<{type_name(schema.get('items', {}), document)}>"
    if schema.get("format"):
        return f"{kind} ({schema['format']})"
    return str(kind)


def describe_fields(
    schema: dict[str, Any], document: dict[str, Any], indent: str = "    ", depth: int = 0
) -> list[str]:
    if depth > 4:
        return [f"{indent}(nested object)"]
    schema = resolve(schema, document)
    if "anyOf" in schema or "oneOf" in schema:
        choices = schema.get("anyOf") or schema.get("oneOf") or []
        return [f"{indent}Allowed: " + " | ".join(type_name(item, document) for item in choices)]
    if schema.get("type") == "array":
        return [f"{indent}Items: {type_name(schema.get('items', {}), document)}"]
    properties = schema.get("properties") or {}
    if not properties:
        return [f"{indent}Type: {type_name(schema, document)}"]
    required = set(schema.get("required") or [])
    lines: list[str] = []
    for name, raw in properties.items():
        field = resolve(raw, document)
        marker = "required" if name in required else "optional"
        details = []
        if "default" in field:
            details.append(f"default={json.dumps(field['default'], ensure_ascii=False)}")
        if "enum" in field:
            details.append("values=" + json.dumps(field["enum"], ensure_ascii=False))
        if field.get("description"):
            details.append(" ".join(str(field["description"]).split()))
        suffix = f"; {'; '.join(details)}" if details else ""
        lines.append(f"{indent}- {name}: {type_name(raw, document)} [{marker}{suffix}]")
        if (field.get("properties") or field.get("type") == "array") and depth < 3:
            lines.extend(describe_fields(field, document, indent + "  ", depth + 1))
    return lines


def request_example(schema: dict[str, Any], document: dict[str, Any], depth: int = 0) -> Any:
    if depth > 3:
        return {}
    schema = resolve(schema, document)
    if "example" in schema:
        return schema["example"]
    choices = schema.get("anyOf") or schema.get("oneOf")
    if choices:
        non_null = [item for item in choices if item.get("type") != "null"]
        return request_example((non_null or choices)[0], document, depth + 1)
    kind = schema.get("type")
    if kind == "array":
        return [request_example(schema.get("items", {}), document, depth + 1)]
    if kind == "integer":
        return schema.get("default", 0)
    if kind == "number":
        return schema.get("default", 0.0)
    if kind == "boolean":
        return schema.get("default", False)
    if kind == "string":
        if schema.get("enum"):
            return schema["enum"][0]
        return schema.get("default", f"<{schema.get('title', 'string')}>")
    props = schema.get("properties") or {}
    required = set(schema.get("required") or [])
    return {
        key: request_example(value, document, depth + 1)
        for key, value in props.items()
        if key in required
    }


def export() -> str:
    with urlopen(OPENAPI_URL, timeout=15) as response:
        spec = json.load(response)
    operations: list[tuple[str, str, dict[str, Any]]] = []
    for path, path_item in spec.get("paths", {}).items():
        for method, operation in path_item.items():
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}:
                operations.append((path, method.upper(), operation))
    operations.sort(key=lambda item: (item[0], item[1]))

    lines = [
        "AI CHATBOT - COMPLETE API REFERENCE",
        "=" * 80,
        "",
        f"API title: {spec.get('info', {}).get('title', 'AI Chatbot API')}",
        f"API version: {spec.get('info', {}).get('version', 'unknown')}",
        f"Total operations: {len(operations)}",
        "",
        "BASE URL",
        "--------",
        "Development: http://localhost:9000",
        "Production:  https://<your-api-domain>",
        "Frontend override: set VITE_API_ORIGIN=https://<your-api-domain>",
        "",
        "STANDARD HEADERS",
        "----------------",
        "Authenticated JSON request:",
        "  Authorization: Bearer <admin-jwt>",
        "  Accept: application/json",
        "  Content-Type: application/json",
        "  X-Request-Id: <optional-client-correlation-id>",
        "",
        "Multipart request:",
        "  Authorization: Bearer <admin-jwt>",
        "  Accept: application/json",
        "  Content-Type: multipart/form-data; boundary=<set automatically by browser>",
        "",
        "Public endpoints do not require Authorization. Endpoint-level Authentication",
        "below states what the OpenAPI document declares. Tenant and role permissions are",
        "still enforced by the server even where OpenAPI cannot express the exact role.",
        "Never place passwords, JWTs, API keys, or MongoDB credentials in URLs or logs.",
        "",
        "COMMON ERROR RESPONSE",
        "---------------------",
        '  {"detail": "Human-readable error", "request_id": "req_..."}',
        "  400 invalid input | 401 missing/expired token | 403 forbidden",
        "  404 not found | 409 conflict | 422 validation | 500/502 server/provider failure",
        "  Preserve the X-Request-Id response header for Errors & health tracing.",
        "",
        "ENDPOINTS",
        "=" * 80,
    ]

    for number, (path, method, op) in enumerate(operations, 1):
        lines.extend(["", f"[{number:03d}] {method} {path}", "-" * 80])
        lines.append(f"Name: {op.get('summary') or op.get('operationId') or 'Unnamed operation'}")
        if op.get("description"):
            lines.append("Description: " + " ".join(op["description"].split()))
        lines.append("Tags: " + ", ".join(op.get("tags") or ["untagged"]))
        security = op.get("security", spec.get("security", []))
        lines.append("Authentication: " + ("Bearer token / declared security scheme" if security else "Public / no scheme declared"))

        params = op.get("parameters") or []
        if params:
            lines.append("Parameters:")
            for param in params:
                req = "required" if param.get("required") else "optional"
                schema = param.get("schema") or {}
                extra = f"; default={json.dumps(schema['default'])}" if "default" in schema else ""
                desc = " ".join(str(param.get("description") or "").split())
                if desc:
                    extra += f"; {desc}"
                lines.append(
                    f"  - {param.get('name')}: {type_name(schema, spec)} "
                    f"[{param.get('in')}, {req}{extra}]"
                )
        else:
            lines.append("Parameters: none")

        body = op.get("requestBody")
        if body:
            lines.append("Request body: " + ("required" if body.get("required") else "optional"))
            for content_type, media in (body.get("content") or {}).items():
                schema = media.get("schema") or {}
                lines.append(f"  Content-Type: {content_type}")
                lines.extend(describe_fields(schema, spec, "    "))
                if content_type == "application/json":
                    lines.append("  Example JSON:")
                    example = request_example(schema, spec)
                    lines.extend("    " + line for line in json.dumps(example, indent=2, ensure_ascii=False).splitlines())
        else:
            lines.append("Request body: none")

        lines.append("Responses:")
        for status, response in (op.get("responses") or {}).items():
            lines.append(f"  - {status}: {response.get('description', '')}")
            for content_type, media in (response.get("content") or {}).items():
                lines.append(f"      Content-Type: {content_type}")
                lines.extend(describe_fields(media.get("schema") or {}, spec, "      "))

        curl_path = path
        lines.append("cURL template:")
        lines.append(f"  curl -X {method} \"https://<your-api-domain>{curl_path}\" \\")
        lines.append('    -H "Accept: application/json" \\')
        if security:
            lines.append('    -H "Authorization: Bearer <admin-jwt>" \\')
        if body and "application/json" in (body.get("content") or {}):
            lines.append('    -H "Content-Type: application/json" \\')
            schema = body["content"]["application/json"].get("schema") or {}
            compact = json.dumps(request_example(schema, spec), ensure_ascii=False)
            lines.append(f"    --data-raw '{compact}'")
        else:
            # Remove the visual continuation marker from the final header line.
            lines[-1] = lines[-1].removesuffix(" \\")

    lines.extend([
        "",
        "=" * 80,
        "END OF API REFERENCE",
        f"Generated from the live FastAPI OpenAPI schema at {OPENAPI_URL}.",
    ])
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    destination = ROOT / "docs" / "FULL_API_REFERENCE.txt"
    destination.write_text(export(), encoding="utf-8")
    print(f"Wrote {destination}")
