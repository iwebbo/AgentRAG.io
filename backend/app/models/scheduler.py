"""
Scheduler models.

Tables:
  - scheduled_tasks      : task definition (agent or prompt) + cron + permission policy
  - scheduled_task_runs  : one row per execution attempt (state machine)
  - notifications        : in-app inbox (+ email delivery status)

Run status lifecycle:
  queued -> running -> success | failed
  queued -> running -> awaiting_approval -> (approve) queued -> running -> ...
                                         -> (reject)  rejected
                                         -> (timeout) expired
  skipped : a previous run of the same task was still active when the tick fired
"""
import uuid

from sqlalchemy import (
    Column, String, Text, Boolean, Integer, Float, DateTime,
    ForeignKey, JSON, Index, UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from app.database import Base


class ScheduledTask(Base):
    __tablename__ = "scheduled_tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    # Identity
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Target: "agent" (existing agent + input_data) or "prompt" (plain LLM prompt)
    task_type = Column(String(20), nullable=False)
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    input_data = Column(JSON, default=dict)
    prompt = Column(Text, nullable=True)
    llm_provider = Column(String(100), nullable=True)
    llm_model = Column(String(255), nullable=True)
    llm_temperature = Column(Float, nullable=True)

    # Frequency
    cron_expr = Column(String(100), nullable=False)
    timezone = Column(String(64), nullable=False, default="UTC")
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    is_enabled = Column(Boolean, nullable=False, default=True)

    # Permissions: manual | auto | skip_all
    permission_mode = Column(String(20), nullable=False, default="manual")
    allowed_recipients = Column(JSON, default=list)
    approval_timeout_minutes = Column(Integer, nullable=False, default=1440)

    # Notifications
    notify_channels = Column(JSON, default=list)  # ["in_app", "email"]
    notify_on = Column(String(20), nullable=False, default="always")  # always|success|failure

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "name", name="uq_scheduled_task_user_name"),
        Index("ix_scheduled_tasks_due", "is_enabled", "next_run_at"),
    )


class ScheduledTaskRun(Base):
    __tablename__ = "scheduled_task_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    task_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_tasks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    status = Column(String(20), nullable=False, default="queued", index=True)
    triggered_by = Column(String(20), nullable=False, default="schedule")  # schedule | manual
    scheduled_for = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    heartbeat_at = Column(DateTime(timezone=True), nullable=True)

    # Links to existing objects
    agent_execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    conversation_id = Column(UUID(as_uuid=True), nullable=True)

    # Result
    result_text = Column(Text, nullable=True)
    result_data = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    # Approval (permission_mode == manual)
    approval_manifest = Column(JSON, nullable=True)
    approval_expires_at = Column(DateTime(timezone=True), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_scheduled_task_runs_status_created", "status", "created_at"),
    )


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type = Column(String(30), nullable=False)  # task_result | task_failed | approval_required
    title = Column(String(255), nullable=False)
    body = Column(Text, nullable=True)
    run_id = Column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_task_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    is_read = Column(Boolean, nullable=False, default=False)
    email_status = Column(String(20), nullable=True)  # sent | failed | skipped
    email_error = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_notifications_user_unread", "user_id", "is_read"),
    )
