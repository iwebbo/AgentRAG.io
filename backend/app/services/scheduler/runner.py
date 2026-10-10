"""
Runner: executes ONE scheduled run, headless, inside a worker thread.

Each run uses its own SQLAlchemy session and its own asyncio event loop, so
blocking calls (IMAP, smtplib, DuckDuckGo...) do not affect other runs.

Entry point: execute_run(run_id)  — never raises.
"""
import asyncio
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.database import SessionLocal
from app.models import Agent, AgentExecution, Conversation, User
from app.models.scheduler import ScheduledTask, ScheduledTaskRun
from app.services import notification_service
from app.services.scheduler import catalog, policy
from app.services.scheduler.formatter import error_to_text, result_to_text

logger = logging.getLogger(__name__)

MAX_RESULT_DATA_BYTES = 1_000_000
MAX_ERROR_CHARS = 20_000


class RunFailure(Exception):
    """Controlled failure with a user-facing message."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    """Make the value JSON-serialisable and bounded in size."""
    if value is None:
        return None
    try:
        dumped = json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return {"unserializable": True}
    if len(dumped.encode("utf-8")) > MAX_RESULT_DATA_BYTES:
        return {"truncated": True, "reason": "result too large to store as structured data"}
    return json.loads(dumped)


class _Beat:
    """Throttled heartbeat so the engine can detect a dead worker."""

    def __init__(self, run_id: UUID, every_seconds: int = 20):
        self.run_id = run_id
        self.every = every_seconds
        self.last = time.monotonic()

    def tick(self, db) -> None:
        if time.monotonic() - self.last < self.every:
            return
        self.last = time.monotonic()
        db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == self.run_id).update(
            {"heartbeat_at": utcnow()}, synchronize_session=False
        )
        db.commit()


# ─────────────────────────── State transitions ───────────────────────────────

def _complete(
    db,
    run_id: UUID,
    status: str,
    *,
    result_text: Optional[str] = None,
    result_data: Any = None,
    error: Optional[str] = None,
) -> Optional[ScheduledTaskRun]:
    run = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
    if run is None:
        return None
    now = utcnow()
    run.status = status
    run.completed_at = now
    run.heartbeat_at = now
    if result_text is not None:
        run.result_text = result_text
    if result_data is not None:
        run.result_data = result_data
    if error is not None:
        run.error = error[:MAX_ERROR_CHARS]
    task = db.query(ScheduledTask).filter(ScheduledTask.id == run.task_id).first()
    if task is not None:
        task.last_run_at = now
    db.commit()
    return run


def mark_execution_failed(db, execution_id: Optional[UUID], message: str) -> None:
    """Close an AgentExecution left in pending/running (timeout, crash)."""
    if not execution_id:
        return
    execution = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
    if execution is not None and execution.status in ("pending", "running"):
        execution.status = "failed"
        execution.output_data = {"error": message}
        execution.completed_at = utcnow()
        db.commit()


def notify_terminal(db, run_id: UUID) -> None:
    """Send the notification matching the final state of a run. Never raises."""
    try:
        run = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
        if run is None:
            return
        task = db.query(ScheduledTask).filter(ScheduledTask.id == run.task_id).first()
        user = db.query(User).filter(User.id == run.user_id).first()
        if task is None or user is None:
            return

        channels = task.notify_channels or ["in_app"]
        notify_on = task.notify_on or "always"

        if run.status == "success":
            if notify_on not in ("always", "success"):
                return
            type_, title = "task_result", f"✅ {task.name}"
            body = run.result_text or "(no output)"
        elif run.status == "failed":
            if notify_on not in ("always", "failure"):
                return
            type_, title = "task_failed", f"❌ {task.name} failed"
            body = f"**{task.name}** failed.\n\n{run.error or 'Unknown error'}"
        elif run.status == "expired":
            type_, title = "task_failed", f"⏱ Approval expired: {task.name}"
            body = (
                f"**{task.name}** was not approved in time and has been skipped.\n\n"
                "The next scheduled occurrence will ask for approval again."
            )
        else:
            return

        notification_service.notify(
            db,
            user=user,
            type_=type_,
            title=title,
            body_md=body,
            run_id=run.id,
            channels=channels,
        )
    except Exception:
        logger.exception("Failed to send terminal notification for run %s", run_id)
        try:
            db.rollback()
        except Exception:
            pass


def _notify_approval(db, run: ScheduledTaskRun, task: ScheduledTask, user: User, manifest: List[Dict[str, Any]], reason: str) -> None:
    try:
        actions = "\n".join(f"- {a.get('label', a.get('kind'))}" for a in manifest) or "- (none)"
        expires = run.approval_expires_at.isoformat() if run.approval_expires_at else "n/a"
        body = (
            f"**{task.name}** is waiting for your approval.\n\n"
            f"{reason}\n\nPlanned actions:\n{actions}\n\n"
            f"The approval request expires at {expires}.\n"
            "Open the Scheduler page to approve or reject this run."
        )
        notification_service.notify(
            db,
            user=user,
            type_="approval_required",
            title=f"🔐 Approval required: {task.name}",
            body_md=body,
            run_id=run.id,
            channels=task.notify_channels or ["in_app"],
            force_in_app=True,
        )
    except Exception:
        logger.exception("Failed to send approval notification for run %s", run.id)
        try:
            db.rollback()
        except Exception:
            pass


def _fail(db, run_id: UUID, message: str) -> None:
    _complete(db, run_id, "failed", error=message)
    notify_terminal(db, run_id)


# ─────────────────────────── Execution bodies ────────────────────────────────

def _stream_piece(data: Any) -> str:
    if isinstance(data, str):
        return data
    if isinstance(data, dict):
        for key in ("content", "text", "chunk", "token", "delta"):
            value = data.get(key)
            if isinstance(value, str):
                return value
    return ""


async def _run_agent(
    db,
    run_id: UUID,
    task: ScheduledTask,
    agent: Agent,
    cleaned_input: Dict[str, Any],
) -> Tuple[Any, str]:
    # Imported lazily: pulls every agent class (and their heavy dependencies)
    from app.agents.agent_executor import AgentExecutor

    cfg = agent.config or {}

    # Same behaviour as POST /api/agents/{id}/execute/stream: one conversation per execution
    conversation = Conversation(
        user_id=task.user_id,
        title=f"[Scheduled] {agent.name}"[:255],
        provider_name=cfg.get("llm_provider", "ollama"),
        model=cfg.get("llm_model", ""),
        temperature=cfg.get("llm_temperature", 0.7),
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    input_data = dict(cleaned_input)
    input_data["conversation_id"] = str(conversation.id)

    execution = AgentExecution(
        agent_id=agent.id,
        status="pending",
        trigger="scheduled",
        input_data=input_data,
        started_at=utcnow(),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    execution_id = execution.id

    run = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
    run.agent_execution_id = execution_id
    run.conversation_id = conversation.id
    run.heartbeat_at = utcnow()
    db.commit()

    beat = _Beat(run_id)
    final_result: Any = None
    error_payload: Any = None
    stream_parts: List[str] = []
    stream_size = 0

    executor = AgentExecutor(db)
    async for update in executor.execute_agent(
        agent_id=agent.id,
        execution_id=execution_id,
        input_data=input_data,
    ):
        kind = update.get("type")
        if kind == "result":
            final_result = update.get("data")
        elif kind == "error":
            error_payload = update.get("data")
        elif kind == "stream" and stream_size < 200_000:
            piece = _stream_piece(update.get("data"))
            stream_parts.append(piece)
            stream_size += len(piece)
        beat.tick(db)

    if final_result is None and error_payload is not None:
        message = error_to_text(error_payload)
        # AgentExecutor marks the execution "success" when an agent yields an
        # error instead of raising: correct it so the history stays truthful.
        failed_exec = db.query(AgentExecution).filter(AgentExecution.id == execution_id).first()
        if failed_exec is not None:
            failed_exec.status = "failed"
            failed_exec.output_data = {"error": message}
            db.commit()
        raise RunFailure(message)

    if final_result is not None:
        text = result_to_text(final_result)
    else:
        text = "".join(stream_parts).strip()
    return final_result, text


async def _run_prompt(db, run_id: UUID, task: ScheduledTask, user: User) -> str:
    from app.services.llm_service import LLMService

    llm = LLMService(db)
    provider = await llm.get_active_provider(user.id, task.llm_provider or None)
    provider_cfg = provider.config or {}
    model = task.llm_model or provider_cfg.get("model") or provider_cfg.get("default_model")
    if not model:
        raise RunFailure(f"No model configured for provider '{provider.name}'")
    temperature = task.llm_temperature if task.llm_temperature is not None else 0.5

    conversation = Conversation(
        user_id=user.id,
        title=f"[Scheduled] {task.name}"[:255],
        provider_name=provider.name,
        model=model,
        temperature=temperature,
    )
    db.add(conversation)
    db.commit()
    db.refresh(conversation)

    run = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
    run.conversation_id = conversation.id
    run.heartbeat_at = utcnow()
    db.commit()

    now_local = datetime.now(ZoneInfo(task.timezone or "UTC")).strftime("%A %Y-%m-%d %H:%M (%Z)")
    message = f"[Current date and time: {now_local}]\n\n{task.prompt}"

    beat = _Beat(run_id)
    parts: List[str] = []
    async for chunk in llm.stream_chat(
        user_id=user.id,
        conversation_id=conversation.id,
        message=message,
        provider_name=provider.name,
        model=model,
        temperature=temperature,
    ):
        if chunk:
            parts.append(str(chunk))
        beat.tick(db)

    text = "".join(parts).strip()
    if not text:
        raise RunFailure("The model returned an empty response")
    return text


# ─────────────────────────────── Entry point ─────────────────────────────────

def execute_run(run_id: UUID) -> None:
    """Thread entry point. Never raises."""
    db = SessionLocal()
    try:
        _execute_run(db, run_id)
    except Exception as exc:
        logger.exception("Unhandled error while executing run %s", run_id)
        try:
            db.rollback()
            _fail(db, run_id, f"Internal scheduler error: {exc}")
        except Exception:
            logger.exception("Could not mark run %s as failed", run_id)
    finally:
        db.close()


def _execute_run(db, run_id: UUID) -> None:
    settings = get_settings()

    run = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
    if run is None or run.status != "running":
        return
    task = db.query(ScheduledTask).filter(ScheduledTask.id == run.task_id).first()
    user = db.query(User).filter(User.id == run.user_id).first()
    if task is None or user is None:
        _fail(db, run_id, "Task or user no longer exists")
        return
    if not user.is_active:
        _fail(db, run_id, "User account is inactive")
        return

    # ── Resolve target + manifest ────────────────────────────────────────────
    agent: Optional[Agent] = None
    cleaned: Dict[str, Any] = {}
    if task.task_type == "agent":
        agent = (
            db.query(Agent)
            .filter(Agent.id == task.agent_id, Agent.user_id == task.user_id)
            .first()
        )
        if agent is None:
            _fail(db, run_id, "The agent no longer exists")
            return
        if not agent.is_active:
            _fail(db, run_id, f"Agent '{agent.name}' is not active")
            return
        cleaned, errors = catalog.validate_input(agent.agent_type, task.input_data or {}, None)
        if errors:
            _fail(db, run_id, "Invalid agent input: " + "; ".join(errors))
            return
        manifest = catalog.build_manifest(agent.agent_type, cleaned, agent.config or {})
    elif task.task_type == "prompt":
        manifest = catalog.prompt_manifest()
    else:
        _fail(db, run_id, f"Unknown task type '{task.task_type}'")
        return

    # ── Pre-flight permission policy ─────────────────────────────────────────
    decision = policy.evaluate(
        task.permission_mode, manifest, user.email, task.allowed_recipients or []
    )
    if decision.outcome == "deny":
        _fail(db, run_id, f"Blocked by permission policy: {decision.reason}")
        return

    if decision.outcome == "ask" and run.approved_at is None:
        run.status = "awaiting_approval"
        run.started_at = None
        run.approval_manifest = {"actions": manifest, "reason": decision.reason}
        run.approval_expires_at = utcnow() + timedelta(minutes=task.approval_timeout_minutes or 1440)
        db.commit()
        db.refresh(run)
        _notify_approval(db, run, task, user, manifest, decision.reason)
        return

    # ── Execute ──────────────────────────────────────────────────────────────
    timeout = settings.SCHEDULER_RUN_TIMEOUT_SECONDS
    try:
        if agent is not None:
            final_result, text = asyncio.run(
                asyncio.wait_for(_run_agent(db, run_id, task, agent, cleaned), timeout=timeout)
            )
        else:
            final_result = None
            text = asyncio.run(
                asyncio.wait_for(_run_prompt(db, run_id, task, user), timeout=timeout)
            )
    except TimeoutError:
        db.rollback()
        message = f"Timed out (run limit {timeout}s reached, or a network timeout occurred)"
        current = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
        mark_execution_failed(db, current.agent_execution_id if current else None, message)
        _fail(db, run_id, message)
        return
    except RunFailure as exc:
        db.rollback()
        _fail(db, run_id, str(exc))
        return
    except Exception as exc:
        logger.exception("Run %s failed", run_id)
        db.rollback()
        current = db.query(ScheduledTaskRun).filter(ScheduledTaskRun.id == run_id).first()
        mark_execution_failed(db, current.agent_execution_id if current else None, str(exc))
        _fail(db, run_id, str(exc) or exc.__class__.__name__)
        return

    _complete(
        db,
        run_id,
        "success",
        result_text=text or "(no output)",
        result_data=_json_safe(final_result),
    )
    notify_terminal(db, run_id)
