"""
Backend source of truth for how each agent type must be called.

Mirrors `executeFields` + `buildInputData()` of frontend Agents.jsx so that a
scheduled run (no UI) is validated deterministically.

To make a NEW agent type schedulable: add its entry to AGENT_INPUT_SPECS
(fields + manifest rule in build_manifest) — nothing else.

Field keys:
  name, label, type (text|textarea|number|select|checkbox|host), required,
  placeholder, options [{value,label}], default, help,
  show_when     {field: [values]}  field only applies when condition matches
  required_when {field: [values]}  field required when condition matches
  transform     "csv_list"         "a, b" -> ["a", "b"]
  min / max                        for number
"""
import re
from email.utils import getaddresses
from typing import Any, Dict, List, Optional, Set, Tuple

# Action kinds used by the permission policy
INTERNAL = "internal"
READ_EXTERNAL = "read_external"
WRITE_EXTERNAL = "write_external"
REMOTE_EXEC = "remote_exec"


def _f(
    name: str,
    label: str,
    type: str = "text",
    required: bool = False,
    placeholder: Optional[str] = None,
    options: Optional[List[Tuple[str, str]]] = None,
    default: Any = None,
    show_when: Optional[Dict[str, List[str]]] = None,
    required_when: Optional[Dict[str, List[str]]] = None,
    help: Optional[str] = None,
    transform: Optional[str] = None,
    min: Optional[int] = None,
    max: Optional[int] = None,
) -> Dict[str, Any]:
    field: Dict[str, Any] = {"name": name, "label": label, "type": type, "required": required}
    if placeholder is not None:
        field["placeholder"] = placeholder
    if options is not None:
        field["options"] = [{"value": v, "label": l} for v, l in options]
    if default is not None:
        field["default"] = default
    if show_when:
        field["show_when"] = show_when
    if required_when:
        field["required_when"] = required_when
    if help:
        field["help"] = help
    if transform:
        field["transform"] = transform
    if min is not None:
        field["min"] = min
    if max is not None:
        field["max"] = max
    return field


AGENT_INPUT_SPECS: Dict[str, Dict[str, Any]] = {
    "branch_code_review": {
        "label": "Code Review",
        "fields": [
            _f("branch", "Branch name", required=True, placeholder="feature/my-branch"),
        ],
    },
    "code_generator": {
        "label": "Code Generator",
        "fields": [
            _f("prompt", "Code generation prompt", "textarea", required=True,
               placeholder="Add OAuth2 authentication..."),
            _f("create_new_files", "Create new files", "checkbox", default=True),
            _f("test_mode", "Test mode (dry-run)", "checkbox", default=True),
        ],
    },
    "legal_fiscal": {
        "label": "Legal & Fiscal Expert",
        "fields": [
            _f("mode", "Analysis mode", "select", required=True, options=[
                ("analyze", "Analyze document"),
                ("risk_assessment", "Risk assessment"),
                ("compliance_check", "Compliance check"),
                ("claim_processing", "Claim processing"),
                ("document_drafting", "Document drafting"),
                ("legal_research", "Legal research"),
                ("training", "Training material"),
                ("monitoring", "Legislative monitoring"),
            ]),
            _f("query", "Query / instructions", "textarea", required=True,
               placeholder="Monitor new GDPR guidance..."),
            _f("documents", "Document paths (optional, comma-separated)",
               placeholder="/app/data/contract.pdf", transform="csv_list"),
        ],
    },
    "accounting_finance": {
        "label": "Accounting & Finance",
        "fields": [
            _f("mode", "Mode", "select", required=True, options=[
                ("accounting_entry", "Accounting entry"),
                ("strategic_advice", "Strategic advice"),
            ]),
            _f("query", "Query / instructions", "textarea", required=True,
               placeholder="Enter invoice details..."),
        ],
    },
    "travel_expert": {
        "label": "Travel Expert",
        "fields": [
            _f("mode", "Mode", "select", required=True, default="itinerary_planning", options=[
                ("itinerary_planning", "Itinerary planning"),
                ("destination_search", "Destination search"),
                ("budget_analysis", "Budget analysis"),
            ]),
            _f("query", "Travel request", "textarea", required=True,
               placeholder="Trip to Japan for 2 weeks, couple, budget 4000€..."),
        ],
    },
    "email_expert": {
        "label": "Email Expert",
        "fields": [
            _f("mode", "Email mode", "select", required=True, options=[
                ("analyze_inbox", "Analyze inbox (recap)"),
                ("send_email", "Send email"),
                ("send_email_llm", "Send email (LLM-generated)"),
            ]),
            _f("limit", "Number of emails to analyze", "number", default=20, min=1, max=100,
               show_when={"mode": ["analyze_inbox"]}),
            _f("unread_only", "Unread only", "checkbox", default=True,
               show_when={"mode": ["analyze_inbox"]}),
            _f("to", "To", placeholder="recipient@example.com",
               show_when={"mode": ["send_email", "send_email_llm"]},
               required_when={"mode": ["send_email", "send_email_llm"]}),
            _f("subject", "Subject", placeholder="Email subject",
               show_when={"mode": ["send_email", "send_email_llm"]}),
            _f("body", "Body", "textarea", placeholder="Email content...",
               show_when={"mode": ["send_email"]},
               required_when={"mode": ["send_email"]}),
            _f("instructions", "Instructions for the LLM", "textarea",
               placeholder="Write a weekly status update...",
               show_when={"mode": ["send_email_llm"]},
               required_when={"mode": ["send_email_llm"]}),
            _f("context", "Additional context", placeholder="Optional context",
               show_when={"mode": ["send_email_llm"]}),
            _f("auto_send", "Send automatically (otherwise only a draft is produced)", "checkbox",
               default=False, show_when={"mode": ["send_email_llm"]}),
        ],
    },
    "websearch": {
        "label": "Web Search",
        "fields": [
            _f("query", "Search query", required=True, placeholder="What to search for..."),
        ],
    },
    "skill": {
        "label": "Skill Agent",
        "fields": [
            _f("query", "Command", required=True, placeholder="disk | restart nginx | pods | logs sshd"),
            _f("host", "Target host", "host", required=True),
            _f("skill_id", "Skill ID (optional)", placeholder="ssh_admin"),
        ],
    },
    "gitea_code_generator": {
        "label": "Gitea Code Generator",
        "fields": [
            _f("prompt", "Code generation prompt", "textarea", required=True,
               placeholder="Add a health check endpoint /healthz..."),
            _f("create_new_files", "Create new files", "checkbox", default=True),
            _f("test_mode", "Test mode (dry-run, no commit)", "checkbox", default=False),
        ],
    },
    "datagouv_explorer": {
        "label": "DataGouv Explorer",
        "fields": [
            _f("mode", "Mode", "select", required=True, default="search", options=[
                ("search", "search — find datasets"),
                ("dataset", "dataset — detail + resources"),
                ("organization", "organization — search an org"),
                ("topic", "topic — DINUM API v2 themes"),
            ]),
            _f("query", "Query", placeholder="population par commune | INSEE",
               show_when={"mode": ["search", "organization"]},
               required_when={"mode": ["search"]}),
            _f("dataset_id", "Dataset ID or slug", placeholder="population-legale-2021",
               show_when={"mode": ["dataset"]}, required_when={"mode": ["dataset"]}),
            _f("topic_id", "Topic slug", placeholder="annuaire-des-entreprises",
               show_when={"mode": ["topic"]}, required_when={"mode": ["topic"]}),
            _f("org_id", "Organization slug", placeholder="direction-interministerielle-du-numerique",
               show_when={"mode": ["organization"]}),
            _f("page_size", "Page size", "number", default=10, min=1, max=100),
            _f("sort", "Sort", placeholder="-last_update",
               show_when={"mode": ["search"]}),
        ],
        "one_of": [
            {"when": {"mode": ["organization"]}, "fields": ["query", "org_id"]},
        ],
    },
}


# ─────────────────────────────── Validation ──────────────────────────────────

def _matches(cond: Optional[Dict[str, List[str]]], values: Dict[str, Any]) -> bool:
    """True when every (field -> allowed values) pair matches the current values."""
    if not cond:
        return False
    return all(values.get(key) in allowed for key, allowed in cond.items())


def _is_empty(value: Any) -> bool:
    return value is None or value == "" or value == []


def _coerce(field: Dict[str, Any], value: Any, errors: List[str], hosts: Optional[Set[str]]) -> Any:
    ftype = field["type"]
    label = field["label"]
    if _is_empty(value):
        return None

    if ftype in ("text", "textarea"):
        text = str(value).strip()
        if field.get("transform") == "csv_list":
            if isinstance(value, list):
                items = [str(x).strip() for x in value if str(x).strip()]
            else:
                items = [x.strip() for x in text.split(",") if x.strip()]
            return items or None
        return text or None

    if ftype == "number":
        try:
            number = int(float(str(value)))
        except (TypeError, ValueError):
            errors.append(f"'{label}' must be a number")
            return None
        if "min" in field and number < field["min"]:
            errors.append(f"'{label}' must be >= {field['min']}")
            return None
        if "max" in field and number > field["max"]:
            errors.append(f"'{label}' must be <= {field['max']}")
            return None
        return number

    if ftype == "checkbox":
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        return str(value).strip().lower() in ("true", "1", "yes", "on")

    if ftype == "select":
        text = str(value).strip()
        allowed = {o["value"] for o in field.get("options", [])}
        if text not in allowed:
            errors.append(f"'{label}' has an invalid value '{text}'")
            return None
        return text

    if ftype == "host":
        text = str(value).strip()
        if hosts is not None and text not in hosts:
            errors.append(f"Unknown host '{text}'")
            return None
        return text or None

    return value


def validate_input(
    agent_type: str,
    raw: Optional[Dict[str, Any]],
    hosts: Optional[Set[str]] = None,
) -> Tuple[Dict[str, Any], List[str]]:
    """Validate and normalise input_data. Returns (cleaned_input, errors)."""
    spec = AGENT_INPUT_SPECS.get(agent_type)
    if spec is None:
        return {}, [f"Agent type '{agent_type}' is not supported by the scheduler"]

    raw = raw or {}
    errors: List[str] = []
    cleaned: Dict[str, Any] = {}

    # Fields are declared with controlling fields (mode) first, so conditions
    # can be evaluated against what is already cleaned.
    for field in spec["fields"]:
        if field.get("show_when") and not _matches(field["show_when"], cleaned):
            continue

        value = raw.get(field["name"])
        if value is None:
            value = field.get("default")
        value = _coerce(field, value, errors, hosts)

        if _is_empty(value):
            required = field.get("required") or _matches(field.get("required_when"), cleaned)
            if required:
                errors.append(f"'{field['label']}' is required")
            continue
        cleaned[field["name"]] = value

    for rule in spec.get("one_of", []):
        if _matches(rule["when"], cleaned) and not any(not _is_empty(cleaned.get(n)) for n in rule["fields"]):
            errors.append("At least one of these fields is required: " + ", ".join(rule["fields"]))

    return cleaned, errors


# ─────────────────────────────── Manifest ────────────────────────────────────

def _action(kind: str, label: str, **extra: Any) -> Dict[str, Any]:
    return {"kind": kind, "label": label, **extra}


def _parse_recipients(value: Any) -> List[str]:
    if not value:
        return []
    return [addr.strip() for _, addr in getaddresses([str(value)]) if addr and addr.strip()]


def prompt_manifest() -> List[Dict[str, Any]]:
    return [_action(INTERNAL, "Run an LLM prompt with your configured provider")]


def build_manifest(
    agent_type: str,
    cleaned_input: Dict[str, Any],
    agent_config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Static, deterministic list of what a run will do (used by the policy)."""
    cfg = agent_config or {}
    mode = cleaned_input.get("mode")

    if agent_type == "email_expert":
        mailbox = (cfg.get("email_config") or {}).get("email") or "mailbox"
        if mode == "analyze_inbox":
            return [_action(READ_EXTERNAL, f"Read mailbox {mailbox} via IMAP")]
        recipients = _parse_recipients(cleaned_input.get("to"))
        to_label = ", ".join(recipients) or str(cleaned_input.get("to") or "?")
        if mode == "send_email":
            return [_action(WRITE_EXTERNAL, f"Send an email to {to_label}", recipients=recipients)]
        if mode == "send_email_llm":
            if cleaned_input.get("auto_send"):
                return [_action(WRITE_EXTERNAL, f"Generate and send an email to {to_label}", recipients=recipients)]
            return [_action(INTERNAL, "Generate an email draft with the LLM (not sent)")]
        return [_action(READ_EXTERNAL, "Access the mailbox")]

    if agent_type == "websearch":
        return [_action(READ_EXTERNAL, f"Search the web (DuckDuckGo): {cleaned_input.get('query', '')}")]

    if agent_type == "datagouv_explorer":
        return [_action(READ_EXTERNAL, "Query the data.gouv.fr API")]

    if agent_type == "skill":
        return [_action(
            REMOTE_EXEC,
            f"Run '{cleaned_input.get('query', '')}' on host {cleaned_input.get('host', '?')}",
            host=cleaned_input.get("host"),
        )]

    if agent_type in ("code_generator", "gitea_code_generator"):
        if cleaned_input.get("test_mode"):
            return [_action(READ_EXTERNAL, "Read the Git repository (dry-run, nothing is committed)")]
        return [_action(WRITE_EXTERNAL, "Generate code and commit to the Git repository")]

    if agent_type == "branch_code_review":
        if cfg.get("auto_fix") or cfg.get("auto_create_pr"):
            return [_action(WRITE_EXTERNAL, "Review the branch, push fixes and/or open a pull request")]
        return [_action(READ_EXTERNAL, "Read the branch on the Git repository")]

    # legal_fiscal, accounting_finance, travel_expert: LLM + local RAG only
    return [_action(INTERNAL, "LLM analysis (no external action)")]


def supported_agent_types() -> List[str]:
    return list(AGENT_INPUT_SPECS.keys())


_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def is_plausible_email(value: str) -> bool:
    return bool(_EMAIL_RE.match((value or "").strip()))
