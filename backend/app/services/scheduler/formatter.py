"""Turn heterogeneous agent results into readable markdown text."""
import json
from typing import Any, Dict

MAX_TEXT = 100_000
_TEXT_KEYS = ("content", "result", "output", "summary", "text", "message", "answer", "response")


def _clip(value: str, limit: int) -> str:
    return value if len(value) <= limit else value[:limit].rstrip() + "…"


def result_to_text(result: Any) -> str:
    return _clip(_render(result, 0).strip(), MAX_TEXT)


def error_to_text(payload: Any) -> str:
    if payload is None:
        return "Unknown error"
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("error", "message", "detail"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value
    return _clip(json.dumps(payload, ensure_ascii=False, default=str), 2000)


def _render(obj: Any, depth: int) -> str:
    if obj is None:
        return ""
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (int, float, bool)):
        return str(obj)
    if isinstance(obj, dict):
        if isinstance(obj.get("emails"), list) and "total_emails" in obj:
            return _render_inbox(obj)
        if isinstance(obj.get("results"), list) and "query" in obj:
            return _render_search(obj)
        for key in _TEXT_KEYS:
            value = obj.get(key)
            if isinstance(value, str) and value.strip():
                return value
        inner = obj.get("data")
        if isinstance(inner, (dict, str)) and depth < 3:
            text = _render(inner, depth + 1)
            if text:
                return text
    dumped = json.dumps(obj, ensure_ascii=False, indent=2, default=str)
    return "```json\n" + _clip(dumped, 20000) + "\n```"


def _render_inbox(obj: Dict[str, Any]) -> str:
    emails = obj.get("emails") or []
    if not emails:
        return str(obj.get("message") or "No emails found.")
    lines = [f"## Inbox recap ({obj.get('total_emails', len(emails))} emails)"]
    summary = obj.get("summary")
    if isinstance(summary, str) and summary.strip():
        lines += ["", summary.strip()]
    for item in emails[:30]:
        if not isinstance(item, dict):
            continue
        subject = _clip(str(item.get("subject") or "(no subject)"), 120)
        lines.append("")
        lines.append(f"- **{subject}** — {item.get('from', '?')} ({item.get('date', '')})")
        analysis = item.get("llm_analysis")
        raw = analysis.get("raw_analysis") if isinstance(analysis, dict) else ""
        if raw:
            lines.append("  " + _clip(" ".join(str(raw).split()), 300))
    return "\n".join(lines)


def _render_search(obj: Dict[str, Any]) -> str:
    results = obj.get("results") or []
    if not results:
        return str(obj.get("message") or f"No results for '{obj.get('query')}'.")
    lines = [f"## Web search: {obj.get('query')}", ""]
    for item in results[:15]:
        if not isinstance(item, dict):
            continue
        title = _clip(str(item.get("title") or item.get("url") or "result"), 140)
        url = item.get("url") or ""
        lines.append(f"- [{title}]({url})" if url else f"- {title}")
        snippet = item.get("snippet")
        if snippet:
            lines.append("  " + _clip(" ".join(str(snippet).split()), 300))
    return "\n".join(lines)
