"""
Scheduler engine (runs inside the dedicated worker process).

Loop (every SCHEDULER_POLL_SECONDS):
  1. enqueue due tasks      scheduled_tasks.next_run_at <= now  -> run(status=queued)
                            claimed with FOR UPDATE SKIP LOCKED: safe with N replicas
  2. housekeeping (30s)     expire approvals, fail runs of dead workers
  3. claim queued runs      queued -> running (SKIP LOCKED), up to free capacity
  4. submit each run to a thread pool (runner.execute_run)

Misfire policy: if the worker was down, a task fires ONCE (coalescing) and the
next occurrence is computed from "now".
Overlap policy: if the previous run of a task is still active, the new
occurrence is recorded as "skipped".
"""
import logging
import signal
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from uuid import UUID

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.models.scheduler import Notification, ScheduledTask, ScheduledTaskRun
from app.services.scheduler import runner
from app.services.scheduler.cron import next_run_after

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = ("queued", "awaiting_approval", "running")
HOUSEKEEPING_EVERY_SECONDS = 30


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_schema(retries: int = 30, delay_seconds: int = 5) -> None:
    """
    Create the scheduler tables if missing (same mechanism as init_db()).
    Retries because the backend may still be creating the base tables.
    """
    import app.models  # noqa: F401  (registers users / agents / ... in the metadata)

    tables = [ScheduledTask.__table__, ScheduledTaskRun.__table__, Notification.__table__]
    last_error: Exception = RuntimeError("unknown")
    for attempt in range(1, retries + 1):
        try:
            Base.metadata.create_all(bind=engine, tables=tables)
            logger.info("Scheduler schema is ready")
            return
        except Exception as exc:
            last_error = exc
            logger.warning("Schema check failed (attempt %s/%s): %s", attempt, retries, exc)
            time.sleep(delay_seconds)
    raise RuntimeError(f"Scheduler schema could not be created: {last_error}")


class SchedulerEngine:
    def __init__(self) -> None:
        self.settings = get_settings()
        self.max_workers = max(1, self.settings.SCHEDULER_MAX_CONCURRENCY)
        self.pool = ThreadPoolExecutor(max_workers=self.max_workers, thread_name_prefix="sched-run")
        self.inflight: Dict[UUID, Future] = {}
        self._stop = threading.Event()
        self._last_housekeeping = 0.0

        # A run is considered dead only well after its timeout
        self.stale_seconds = max(
            self.settings.SCHEDULER_STALE_SECONDS,
            self.settings.SCHEDULER_RUN_TIMEOUT_SECONDS + 300,
        )

    # ───────────────────────────── 1. due tasks ─────────────────────────────

    def enqueue_due_tasks(self, db) -> int:
        now = utcnow()
        tasks: List[ScheduledTask] = (
            db.query(ScheduledTask)
            .filter(
                ScheduledTask.is_enabled.is_(True),
                ScheduledTask.next_run_at.isnot(None),
                ScheduledTask.next_run_at <= now,
            )
            .order_by(ScheduledTask.next_run_at)
            .with_for_update(skip_locked=True)
            .limit(100)
            .all()
        )

        created = 0
        for task in tasks:
            scheduled_for = task.next_run_at
            try:
                task.next_run_at = next_run_after(task.cron_expr, task.timezone or "UTC", now)
            except Exception as exc:
                logger.error("Task %s has an invalid schedule, disabling it: %s", task.id, exc)
                task.is_enabled = False
                task.next_run_at = None
                continue

            active = (
                db.query(ScheduledTaskRun.id)
                .filter(
                    ScheduledTaskRun.task_id == task.id,
                    ScheduledTaskRun.status.in_(ACTIVE_STATUSES),
                )
                .first()
            )
            if active is not None:
                db.add(
                    ScheduledTaskRun(
                        task_id=task.id,
                        user_id=task.user_id,
                        status="skipped",
                        triggered_by="schedule",
                        scheduled_for=scheduled_for,
                        completed_at=now,
                        error="Skipped: the previous run of this task is still active",
                    )
                )
            else:
                db.add(
                    ScheduledTaskRun(
                        task_id=task.id,
                        user_id=task.user_id,
                        status="queued",
                        triggered_by="schedule",
                        scheduled_for=scheduled_for,
                    )
                )
                created += 1

        db.commit()
        if created:
            logger.info("Queued %s run(s)", created)
        return created

    # ───────────────────────────── 2. housekeeping ──────────────────────────

    def expire_approvals(self, db) -> None:
        now = utcnow()
        runs = (
            db.query(ScheduledTaskRun)
            .filter(
                ScheduledTaskRun.status == "awaiting_approval",
                ScheduledTaskRun.approval_expires_at.isnot(None),
                ScheduledTaskRun.approval_expires_at < now,
            )
            .with_for_update(skip_locked=True)
            .limit(50)
            .all()
        )
        ids = []
        for run in runs:
            run.status = "expired"
            run.completed_at = now
            run.error = "Approval request expired"
            ids.append(run.id)
        db.commit()
        for run_id in ids:
            logger.info("Run %s expired (no approval)", run_id)
            runner.notify_terminal(db, run_id)

    def recover_stale_runs(self, db) -> None:
        now = utcnow()
        threshold = now - timedelta(seconds=self.stale_seconds)
        runs = (
            db.query(ScheduledTaskRun)
            .filter(
                ScheduledTaskRun.status == "running",
                ScheduledTaskRun.heartbeat_at.isnot(None),
                ScheduledTaskRun.heartbeat_at < threshold,
            )
            .with_for_update(skip_locked=True)
            .limit(50)
            .all()
        )
        recovered = []
        for run in runs:
            if run.id in self.inflight:
                continue  # still executing in this very process (long blocking call)
            run.status = "failed"
            run.completed_at = now
            run.error = "Interrupted: the worker executing this run was lost"
            recovered.append((run.id, run.agent_execution_id))
        db.commit()
        for run_id, execution_id in recovered:
            logger.warning("Run %s recovered as failed (stale heartbeat)", run_id)
            runner.mark_execution_failed(db, execution_id, "Interrupted: worker lost")
            runner.notify_terminal(db, run_id)

    def housekeeping(self, db) -> None:
        self.expire_approvals(db)
        self.recover_stale_runs(db)

    # ───────────────────────────── 3. claim runs ────────────────────────────

    def claim_runs(self, db, limit: int) -> List[UUID]:
        runs = (
            db.query(ScheduledTaskRun)
            .filter(ScheduledTaskRun.status == "queued")
            .order_by(ScheduledTaskRun.created_at)
            .with_for_update(skip_locked=True)
            .limit(limit)
            .all()
        )
        now = utcnow()
        ids = [run.id for run in runs]
        for run in runs:
            run.status = "running"
            run.started_at = now
            run.heartbeat_at = now
        db.commit()
        return ids

    # ───────────────────────────── loop ─────────────────────────────────────

    def _reap(self) -> None:
        for run_id, future in list(self.inflight.items()):
            if future.done():
                del self.inflight[run_id]
                exc = future.exception()
                if exc is not None:
                    logger.error("Run %s crashed its worker thread: %r", run_id, exc)

    def tick(self) -> None:
        self._reap()
        db = SessionLocal()
        try:
            self.enqueue_due_tasks(db)

            now_m = time.monotonic()
            if now_m - self._last_housekeeping >= HOUSEKEEPING_EVERY_SECONDS:
                self._last_housekeeping = now_m
                self.housekeeping(db)

            capacity = self.max_workers - len(self.inflight)
            if capacity > 0:
                for run_id in self.claim_runs(db, capacity):
                    self.inflight[run_id] = self.pool.submit(runner.execute_run, run_id)
                    logger.info("Run %s started", run_id)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _touch_heartbeat(self) -> None:
        try:
            with open(self.settings.SCHEDULER_HEARTBEAT_FILE, "w") as handle:
                handle.write(str(time.time()))
        except OSError as exc:
            logger.warning("Cannot write heartbeat file: %s", exc)

    def stop(self, *_args) -> None:
        logger.info("Stop signal received, shutting down scheduler loop")
        self._stop.set()

    def run_forever(self) -> None:
        ensure_schema()
        signal.signal(signal.SIGTERM, self.stop)
        signal.signal(signal.SIGINT, self.stop)

        logger.info(
            "Scheduler started (poll=%ss, concurrency=%s, run timeout=%ss)",
            self.settings.SCHEDULER_POLL_SECONDS,
            self.max_workers,
            self.settings.SCHEDULER_RUN_TIMEOUT_SECONDS,
        )
        while not self._stop.is_set():
            try:
                self.tick()
            except Exception:
                logger.exception("Scheduler tick failed")
            self._touch_heartbeat()
            self._stop.wait(self.settings.SCHEDULER_POLL_SECONDS)

        logger.info("Waiting for %s in-flight run(s) to finish...", len(self.inflight))
        self.pool.shutdown(wait=False, cancel_futures=True)
