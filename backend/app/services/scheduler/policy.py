"""
Permission policy evaluated BEFORE a run starts (pre-flight).

Modes:
  manual   : any non-internal action requires an explicit approval
  auto     : no question asked, but writes to third-party recipients are refused
  skip_all : no guardrail at all (explicit opt-in)
"""
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional

SENSITIVE_KINDS = {"read_external", "write_external", "remote_exec"}
VALID_MODES = ("manual", "auto", "skip_all")


@dataclass
class PolicyDecision:
    outcome: str  # allow | ask | deny
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {"outcome": self.outcome, "reason": self.reason}


def evaluate(
    mode: str,
    manifest: List[Dict[str, Any]],
    user_email: Optional[str],
    allowed_recipients: Optional[Iterable[str]],
) -> PolicyDecision:
    if mode == "skip_all":
        return PolicyDecision("allow", "Approval and perimeter checks are bypassed (skip_all)")

    if mode == "manual":
        sensitive = [a for a in manifest if a.get("kind") in SENSITIVE_KINDS]
        if sensitive:
            return PolicyDecision(
                "ask", f"{len(sensitive)} external action(s) require your approval before the run"
            )
        return PolicyDecision("allow", "Internal-only task: no approval required")

    if mode == "auto":
        allowed = {(user_email or "").strip().lower()} if user_email else set()
        allowed |= {str(r).strip().lower() for r in (allowed_recipients or []) if r}
        for action in manifest:
            if action.get("kind") != "write_external":
                continue
            for recipient in action.get("recipients", []) or []:
                if recipient.strip().lower() not in allowed:
                    return PolicyDecision(
                        "deny",
                        f"Recipient '{recipient}' is outside the allowed perimeter. "
                        "Add it to the allowed recipients, or use manual / skip_all mode.",
                    )
        return PolicyDecision("allow", "Within the agent's configured perimeter")

    return PolicyDecision("deny", f"Unknown permission mode '{mode}'")
