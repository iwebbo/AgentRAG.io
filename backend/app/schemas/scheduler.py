from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


# ───────────────────────────── Task payloads ─────────────────────────────────

class TaskDraft(BaseModel):
    """Lenient payload used by /tasks/validate (live form validation)."""
    name: str = ""
    description: Optional[str] = None
    task_type: str = "agent"
    agent_id: Optional[UUID] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    prompt: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = Field(default=None, ge=0.0, le=2.0)
    cron_expr: str = ""
    timezone: str = "UTC"
    permission_mode: str = "manual"
    allowed_recipients: List[str] = Field(default_factory=list)
    approval_timeout_minutes: int = Field(default=1440, ge=5, le=10080)
    notify_channels: List[str] = Field(default_factory=lambda: ["in_app"])
    notify_on: str = "always"
    confirm_skip_all: bool = False


class TaskPayload(TaskDraft):
    """Strict payload used by create / update."""
    name: str = Field(..., min_length=1, max_length=255)
    task_type: Literal["agent", "prompt"]
    cron_expr: str = Field(..., min_length=1, max_length=100)
    permission_mode: Literal["manual", "auto", "skip_all"] = "manual"
    allowed_recipients: List[EmailStr] = Field(default_factory=list)
    notify_channels: List[Literal["in_app", "email"]] = Field(default_factory=lambda: ["in_app"])
    notify_on: Literal["always", "success", "failure"] = "always"

    @field_validator("name", "cron_expr")
    @classmethod
    def _strip(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("must not be empty")
        return v


class RunNowRequest(BaseModel):
    confirm: bool = False


# ───────────────────────────── Task responses ────────────────────────────────

class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: Optional[str] = None
    task_type: str
    agent_id: Optional[UUID] = None
    agent_name: Optional[str] = None
    agent_type: Optional[str] = None
    input_data: Dict[str, Any] = Field(default_factory=dict)
    prompt: Optional[str] = None
    llm_provider: Optional[str] = None
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    cron_expr: str
    timezone: str
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    is_enabled: bool
    permission_mode: str
    allowed_recipients: List[str] = Field(default_factory=list)
    approval_timeout_minutes: int
    notify_channels: List[str] = Field(default_factory=list)
    notify_on: str
    manifest: List[Dict[str, Any]] = Field(default_factory=list)
    policy: Optional[Dict[str, Any]] = None
    last_run_status: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


# ───────────────────────────── Run responses ─────────────────────────────────

class RunListItem(BaseModel):
    id: UUID
    task_id: UUID
    task_name: Optional[str] = None
    status: str
    triggered_by: str
    scheduled_for: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result_preview: Optional[str] = None
    error: Optional[str] = None
    approval_expires_at: Optional[datetime] = None
    conversation_id: Optional[UUID] = None
    created_at: Optional[datetime] = None


class RunDetail(RunListItem):
    result_text: Optional[str] = None
    approval_manifest: Optional[Dict[str, Any]] = None
    agent_execution_id: Optional[UUID] = None
    approved_at: Optional[datetime] = None


# ───────────────────────────── Notifications ─────────────────────────────────

class NotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    type: str
    title: str
    body: Optional[str] = None
    run_id: Optional[UUID] = None
    is_read: bool
    email_status: Optional[str] = None
    email_error: Optional[str] = None
    created_at: Optional[datetime] = None
