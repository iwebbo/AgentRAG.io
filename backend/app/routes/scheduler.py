import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import Agent, Provider, User
from app.models.scheduler import ScheduledTask, ScheduledTaskRun
from app.schemas.scheduler import (
    RunDetail,
    RunListItem,
    RunNowRequest,
    TaskDraft,
    TaskPayload,
    TaskResponse,
)
from app.services import notification_service
from app.services.scheduler import catalog, cron, policy

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/scheduler", tags=["Scheduler"])

ACTIVE_STATUSES = ("queued", "awaiting_approval", "running")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ═══════════════════════════════ Helpers ═════════════════════════════════════

def _user_host_names(db: Session, user: User) -> Optional[Set[str]]:
    """Names of the user's remote hosts (None if they cannot be resolved)."""
    try:
        from app.models.remote_host import RemoteHost

        rows = db.query(RemoteHost).filter(RemoteHost.user_id == user.id).all()
        return {h.name for h in rows}
    except Exception as exc:
        db.rollback()
        logger.warning("Could not load remote hosts for validation: %s", exc)
        return None


def _manifest_for_task(task: ScheduledTask, agent: Optional[Agent]) -> List[Dict[str, Any]]:
    if task.task_type == "agent" and agent is not None:
        return catalog.build_manifest(agent.agent_type, task.input_data or {}, agent.config or {})
    return catalog.prompt_manifest()


def _task_out(
    task: ScheduledTask,
    agent: Optional[Agent],
    last_status: Optional[str],
    user: User,
) -> TaskResponse:
    manifest = _manifest_for_task(task, agent)
    decision = policy.evaluate(
        task.permission_mode, manifest, user.email, task.allowed_recipients or []
    )
    return TaskResponse(
        id=task.id,
        name=task.name,
        description=task.description,
        task_type=task.task_type,
        agent_id=task.agent_id,
        agent_name=agent.name if agent else None,
        agent_type=agent.agent_type if agent else None,
        input_data=task.input_data or {},
        prompt=task.prompt,
        llm_provider=task.llm_provider,
        llm_model=task.llm_model,
        llm_temperature=task.llm_temperature,
        cron_expr=task.cron_expr,
        timezone=task.timezone,
        next_run_at=task.next_run_at,
        last_run_at=task.last_run_at,
        is_enabled=task.is_enabled,
        permission_mode=task.permission_mode,
        allowed_recipients=list(task.allowed_recipients or []),
        approval_timeout_minutes=task.approval_timeout_minutes,
        notify_channels=list(task.notify_channels or []),
        notify_on=task.notify_on,
        manifest=manifest,
        policy=decision.to_dict(),
        last_run_status=last_status,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _last_statuses(db: Session, task_ids: List[UUID]) -> Dict[UUID, str]:
    if not task_ids:
        return {}
    rows = (
        db.query(ScheduledTaskRun.task_id, ScheduledTaskRun.status)
        .filter(ScheduledTaskRun.task_id.in_(task_ids))
        .order_by(ScheduledTaskRun.task_id, ScheduledTaskRun.created_at.desc())
        .distinct(ScheduledTaskRun.task_id)
        .all()
    )
    return {row.task_id: row.status for row in rows}


def _get_task(db: Session, user: User, task_id: UUID) -> ScheduledTask:
    task = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.id == task_id, ScheduledTask.user_id == user.id)
        .first()
    )
    if task is None:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def _agent_for(db: Session, task: ScheduledTask) -> Optional[Agent]:
    if not task.agent_id:
        return None
    return db.query(Agent).filter(Agent.id == task.agent_id, Agent.user_id == task.user_id).first()


def _run_item(run: ScheduledTaskRun, task_name: Optional[str]) -> Dict[str, Any]:
    preview = None
    if run.result_text:
        preview = run.result_text[:300] + ("…" if len(run.result_text) > 300 else "")
    return {
        "id": run.id,
        "task_id": run.task_id,
        "task_name": task_name,
        "status": run.status,
        "triggered_by": run.triggered_by,
        "scheduled_for": run.scheduled_for,
        "started_at": run.started_at,
        "completed_at": run.completed_at,
        "result_preview": preview,
        "error": run.error,
        "approval_expires_at": run.approval_expires_at,
        "conversation_id": run.conversation_id,
        "created_at": run.created_at,
    }


def _run_detail(run: ScheduledTaskRun, task_name: Optional[str]) -> RunDetail:
    data = _run_item(run, task_name)
    data.update(
        {
            "result_text": run.result_text,
            "approval_manifest": run.approval_manifest,
            "agent_execution_id": run.agent_execution_id,
            "approved_at": run.approved_at,
        }
    )
    return RunDetail(**data)


# ═══════════════════════════ Validation / building ═══════════════════════════

def _prepare(
    db: Session,
    user: User,
    data: TaskDraft,
    existing: Optional[ScheduledTask] = None,
) -> Dict[str, Any]:
    """Validate a task definition. Shared by /validate, create and update."""
    errors: List[str] = []

    name = (data.name or "").strip()
    if not name:
        errors.append("Name is required")
    else:
        query = db.query(ScheduledTask.id).filter(
            ScheduledTask.user_id == user.id, ScheduledTask.name == name
        )
        if existing is not None:
            query = query.filter(ScheduledTask.id != existing.id)
        if query.first() is not None:
            errors.append(f"A task named '{name}' already exists")

    if data.task_type not in ("agent", "prompt"):
        errors.append("task_type must be 'agent' or 'prompt'")
    if data.permission_mode not in policy.VALID_MODES:
        errors.append("permission_mode must be manual, auto or skip_all")
    if any(ch not in ("in_app", "email") for ch in data.notify_channels):
        errors.append("notify_channels only accepts 'in_app' and 'email'")
    if data.notify_on not in ("always", "success", "failure"):
        errors.append("notify_on must be always, success or failure")
    bad_recipients = [r for r in data.allowed_recipients if not catalog.is_plausible_email(r)]
    if bad_recipients:
        errors.append("Invalid allowed recipient(s): " + ", ".join(bad_recipients))

    # Schedule
    schedule_error = cron.validate_timezone(data.timezone) or cron.validate_cron(data.cron_expr)
    next_runs: List[str] = []
    if schedule_error is None:
        next_runs = [dt.isoformat() for dt in cron.upcoming(data.cron_expr, data.timezone, 5)]
    else:
        errors.append(schedule_error)

    # Target
    agent: Optional[Agent] = None
    cleaned: Dict[str, Any] = {}
    manifest: List[Dict[str, Any]] = []
    if data.task_type == "agent":
        if not data.agent_id:
            errors.append("An agent must be selected")
        else:
            agent = (
                db.query(Agent)
                .filter(Agent.id == data.agent_id, Agent.user_id == user.id)
                .first()
            )
            if agent is None:
                errors.append("Agent not found")
            else:
                hosts = _user_host_names(db, user) if agent.agent_type == "skill" else None
                cleaned, input_errors = catalog.validate_input(
                    agent.agent_type, data.input_data, hosts
                )
                errors.extend(input_errors)
                if not input_errors:
                    manifest = catalog.build_manifest(agent.agent_type, cleaned, agent.config or {})
    elif data.task_type == "prompt":
        if not (data.prompt or "").strip():
            errors.append("A prompt is required")
        manifest = catalog.prompt_manifest()

    # Permissions
    decision = None
    if data.permission_mode in policy.VALID_MODES:
        decision = policy.evaluate(
            data.permission_mode, manifest, user.email, data.allowed_recipients
        )
        if decision.outcome == "deny":
            errors.append(decision.reason)
    if (
        data.permission_mode == "skip_all"
        and not data.confirm_skip_all
        and (existing is None or existing.permission_mode != "skip_all")
    ):
        errors.append("skip_all mode requires an explicit confirmation")

    return {
        "errors": errors,
        "schedule_error": schedule_error,
        "next_runs": next_runs,
        "agent": agent,
        "cleaned_input": cleaned,
        "manifest": manifest,
        "decision": decision,
    }


def _apply(task: ScheduledTask, data: TaskDraft, prep: Dict[str, Any]) -> None:
    agent: Optional[Agent] = prep["agent"]
    task.name = data.name.strip()
    task.description = (data.description or "").strip() or None
    task.task_type = data.task_type

    if data.task_type == "agent" and agent is not None:
        task.agent_id = agent.id
        task.input_data = prep["cleaned_input"]
        task.prompt = None
        task.llm_provider = None
        task.llm_model = None
        task.llm_temperature = None
    else:
        task.agent_id = None
        task.input_data = {}
        task.prompt = (data.prompt or "").strip()
        task.llm_provider = (data.llm_provider or "").strip() or None
        task.llm_model = (data.llm_model or "").strip() or None
        task.llm_temperature = data.llm_temperature if data.llm_temperature is not None else 0.5

    task.cron_expr = data.cron_expr.strip()
    task.timezone = data.timezone
    task.permission_mode = data.permission_mode
    task.allowed_recipients = sorted({str(r).strip().lower() for r in data.allowed_recipients})
    task.approval_timeout_minutes = data.approval_timeout_minutes
    task.notify_channels = list(dict.fromkeys(data.notify_channels)) or ["in_app"]
    task.notify_on = data.notify_on


def _audit_skip_all(user: User, task: ScheduledTask) -> None:
    logger.warning(
        "AUDIT permission_mode=skip_all user=%s task=%s (%s)", user.id, task.id, task.name
    )


# ═══════════════════════════════ Catalog ═════════════════════════════════════

@router.get("/catalog")
def get_catalog(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Agents created by the user (+ how to call them), hosts, providers, limits."""
    agents = (
        db.query(Agent)
        .filter(Agent.user_id == current_user.id)
        .order_by(Agent.name)
        .all()
    )
    agent_entries = []
    for agent in agents:
        spec = catalog.AGENT_INPUT_SPECS.get(agent.agent_type)
        agent_entries.append(
            {
                "id": str(agent.id),
                "name": agent.name,
                "description": agent.description,
                "agent_type": agent.agent_type,
                "type_label": spec["label"] if spec else agent.agent_type,
                "is_active": agent.is_active,
                "supported": spec is not None,
                "fields": spec["fields"] if spec else [],
            }
        )

    hosts: List[Dict[str, Any]] = []
    try:
        from app.models.remote_host import RemoteHost

        for h in db.query(RemoteHost).filter(RemoteHost.user_id == current_user.id).all():
            hosts.append(
                {
                    "name": h.name,
                    "host": h.host,
                    "protocol": h.protocol,
                    "is_active": bool(h.is_active),
                }
            )
    except Exception as exc:
        db.rollback()
        logger.warning("Could not load remote hosts for catalog: %s", exc)

    providers = []
    for p in (
        db.query(Provider)
        .filter(Provider.user_id == current_user.id, Provider.is_active == True)  # noqa: E712
        .order_by(Provider.priority.desc())
        .all()
    ):
        cfg = p.config or {}
        providers.append({"name": p.name, "default_model": cfg.get("model") or cfg.get("default_model")})

    from app.config import get_settings

    return {
        "agents": agent_entries,
        "hosts": hosts,
        "providers": providers,
        "smtp_enabled": notification_service.smtp_enabled(),
        "user_email": current_user.email,
        "min_interval_minutes": get_settings().SCHEDULER_MIN_INTERVAL_MINUTES,
    }


# ═══════════════════════════════ Tasks ═══════════════════════════════════════

@router.post("/tasks/validate")
def validate_task(
    draft: TaskDraft,
    task_id: Optional[UUID] = Query(None, description="Task being edited (name uniqueness)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Live validation for the form: errors, manifest, policy decision, next runs."""
    existing = None
    if task_id is not None:
        existing = (
            db.query(ScheduledTask)
            .filter(ScheduledTask.id == task_id, ScheduledTask.user_id == current_user.id)
            .first()
        )
    prep = _prepare(db, current_user, draft, existing)
    return {
        "valid": not prep["errors"],
        "errors": prep["errors"],
        "schedule_error": prep["schedule_error"],
        "next_runs": prep["next_runs"],
        "cleaned_input": prep["cleaned_input"],
        "manifest": prep["manifest"],
        "policy": prep["decision"].to_dict() if prep["decision"] else None,
    }


@router.get("/tasks", response_model=List[TaskResponse])
def list_tasks(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    tasks = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.user_id == current_user.id)
        .order_by(ScheduledTask.created_at.desc())
        .all()
    )
    agent_ids = [t.agent_id for t in tasks if t.agent_id]
    agents: Dict[UUID, Agent] = {}
    if agent_ids:
        agents = {a.id: a for a in db.query(Agent).filter(Agent.id.in_(agent_ids)).all()}
    last = _last_statuses(db, [t.id for t in tasks])
    return [_task_out(t, agents.get(t.agent_id), last.get(t.id), current_user) for t in tasks]


@router.post("/tasks", response_model=TaskResponse, status_code=201)
def create_task(
    payload: TaskPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    prep = _prepare(db, current_user, payload)
    if prep["errors"]:
        raise HTTPException(status_code=422, detail="; ".join(prep["errors"]))

    task = ScheduledTask(user_id=current_user.id, is_enabled=True)
    _apply(task, payload, prep)
    task.next_run_at = cron.next_run_after(task.cron_expr, task.timezone, utcnow())

    db.add(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail=f"A task named '{task.name}' already exists")
    db.refresh(task)

    if task.permission_mode == "skip_all":
        _audit_skip_all(current_user, task)
    logger.info("Scheduled task created: %s (%s) by user %s", task.name, task.id, current_user.id)
    return _task_out(task, prep["agent"], None, current_user)


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_task(db, current_user, task_id)
    last = _last_statuses(db, [task.id])
    return _task_out(task, _agent_for(db, task), last.get(task.id), current_user)


@router.put("/tasks/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: UUID,
    payload: TaskPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_task(db, current_user, task_id)
    previous_mode = task.permission_mode

    prep = _prepare(db, current_user, payload, existing=task)
    if prep["errors"]:
        raise HTTPException(status_code=422, detail="; ".join(prep["errors"]))

    _apply(task, payload, prep)
    task.next_run_at = (
        cron.next_run_after(task.cron_expr, task.timezone, utcnow()) if task.is_enabled else None
    )
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="A task with this name already exists")
    db.refresh(task)

    if task.permission_mode == "skip_all" and previous_mode != "skip_all":
        _audit_skip_all(current_user, task)
    last = _last_statuses(db, [task.id])
    return _task_out(task, prep["agent"], last.get(task.id), current_user)


@router.patch("/tasks/{task_id}/toggle", response_model=TaskResponse)
def toggle_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_task(db, current_user, task_id)
    task.is_enabled = not task.is_enabled
    task.next_run_at = (
        cron.next_run_after(task.cron_expr, task.timezone, utcnow()) if task.is_enabled else None
    )
    db.commit()
    db.refresh(task)
    last = _last_statuses(db, [task.id])
    return _task_out(task, _agent_for(db, task), last.get(task.id), current_user)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    task = _get_task(db, current_user, task_id)
    logger.info("Scheduled task deleted: %s (%s) by user %s", task.name, task.id, current_user.id)
    db.delete(task)
    db.commit()
    return None


@router.post("/tasks/{task_id}/run", response_model=RunDetail, status_code=202)
def run_task_now(
    task_id: UUID,
    body: Optional[RunNowRequest] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Queue a run immediately (picked up by the worker within a few seconds)."""
    task = _get_task(db, current_user, task_id)

    active = (
        db.query(ScheduledTaskRun.id)
        .filter(ScheduledTaskRun.task_id == task.id, ScheduledTaskRun.status.in_(ACTIVE_STATUSES))
        .first()
    )
    if active is not None:
        raise HTTPException(status_code=409, detail="A run of this task is already active")

    agent = _agent_for(db, task)
    if task.task_type == "agent" and agent is None:
        raise HTTPException(status_code=422, detail="The agent of this task no longer exists")

    manifest = _manifest_for_task(task, agent)
    decision = policy.evaluate(
        task.permission_mode, manifest, current_user.email, task.allowed_recipients or []
    )
    if decision.outcome == "deny":
        raise HTTPException(status_code=422, detail=decision.reason)

    confirmed = bool(body and body.confirm)
    if decision.outcome == "ask" and not confirmed:
        raise HTTPException(
            status_code=409,
            detail={
                "code": "confirmation_required",
                "reason": decision.reason,
                "manifest": manifest,
            },
        )

    run = ScheduledTaskRun(
        task_id=task.id,
        user_id=current_user.id,
        status="queued",
        triggered_by="manual",
        scheduled_for=utcnow(),
        approved_at=utcnow() if decision.outcome == "ask" else None,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return _run_detail(run, task.name)


# ═══════════════════════════════ Runs ════════════════════════════════════════

@router.get("/runs", response_model=List[RunListItem])
def list_runs(
    task_id: Optional[UUID] = None,
    status_filter: Optional[str] = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = (
        db.query(ScheduledTaskRun, ScheduledTask.name)
        .join(ScheduledTask, ScheduledTask.id == ScheduledTaskRun.task_id)
        .filter(ScheduledTaskRun.user_id == current_user.id)
    )
    if task_id is not None:
        query = query.filter(ScheduledTaskRun.task_id == task_id)
    if status_filter:
        query = query.filter(ScheduledTaskRun.status == status_filter)
    rows = query.order_by(ScheduledTaskRun.created_at.desc()).limit(limit).all()
    return [RunListItem(**_run_item(run, name)) for run, name in rows]


@router.get("/runs/{run_id}", response_model=RunDetail)
def get_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    row = (
        db.query(ScheduledTaskRun, ScheduledTask.name)
        .join(ScheduledTask, ScheduledTask.id == ScheduledTaskRun.task_id)
        .filter(ScheduledTaskRun.id == run_id, ScheduledTaskRun.user_id == current_user.id)
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    run, task_name = row
    return _run_detail(run, task_name)


def _lock_run(db: Session, user: User, run_id: UUID) -> ScheduledTaskRun:
    run = (
        db.query(ScheduledTaskRun)
        .filter(ScheduledTaskRun.id == run_id, ScheduledTaskRun.user_id == user.id)
        .with_for_update()
        .first()
    )
    if run is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return run


@router.post("/runs/{run_id}/approve", response_model=RunDetail)
def approve_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = _lock_run(db, current_user, run_id)
    if run.status != "awaiting_approval":
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Run is '{run.status}', not awaiting approval")
    if run.approval_expires_at and run.approval_expires_at < utcnow():
        db.rollback()
        raise HTTPException(status_code=409, detail="The approval request has expired")

    run.status = "queued"
    run.approved_at = utcnow()
    db.commit()
    db.refresh(run)
    logger.info("Run %s approved by user %s", run.id, current_user.id)
    task = db.query(ScheduledTask).filter(ScheduledTask.id == run.task_id).first()
    return _run_detail(run, task.name if task else None)


@router.post("/runs/{run_id}/reject", response_model=RunDetail)
def reject_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    run = _lock_run(db, current_user, run_id)
    if run.status != "awaiting_approval":
        db.rollback()
        raise HTTPException(status_code=409, detail=f"Run is '{run.status}', not awaiting approval")

    run.status = "rejected"
    run.completed_at = utcnow()
    run.error = "Rejected by user"
    db.commit()
    db.refresh(run)
    logger.info("Run %s rejected by user %s", run.id, current_user.id)
    task = db.query(ScheduledTask).filter(ScheduledTask.id == run.task_id).first()
    return _run_detail(run, task.name if task else None)
