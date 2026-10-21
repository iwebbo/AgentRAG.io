"""
SchemaCheck — la réponse respecte-t-elle un format attendu ? (surtout utile côté agents)

S'active uniquement si le contexte porte `expected_format` ("json" | "yaml") et/ou
`expected_schema`. Sinon : SKIPPED.

`expected_schema` est un sous-ensemble volontairement réduit de JSON Schema, évalué
sans dépendance externe :

    {
      "type": "object",
      "required": ["summary", "features"],
      "properties": {
        "summary":  {"type": "string", "minLength": 1},
        "features": {"type": "array", "minItems": 1, "items": {"type": "object"}},
        "level":    {"type": "string", "enum": ["low", "high"]}
      }
    }

Mots-clés supportés : type, required, properties, items, enum, minItems, maxItems,
minLength, maxLength.
"""
from __future__ import annotations

from typing import Any, List, Optional, Sequence

from .base import (
    CheckResult,
    Finding,
    Severity,
    VerificationContext,
    extract_fenced_blocks,
    extract_json_object,
    strip_think,
)

try:
    import yaml  # type: ignore
except Exception:  # pragma: no cover
    yaml = None  # type: ignore

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "array": lambda v: isinstance(v, list),
    "object": lambda v: isinstance(v, dict),
    "null": lambda v: v is None,
}
_MAX_DEPTH = 8
_MAX_FINDINGS = 10


def validate_schema(value: Any, schema: dict, path: str = "$", depth: int = 0) -> List[str]:
    """Retourne la liste des violations (chaînes lisibles). Vide = conforme."""
    errors: List[str] = []
    if depth > _MAX_DEPTH or not isinstance(schema, dict):
        return errors

    expected_type = schema.get("type")
    if expected_type:
        types = expected_type if isinstance(expected_type, list) else [expected_type]
        if not any(_TYPE_CHECKS.get(t, lambda _v: True)(value) for t in types):
            errors.append(f"{path}: expected {'/'.join(map(str, types))}, got {type(value).__name__}")
            return errors

    if "enum" in schema and value not in schema["enum"]:
        errors.append(f"{path}: value {value!r} not in {schema['enum']!r}")

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append(f"{path}: string shorter than {schema['minLength']}")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append(f"{path}: string longer than {schema['maxLength']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append(f"{path}: fewer than {schema['minItems']} item(s)")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append(f"{path}: more than {schema['maxItems']} item(s)")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(value[:50]):
                errors.extend(validate_schema(item, items, f"{path}[{index}]", depth + 1))

    if isinstance(value, dict):
        for key in schema.get("required", []) or []:
            if key not in value:
                errors.append(f"{path}: missing required key '{key}'")
        for key, sub in (schema.get("properties") or {}).items():
            if key in value:
                errors.extend(validate_schema(value[key], sub, f"{path}.{key}", depth + 1))

    return errors[:_MAX_FINDINGS * 2]


def _extract_yaml(text: str) -> Optional[Any]:
    if yaml is None:
        return None
    cleaned = strip_think(text)
    for block in extract_fenced_blocks(cleaned):
        if block.lang in ("yaml", "yml") and block.closed:
            cleaned = block.code
            break
    try:
        return yaml.safe_load(cleaned)
    except Exception:
        return None


class SchemaCheck:
    name = "schema"
    blocking = False

    def run(self, response: str, ctx: VerificationContext, prior: Sequence[CheckResult]) -> CheckResult:
        fmt = (ctx.expected_format or "").lower() or None
        schema = ctx.expected_schema
        if not fmt and not schema:
            return CheckResult.skipped(self.name, "no expected format")
        fmt = fmt or "json"

        if fmt == "json":
            parsed = extract_json_object(response)
            if parsed is None:
                return CheckResult.from_findings(self.name, [Finding(
                    "schema.invalid_json",
                    Severity.ERROR,
                    "The answer is expected to be a single valid JSON value but could not be parsed.",
                )])
        elif fmt in ("yaml", "yml"):
            if yaml is None:
                return CheckResult.skipped(self.name, "PyYAML not installed")
            parsed = _extract_yaml(response)
            if parsed is None:
                return CheckResult.from_findings(self.name, [Finding(
                    "schema.invalid_yaml",
                    Severity.ERROR,
                    "The answer is expected to be valid YAML but could not be parsed.",
                )])
        else:
            return CheckResult.skipped(self.name, f"unsupported format {fmt!r}")

        findings: List[Finding] = []
        if schema:
            for message in validate_schema(parsed, schema)[:_MAX_FINDINGS]:
                findings.append(Finding("schema.violation", Severity.ERROR, f"Schema violation — {message}"))
        return CheckResult.from_findings(self.name, findings)
